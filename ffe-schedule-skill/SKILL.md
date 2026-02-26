---
name: ffe-schedule-skill
description: "Compiles Fixtures, Finishes & Equipment (FF&E) schedules for construction and renovation projects. Use this skill whenever a user mentions FF&E, fixtures finishes and equipment, finish schedules, fixture schedules, material selections, product selections, specifications for remodels or renovations, or is planning ANY construction or renovation project that involves choosing products, materials, or finishes. Also trigger on phrases like 'what do I need to pick out for my remodel', 'what finishes do I need', 'help me with my selections', 'what materials should I choose', 'finish schedule', 'fixture list', 'appliance list', 'what goes into a bathroom/kitchen remodel', 'selections for my renovation', 'interior finishes', 'spec sheet', or any conversation where a homeowner or contractor is scoping a remodel, renovation, addition, or new build and needs to understand what items must be selected. Even if the user never says 'FF&E' explicitly — if they are planning a remodel or renovation and need to understand what to choose, specify, or purchase — USE THIS SKILL."
---

# FF&E Schedule Skill

Generates comprehensive Fixtures, Finishes & Equipment schedules for construction and renovation projects.

## Definitions

- **Fixtures**: Permanently installed items (toilets, sinks, tubs, faucets, cabinetry, built-ins)
- **Finishes**: Surface materials (tile, paint, flooring, countertops, backsplash)
- **Equipment**: MEP devices & appliances (exhaust fans, lights, appliances, HVAC, outlets/switches)

## Supported Project Types

1. **Bathroom Remodel**
2. **Kitchen Remodel**
3. **Gut Renovation** (full interior demo and rebuild)
4. **Ground-Up Construction** (new build from foundation)
5. **Room Addition** (adding new square footage)
6. **Other** (custom scope — home office, basement finish, garage conversion, etc.)

## Workflow

### Step 1 — Gather Project Info

Ask the user for:
- **Project type** (from the 6 above)
- **Rooms/areas included** (required for gut reno, ground-up, addition, other)
- **Style preferences** (optional — modern, traditional, transitional, farmhouse, etc.)
- **Budget tier** (optional — Budget-Friendly / Mid-Range / High-End / Luxury; default Mid-Range)
- **Already-decided items** (anything already purchased or specified)

### Step 2 — Load Presets

Read `references/ffe_presets.md` for the appropriate project type. For larger scopes (gut reno, ground-up, addition, other), combine multiple room presets. Filter or adapt items based on the user's scope.

### Step 3 — Generate JSON FF&E Schedule

Save a single `.json` file to the `outputs/` directory. Use this exact schema:

```json
{
  "project": {
    "name": "<project name or address>",
    "type": "Bathroom Remodel",
    "location": "<city, state>",
    "area_sf": 120,
    "style": "Modern / Contemporary",
    "budget_tier": "High-End",
    "date_generated": "YYYY-MM-DD"
  },
  "summary": {
    "total_items": 32,
    "by_category": { "Fixtures": 15, "Finishes": 8, "Equipment": 9 },
    "long_lead_time_items": ["item — X wk lead"],
    "commonly_forgotten": ["item — why"],
    "dependencies": ["description of dependency"],
    "jurisdiction_notes": ["permit / code notes"]
  },
  "rooms": [
    {
      "room": "Primary Bathroom",
      "items": [
        {
          "category": "Fixtures | Finishes | Equipment",
          "item": "Toilet",
          "description": "Wall-hung; elongated; comfort height; 1.28 GPF",
          "qty": 1,
          "spec_notes": "Verify rough-in 10\"/12\"",
          "allowance_low": 700,
          "allowance_high": 1500,
          "allowance_unit": "each",
          "selection_status": "Not Started",
          "owner_notes": ""
        }
      ]
    }
  ]
}
```

**Schema rules:**
- `allowance_low` / `allowance_high` are **numbers** (no `$` signs, no commas) representing the budget-tier range
- `allowance_unit` is one of: `"each"`, `"per SF"`, `"per LF"`, `"per gal"`, `"lot"`
- For per-unit pricing, also include `"total_low"` and `"total_high"` fields with the calculated total (qty * unit price)
- `selection_status` defaults to `"Not Started"` — valid values: `Not Started`, `In Progress`, `Selected`, `Ordered`, `Installed`
- One object per room in the `rooms` array
- For gut reno / ground-up / addition, include one room object per area (kitchen, bathrooms, living room, etc.)
- `summary.dependencies` should list every item-to-item dependency (e.g., "Undermount sink requires solid-surface countertop")
- `summary.long_lead_time_items` should list items with 4+ week lead times relevant to THIS project
- Filename format: `FFE_Schedule_<ProjectType>_<Area>SF_<Location>.json`

### Step 4 — Present and Explain

Save to outputs directory. Present the file with:
- Total item count and breakdown by category
- Key categories to prioritize first
- Long lead-time items to order early (see presets reference)
- Commonly overlooked items (see presets reference)
- Any dependency flags (e.g., undermount sink requires solid-surface countertop)

## Key Principles

- **Be comprehensive** — better to over-include than miss something; user can delete rows
- **Be practical** — flag long lead-time items and dependencies
- **Be clear** — homeowner-friendly language, not contractor jargon
- **Be realistic** — use current market pricing for the selected budget tier (default mid-range)
- **Flag dependencies** — note when one selection constrains another
