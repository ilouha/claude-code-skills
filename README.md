# Skills

This directory contains specialized skills that the agent can invoke to handle construction and real estate questions. When a user's request matches one of the skills below, the agent **must read the corresponding `SKILL.md` file first** before responding — these files contain the required workflow, templates, reference data paths, and output formats.

## Available Skills

### 1. Zoning (`/zoning-skill`)
Navigate and explain zoning codes for any US jurisdiction. Covers zone classifications (R1, R2, C1, M1, etc.), permitted uses, setbacks, height limits, lot coverage, FAR, density, parking, and land-use questions. Includes bundled reference data for Los Angeles, New York City, and Chicago.

**Read first:** `zoning-skill/SKILL.md`

---

### 2. Building Code (`/building-code-skill`)
Search and interpret the International Building Code (IBC) for construction and life-safety requirements. Covers construction types (Type I-A through Type V-B), occupancy groups, allowable height and area, egress, fire-resistance ratings, sprinkler requirements, and mixed-occupancy separation. Includes bundled IBC reference tables and hyperlinked section citations.

**Read first:** `building-code-skill/SKILL.md`

---

### 3. Permits (`/permit-skill`)
Identify the permits required for a construction project based on address, scope of work, and jurisdiction. Returns the Authority Having Jurisdiction (AHJ), required permits, typical timelines, fee estimates, and step-by-step next steps. Jurisdiction data lives in `permit-skill/assets/permit-types.json`.

**Read first:** `permit-skill/SKILL.md`

---

### 4. Estimates (`/estimate-skill`)
Generate rough planning-level construction cost estimates using SF x cost/SF, adjusted by regional multiplier. Covers 30+ project types and 30+ US metro areas. Outputs a tiered cost table (low / mid / high) with hard cost and soft cost breakdowns.

**Read first:** `estimate-skill/SKILL.md`

---

### 5. Budget (`/budget-skill`)
Seed a project budget with scope-appropriate line items. Maps the project's scope of work to a template (kitchen, bathroom, gut renovation, new construction, addition, ADU), generates line-item estimates, and flags irregularities against regional $/sqft benchmarks.

**Read first:** `budget-skill/SKILL.md`

---

### 7. Property Info (`/property-info-skill`)
Look up property records from county/city assessor databases given a street address. Returns structured property info including parcel number, lot area, building area, legal description, year built, zoning, assessed value, and a direct link to the official assessor record. The skill maintains a growing reference file of assessor portals that auto-updates as new jurisdictions are discovered.

**Read first:** `property-info-skill/SKILL.md`

---

### 6. Timeline (`/timeline-skill`)
Generate editable construction timelines with milestone JSON output. Matches the project to one of 5 preset schedule types (bathroom remodel, kitchen remodel, gut renovation, new construction, room addition), calculates dates from a start date, and outputs structured milestone data.

**Read first:** `timeline-skill/SKILL.md`

---

## New Project Onboarding — Sequential Skill Activation

When a new project is created, the agent **must run all 6 skills in order**, one at a time. Each skill gathers its data before the next one begins. At the end, everything is consolidated into a single project JSON file.

### Activation Sequence

| Step | Skill | What It Collects |
|------|-------|------------------|
| 0 | **Property Info** | Parcel/APN, lot area, building area, year built, zoning/use, assessed value, legal description |
| 1 | **Zoning** | Zone classification, permitted uses, setbacks, height limits, FAR, lot coverage, parking |
| 2 | **Building Code** | Occupancy group, construction type, allowable height/area, egress, fire-resistance, sprinklers |
| 3 | **Permits** | Required permits, AHJ, fees, timelines, next steps |
| 4 | **Estimates** | Hard costs (low/mid/high), soft costs, total project cost |
| 5 | **Budget** | Line-item budget with category breakdowns and irregularity flags |
| 6 | **Timeline** | Phases, milestones, durations, start/end dates |

### Workflow

1. Collect the **project address**, **scope of work**, **square footage**, and **start date** from the user upfront
2. Run each skill sequentially (1 → 2 → 3 → 4 → 5 → 6), reading the `SKILL.md` and following its workflow at each step
3. After all 6 skills have completed, consolidate the outputs into a single JSON file:

```
project-YYYY-MM-DD.json
```

### Export JSON Structure

```json
{
  "project": {
    "address": "",
    "scope_of_work": "",
    "square_footage": 0,
    "created_date": "YYYY-MM-DD"
  },
  "property_info": {
    "parcel_apn": "",
    "lot_area": "",
    "building_area": "",
    "legal_description": "",
    "year_built": "",
    "zoning_use": "",
    "assessed_value": "",
    "owner": "",
    "source": "",
    "direct_link": ""
  },
  "zoning": {
    "jurisdiction": "",
    "zone_classification": "",
    "permitted_uses": [],
    "setbacks": { "front": "", "side": "", "rear": "" },
    "max_height": "",
    "max_far": "",
    "lot_coverage": "",
    "parking": "",
    "state_bonuses": [],
    "caveats": []
  },
  "building_code": {
    "occupancy_group": "",
    "construction_type": "",
    "allowable_height": "",
    "allowable_stories": "",
    "allowable_area_per_floor": "",
    "sprinkler_required": false,
    "fire_resistance_ratings": {},
    "egress_requirements": {},
    "caveats": []
  },
  "permits": {
    "jurisdiction_name": "",
    "ahj": "",
    "permits_required": [],
    "typical_timeline": "",
    "typical_fees": "",
    "next_steps": [],
    "flags": []
  },
  "estimates": {
    "regional_multiplier": 0,
    "cost_per_sf": { "low": 0, "mid": 0, "high": 0 },
    "hard_costs": { "low": 0, "mid": 0, "high": 0 },
    "soft_costs": {},
    "total_project_cost": { "low": 0, "mid": 0, "high": 0 }
  },
  "budget": {
    "template_used": "",
    "line_items": [],
    "total_budget": 0,
    "commentary": [],
    "sanity_checks": []
  },
  "timeline": {
    "start_date": "",
    "end_date": "",
    "total_duration_weeks": 0,
    "milestones": []
  }
}
```

Save the file to the project working directory as `project-YYYY-MM-DD.json` (using the creation date).

---

## How to Use (Individual Skills)

When a user request triggers a single skill outside of project onboarding:

1. **Read the `SKILL.md`** file for the matching skill
2. **Read the referenced data files** (references, assets) as instructed by the SKILL.md
3. **Follow the workflow** defined in the SKILL.md — do not free-form the response
4. **Use the output templates** specified in the SKILL.md
5. **Only search the web** if the bundled reference data is insufficient
