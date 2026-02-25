---
name: budget-skill
description: Seeds a project budget with scope-appropriate line items when a user asks about budget or costs
---

# Budget Skill

Automatically seeds a project's budget with scope-appropriate line items when a user asks about budget or costs.

## What it does

When triggered, the skill:
1. Selects a template based on the project's `scope_of_work`
2. Expands the template into a flat list of `FinancialItem`-compatible estimate records
3. Writes those records into `project.data.financial_data.estimates[]`
4. Sets `source: "budget_template"` on each item so the double-apply guard works

## Required input: project area (square footage)

**Before generating any budget, the skill must request the total project area if it has not been provided.**

Square footage is a critical input because template percentages produce dollar amounts that may be wildly misaligned with real-world unit costs when area is unknown. Always ask:

> "What is the approximate square footage of the area being worked on?"

Once area is known:
- Calculate an implied **cost per square foot** for each major line item
- Compare those implied $/sqft values against regional benchmarks (see table below)
- Flag any line item where the implied $/sqft falls significantly outside the expected range

### Regional $/sqft benchmarks by line item (cosmetic/remodel scope)

| Line Item | Low market (AR, TN, OK) | Mid market (TX, CO, FL) | High market (CA, NY, MA) |
|---|---|---|---|
| Flooring (LVP installed) | $3–5 | $5–8 | $8–14 |
| Flooring (carpet installed) | $2–3 | $3–5 | $5–8 |
| Flooring (tile installed) | $5–8 | $8–12 | $12–20 |
| Interior paint (walls + ceilings) | $1.50–2.50 | $2.50–4 | $4–7 |
| Kitchen remodel (mid-grade) | $50–80/sqft of kitchen | $80–120 | $120–250+ |
| Bath remodel (cosmetic) | $3,000–6,000/bath | $6,000–12,000 | $12,000–25,000+ |
| Exterior paint | $1–2 | $2–3.50 | $3.50–6 |

### Irregularity detection

After calculating implied $/sqft per line item, the skill **must flag irregularities** where the template allocation is inconsistent with known unit costs for the region and scope. An irregularity exists when:

- The implied $/sqft is **more than 2× the regional high benchmark**, or
- The implied $/sqft is **less than 50% of the regional low benchmark**, or
- A line item is allocated budget for work that was **explicitly excluded** by the user (e.g., MEP line items when user said "no utility changes")

When irregularities are found, append a **"⚠️ Line Item Sanity Check"** section (see format below).

## Trigger conditions

| Trigger | Where | Logic |
|---------|-------|-------|
| **NUX (new project onboarding)** | `agents/graphs/onboarding_graph.py → store_onboarding_data` | Always runs when a `scope_of_work` is present and no template has been applied yet |
| **Keyword in email/chat** | `agents/nodes/shared_nodes.py → budget_skill_node` | Runs when `detect_budget_keywords(text)` returns `True` and no template has been applied yet |

## Scope → template mapping

| `scope_of_work` value | Template used |
|-----------------------|---------------|
| `kitchen` | Kitchen Remodel |
| `bathroom` | Bathroom Remodel |
| `whole_house` | Gut Renovation |
| `new_construction` | Ground Up |
| `addition` | Room Addition |
| `adu` | Ground Up *(closest proxy)* |
| `other` | *(none — skill skips silently)* |

## Atypical project commentary

When the user's request includes signals that the project falls outside standard assumptions, the skill's response **must append contextual comments** to the budget output flagging where the template percentages are likely to be inaccurate.

### Signals to watch for

| Signal | Examples |
|--------|----------|
| **High-end / luxury market** | "luxury", "high-end", "premium", "Soho", "Tribeca", "Beverly Hills", "Malibu", "high spec" |
| **High cost-of-living city** | New York, San Francisco, Los Angeles, Miami, Boston, Seattle, Chicago |
| **Atypical project type** | loft conversion, historic building, landmarked property, hillside, below grade |
| **Very large budget** | Any single-scope project over $750k |
| **Client-stated assumptions** | "assume higher soft costs", "this is a luxury build", "high-end finishes" |
| **Excluded scope in template** | User states no MEP, no architect, owner-builder, cosmetic only — remove or zero out inapplicable line items |
| **Area-implied cost mismatch** | Any line item where implied $/sqft falls outside regional benchmarks (see Required input section) |

### What to comment on

When one or more signals are detected, append a **"⚠️ Budget Commentary"** section after the line-item table covering:

1. **Soft costs** — Flag if template soft cost % is likely too low for the market or project type. Provide a realistic range (e.g. "For a high-end NYC loft, soft costs typically run 18–22% vs. 10% in this template").
2. **GC markup** — Flag if the GC fee % is below market for the region (e.g. NYC luxury GC markup is 18–25%, not 9–10%).
3. **Missing line items** — Call out categories not in the template that are common for the project type (e.g. interior designer, expediter, MEP engineer, acoustic consultant for lofts).
4. **Permit & fee exposure** — Flag if the jurisdiction is known for high permit fees, impact fees, or lengthy approval timelines.
5. **Contingency adequacy** — Flag if the contingency % may be insufficient given project complexity, age of building, or hidden conditions risk.

### Format

```
⚠️ Budget Commentary

This budget was generated using the standard [Template Name] template. Based on the project description, the following line items may not reflect real-world costs for this project:

- **Architect / Designer ($X):** For a [high-end / NYC / loft] project, expect $Y–$Z. Consider increasing to X%.
- **GC Overhead & Profit ($X):** NYC luxury GC markup runs 18–25%. This template allocates 9%.
- **Missing: Interior Designer** — Not included in the template. Luxury projects typically budget $50k–$150k.
- **Permits ($X):** NYC DOB permits + expediter for a project this size typically run $40k–$60k.
- **Contingency ($X at 8%):** For a loft conversion with unknown structural conditions, 12–15% is recommended.
```

### Line item sanity check format

When area-implied cost mismatches or excluded-scope issues are detected, append this section after the budget table:

```
⚠️ Line Item Sanity Check

Project area: [X sqft] | Market: [region] | Implied total $/sqft: $X

The following line items appear misaligned with expected costs for this project size and market:

- **Flooring ($22,500 → implied $15/sqft):** For LVP in Fayetteville AR, expect $3–5/sqft installed.
  At 1,500 sqft, a realistic allocation is $4,500–7,500. Suggested adjustment: reduce to $6,000.

- **[Line item] ($X → implied $Y/sqft):** [Explanation]. Suggested adjustment: [action].

- **[Excluded scope removed]:** Template included [line item] but user stated [exclusion reason].
  This line item has been zeroed out / removed.
```

**Rules for suggestions:**
- Always state the implied $/sqft alongside the dollar amount so the irregularity is self-evident
- Provide a concrete revised dollar amount, not just a percentage
- If a line item was excluded by the user, remove it from the table entirely and note it here
- Redistribute freed-up budget to a "Reserve / undecided" line or flag it as available to reallocate

## Double-apply guard

`template_already_applied(project_data)` checks whether any item in `financial_data.estimates[]` already has `source == "budget_template"`. If so, the skill exits early and does nothing.

## Output format

Each line item written to `financial_data.estimates[]`:

```json
{
  "description": "<line_item name>",
  "amount": 0,
  "status": "pending",
  "category": "<category>",
  "vendor": null,
  "source": "budget_template",
  "cost_type": "soft | hard",
  "pct_of_total_budget": 5.0,
  "notes": "<optional note>"
}
```

## Editing the skill (no Python required)

| What to change | Edit this file |
|----------------|----------------|
| Add/remove keyword triggers | `assets/budget-skill-config.json` → `trigger_keywords` array |
| Add/edit line items in a template | `assets/budget-templates.json` → relevant template section |
| Add a new template | `assets/budget-templates.json` + `SCOPE_TO_TEMPLATE` dict in `scripts/budget_skill.py` |

## Implementation files

```
skills/budget-skill/
├── SKILL.md                         ← this file
├── scripts/
│   └── budget_skill.py              ← canonical implementation (pure functions)
├── references/                      ← reserved for future reference docs
└── assets/
    ├── budget-templates.json        ← line-item templates per scope
    └── budget-skill-config.json     ← keyword trigger list
```

Callers import via the stable bridge at `agents/helpers/budget_skill.py`, which re-exports everything from `scripts/budget_skill.py`.
