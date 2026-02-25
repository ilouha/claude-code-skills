---
name: estimate-skill
description: Generates rough, high-level construction cost estimates based on SF x cost/SF adjusted by region. Use this skill whenever a user asks about construction costs, building costs, cost per square foot, project budgets, "how much to build," "how much does it cost," development pro formas, RS Means, cost indices, cost estimating, hard costs, construction pricing, or any variation of estimating construction project costs. Also trigger when the user mentions specific project types (e.g., "warehouse," "school," "hotel") in combination with cost or budget language.
---

# Construction Cost Estimate Skill

Generates rough planning-level construction cost estimates using SF x cost/SF, adjusted by regional cost multiplier.

## Workflow

### Step 1: Gather Inputs

Collect three things from the user (ask for anything not provided):

1. **Project type** — What are they building? (e.g., custom home, warehouse, medical office, mid-rise apartments)
2. **Approximate square footage** — Total gross SF of the project
3. **Location** — City and state (or metro area)

If the user provides all three upfront, skip straight to calculation. Don't ask unnecessary follow-up questions.

### Step 2: Look Up Reference Data

**Always read `references/regional_costs.json` first.** This is a local file in the skill directory. Read it before any web search.

The reference file contains:
- Base cost/SF ranges (low, mid, high) for 30+ project types and subtypes
- Regional cost multipliers for 30+ US metro areas organized by region
- Soft cost percentages
- Escalation rates

**Only search the web if:**
- The project type isn't covered in the reference data
- The location is outside the US
- The user specifically asks for current market data or cites a source they want compared
- The user asks about a very specialized building type not in the reference file

When you do search the web, note the source and date of the data.

### Step 3: Calculate

```
Adjusted Cost/SF = Base Cost/SF × Regional Multiplier
Total Estimated Cost = Adjusted Cost/SF × Square Footage
```

**Finding the regional multiplier:**
1. Check if the user's city is listed directly in the metro data
2. If not, use the regional default multiplier for their state's region
3. If the location is ambiguous, state which multiplier you're using and why

### Step 4: Present Results

**Lead with numbers, not disclaimers.** Present a clean table:

```
## Cost Estimate: [Project Type] — [Location]
[SF] SF | Regional Multiplier: [X.XX] ([Metro/Region])

| Tier | Cost/SF | Total |
|------|---------|-------|
| Low  | $XXX    | $X.XXM |
| Mid  | $XXX    | $X.XXM |
| High | $XXX    | $X.XXM |
```

Then show the breakdown:

```
### Hard Costs (Mid Estimate)
Total Hard Cost: $X.XXM

### Soft Costs (estimated 25-35% of hard costs)
| Category         | % of Hard | Amount   |
|------------------|-----------|----------|
| A/E Fees         | 5-12%     | $XXX,XXX |
| Permitting       | 1-5%      | $XX,XXX  |
| Contingency      | 5-15%     | $XXX,XXX |
| Financing        | 2-7%      | $XXX,XXX |
| Other soft costs | 2-5%      | $XX,XXX  |
| **Total Soft**   |           | $XXX,XXX |

### Total Project Cost (Mid Estimate)
Hard + Soft: $X.XXM — $X.XXM
```

**After the numbers**, add one line:

> Planning-level estimate based on [data vintage] cost data. Not a bid — actual costs will vary based on design, site conditions, and market timing.

### Step 5: Soft Cost Detail (if requested or if project > $1M)

For projects over $1M or when the user asks, break out soft costs:

| Category | Typical Range | Applied % | Amount |
|----------|--------------|-----------|--------|
| Architect / Engineer | 5-12% | X% | $XXX |
| Permitting & Fees | 1-5% | X% | $XXX |
| Contingency | 5-15% | X% | $XXX |
| Financing / Carry | 2-7% | X% | $XXX |
| Developer Fee | 3-5% | X% | $XXX |
| Legal / Insurance | 1-3% | X% | $XXX |

Use the lower end for simple/standard projects, higher end for complex/custom/institutional.

## Edge Cases

### Renovations & Tenant Improvements
- Use the renovation/TI cost ranges from the reference data (typically 40-70% of new construction)
- Bump contingency to 15-20% (hidden conditions)
- Note: gut renovations can approach or exceed new construction costs

### Mixed-Use Projects
- Estimate each component separately (e.g., ground floor retail + upper floor residential)
- Apply the appropriate cost/SF to each component
- Sum for total, note that shared systems (MEP, structure, envelope) create some economies

### Very Small Projects (under 2,000 SF)
- Per-SF costs run 15-30% higher due to fixed mobilization costs, minimum crew sizes, and material minimums
- Note this in the estimate

### Very Large Projects (over 100,000 SF)
- Economies of scale typically reduce per-SF costs by 5-15%
- Note this in the estimate

### Luxury / High-End
- Use the high tier as a starting point, not a ceiling
- Ultra-luxury residential can exceed $1,000/SF in major metros
- Note that finishes, custom millwork, and specialty systems drive costs above standard ranges

### ADUs
- Use the ADU-specific line in the reference data
- ADUs are small so per-SF costs are elevated (see "very small projects")
- Detached ADUs cost more than attached/conversion ADUs

## Tone

- Direct and practical
- Lead with numbers, follow with context
- Don't bury the estimate in caveats
- Use plain language, not construction jargon (unless the user is clearly an industry professional)
- If the user gives vague inputs, give a range and explain what would narrow it

## Implementation Files

```
skills/estimate-skill/
├── SKILL.md                          ← this file
└── references/
    └── regional_costs.json           ← cost data by project type and region (2025-Q1)
```
