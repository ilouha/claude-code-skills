---
name: permit-skill
description: Identifies permits required for a construction project based on address, scope of work, and jurisdiction
---

# Permit Skill

Identifies the permits required for a construction project based on the project's address, scope of work, and jurisdiction — and outlines the next steps to obtain them.

## What it does

When triggered, the skill:
1. Detects permit-related keywords in the user's message
2. Extracts the jurisdiction from the project address or message text
3. Identifies the Authority Having Jurisdiction (AHJ) for that location
4. Returns the list of permits required for the given scope of work
5. Provides typical timeline, fee estimates, and step-by-step next steps

## Trigger conditions

| Trigger | Where | Logic |
|---------|-------|-------|
| **Keyword in email/chat** | `agents/nodes/shared_nodes.py → permit_skill_node` | Runs when `detect_permit_keywords(text)` returns `True` |
| **NUX onboarding** | `agents/graphs/onboarding_graph.py → store_onboarding_data` | Runs when a project address and `scope_of_work` are present |

## Scope → permit mapping

| Scope | Canonical Key |
|-------|---------------|
| Kitchen remodel / renovation | `kitchen` |
| Bathroom remodel | `bathroom` |
| Gut renovation / whole house / full rehab | `whole_house` |
| New construction / ground up / new build | `new_construction` |
| Addition / room addition | `addition` |
| ADU / accessory dwelling unit / garage conversion | `adu` |
| Demolition / demo / tear down / raze | `demolition` |

## Jurisdiction detection

The skill parses the project address or message text and matches against the `address_keywords` map in `assets/permit-types.json`. If no match is found, it falls back to the `generic` jurisdiction entry in the same file.

**Do not hardcode jurisdiction data here.** All jurisdiction information — AHJ, website, portal, phone, permits by scope, fees, timelines, and next steps — lives in `assets/permit-types.json`. This file is the single source of truth.

To look up which jurisdictions are currently supported, read `assets/permit-types.json` → `address_keywords`.

## Output format

`build_permit_summary()` returns a structured dict:

```json
{
  "jurisdiction_key":    "los_angeles_city",
  "jurisdiction_name":   "City of Los Angeles",
  "ahj":                 "Los Angeles Department of Building and Safety (LADBS)",
  "website":             "https://www.ladbs.org",
  "portal":              "LADBS ePlanCheck & Online Permit Center",
  "phone":               "311",
  "notes":               "LA uses ePlanCheck for most residential...",
  "scope":               "new_construction",
  "permits_required": [
    {
      "type":      "Building Permit",
      "authority": "LADBS",
      "notes":     "Required for all new structures..."
    }
  ],
  "typical_timeline":    "6–18 months",
  "typical_fees":        "1–3% of total construction valuation",
  "estimated_fee_range": "$25,000 – $75,000 (based on $2,500,000 budget)",
  "next_steps": [
    "Hire a licensed architect...",
    "Submit plans via LADBS ePlanCheck..."
  ]
}
```

`format_permit_summary()` converts this dict into a formatted human-readable text block for display in chat or email responses.

## Atypical project flags

After matching a jurisdiction, read its `flags` array from `assets/permit-types.json`. For each flag present, look up the corresponding commentary in the top-level `flag_definitions` object in the same file and append it as a **⚠️ note** at the end of the permit summary response.

**All flag definitions and per-jurisdiction flag assignments live in `assets/permit-types.json` — do not hardcode flag logic here.**

Example behavior:
- Matched jurisdiction has `"flags": ["historic_district", "high_complexity"]`
- Agent reads `flag_definitions.historic_district` and `flag_definitions.high_complexity`
- Both are appended as ⚠️ notes after the permit table

## Editing the skill (no Python required)

| What to change | Edit this file |
|----------------|----------------|
| Add/remove keyword triggers | `assets/permit-skill-config.json` → `trigger_keywords` array |
| Add/edit permits for a jurisdiction | `assets/permit-types.json` → `jurisdictions` → relevant key → `scopes` |
| Add a new jurisdiction | `assets/permit-types.json` → add entry to `address_keywords` + full block to `jurisdictions` |
| Add a new scope alias | `scripts/permit_skill.py` → `SCOPE_ALIASES` dict |
| **Never add jurisdiction data to SKILL.md** | All AHJ info, fees, timelines, and permits belong in `assets/permit-types.json` only |

## Implementation files

```
skills/permit-skill/
├── SKILL.md                          ← this file
├── scripts/
│   └── permit_skill.py               ← canonical implementation (pure functions)
├── references/                       ← reserved for jurisdiction reference docs
└── assets/
    ├── permit-types.json             ← permit requirements by jurisdiction + scope
    └── permit-skill-config.json      ← keyword trigger list
```

Callers import via the stable bridge at `agents/helpers/permit_skill.py`, which re-exports everything from `scripts/permit_skill.py`.
