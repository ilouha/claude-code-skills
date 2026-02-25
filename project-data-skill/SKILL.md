---
name: project-data-skill
description: >
  Run all 7 construction-project skills in sequence for a given address and scope
  of work, collect each skill's output as structured JSON, and save the combined
  result as a single file. Use this skill whenever the user says "full project
  report", "project data", "run all skills", "full analysis", "complete project
  package", or asks you to run every skill for an address. Also trigger when the
  user invokes /project-data-skill.
---

# Project Data Orchestrator

Runs all 7 construction-project skills for a single address, collects structured
JSON from each, and saves a combined project data file.

**Performance note:** This skill uses Python scripts for compute-only steps
(estimate, budget, timeline) and reserves LLM subagents for research steps
(property lookup, zoning, building code, permits). It also caches property and
zoning data so repeat runs for the same address skip web lookups.

## Scripts Directory

All scripts are at: `C:\Users\ilouh\.claude\skills\project-data-skill\scripts\`

- `slugify.py` — address → filename slug
- `estimate.py` — cost estimate from regional_costs.json
- `budget.py` — budget line items from budget-templates.json
- `cache.py` — check/read/write cached property and zoning data

The timeline skill's script is at:
`C:\Users\ilouh\.claude\skills\timeline-skill\scripts\generate_timeline.py`

## Required Inputs

The user **must** provide both of these upfront. If either is missing, ask before
proceeding:

1. **Address** — a full US street address (e.g., "630 N Crescent Drive, Beverly Hills, CA 90210")
2. **Scope of work** — project type (e.g., gut renovation, kitchen remodel, new construction, room addition, bathroom remodel)

Parse the city and state from the address for later use.

## Step 0: Slugify + Check Cache

Run the slugify helper to generate the output filename:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\slugify.py" "<full address>"
```

Capture the output as `SLUG`. Then check if we have cached property data:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\cache.py" check --type property --key "<SLUG>"
```

If `"cached": true`, read the cached property info:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\cache.py" read --type property --key "<SLUG>"
```

If cached and fresh, **skip Step 1 entirely** and proceed to Step 2 using the
cached data. Otherwise continue to Step 1.

Also check zoning cache:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\cache.py" check --type zoning --key "<jurisdiction>-<zone_code>"
```

Create the output directory if needed:
```bash
mkdir -p "C:\Users\ilouh\.claude\outputs\project-data"
```

## Step 1: Property Info (only if cache miss)

Use the Task tool to invoke a **general-purpose** subagent for the
**property-info-skill** lookup. Provide the full address.

Instruct the subagent to:
- Search ONLY official county/city assessor portals (no third-party sites)
- Return a JSON object matching the schema below
- Limit to 3 web searches maximum

After receiving the result, **write it to cache**:

```bash
echo '<property_info_json>' | python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\cache.py" write --type property --key "<SLUG>" --stdin
```

Extract and keep these values for downstream steps:
- `lot_area_sf`, `building_area_sf`, `zone_classification`
- `year_built`, `jurisdiction`, `county`, `state`
- `bedrooms`, `bathrooms`, `stories`, `construction_type`

### property_info JSON schema

```json
{
  "address": "string",
  "apn": "string or null",
  "lot_area_sf": "number or null",
  "building_area_sf": "number or null",
  "zone_classification": "string or null",
  "year_built": "number or null",
  "bedrooms": "number or null",
  "bathrooms": "number or null",
  "stories": "number or null",
  "construction_type": "string or null",
  "jurisdiction": "string",
  "county": "string",
  "state": "string",
  "assessor_url": "string or null",
  "source": "string"
}
```

## Steps 2-4 + 7: Parallel Block

After Step 1 completes (or cache is loaded), launch **four** tasks in parallel
using the Task tool — all in a single message:

1. **Zoning** (subagent — requires web research)
2. **Building Code** (subagent — requires web research)
3. **Permits** (subagent — requires web research)
4. **Timeline** (Python script — instant, no web needed)

### Step 2: Zoning (subagent)

**Check zoning cache first.** If `<jurisdiction>-<zone_code>` is cached, read it
and skip the subagent.

If not cached, use the Task tool with a **general-purpose** subagent. Provide:
- The address, zone_classification, jurisdiction, and state from Step 1
- Instruct: "Use the zoning-skill approach. Limit to 1 web search and max 3 URL
  fetches. Only use official sources (amlegal.com, municode.com, .gov sites)."
- Instruct: "Return ONLY a JSON object matching the schema below."

After receiving the result, **write it to zoning cache**:

```bash
echo '<zoning_json>' | python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\cache.py" write --type zoning --key "<jurisdiction>-<zone_code>" --stdin
```

#### zoning JSON schema

```json
{
  "zone_code": "string",
  "zone_name": "string",
  "jurisdiction": "string",
  "permitted_uses": ["string"],
  "conditionally_permitted_uses": ["string"],
  "setbacks": {
    "front_ft": "number or null",
    "side_ft": "number or null",
    "rear_ft": "number or null"
  },
  "max_height_ft": "number or null",
  "max_stories": "number or null",
  "far": "number or null",
  "lot_coverage_pct": "number or null",
  "parking_required": "string or null",
  "notes": "string or null",
  "source_url": "string or null"
}
```

### Step 3: Building Code (subagent)

Use the Task tool with a **general-purpose** subagent. Provide:
- The occupancy/use type inferred from the scope of work
- Building area, stories, and construction type from Step 1
- The jurisdiction and state
- Instruct: "Use the building-code-skill approach. Use the IBC/CBC to determine
  code requirements. Limit web searches to 3 maximum. Return ONLY a JSON object."

#### building_code JSON schema

```json
{
  "occupancy_group": "string",
  "construction_type": "string",
  "sprinkler_required": "boolean or null",
  "allowable_height_ft": "number or null",
  "allowable_stories": "number or null",
  "allowable_area_sf": "number or null",
  "egress_requirements": {
    "number_of_exits": "number or null",
    "exit_width_in": "number or null",
    "travel_distance_ft": "number or null"
  },
  "fire_resistance_rating_hr": "number or null",
  "applicable_code": "string",
  "notes": "string or null"
}
```

### Step 4: Permits (subagent)

Use the Task tool with a **general-purpose** subagent. Provide:
- The address, scope of work, and jurisdiction from Step 1
- Instruct: "Use the permit-skill approach. Limit web searches to 3 maximum.
  Return ONLY a JSON object."

#### permits JSON schema

```json
{
  "jurisdiction": "string",
  "ahj": "string",
  "permits_required": [
    {
      "permit_type": "string",
      "description": "string",
      "estimated_fee": "string or null",
      "typical_timeline": "string or null"
    }
  ],
  "plan_check_required": "boolean",
  "special_inspections": ["string"],
  "notes": "string or null",
  "source_url": "string or null"
}
```

### Step 7: Timeline (Python script — runs in parallel)

Run the timeline generation script directly — no subagent needed:

```bash
python "C:\Users\ilouh\.claude\skills\timeline-skill\scripts\generate_timeline.py" \
  --type <scope_key> \
  --start-date <today YYYY-MM-DD> \
  --project-name "<address> <scope>" \
  --output "C:\Users\ilouh\.claude\outputs\project-data\<SLUG>-timeline.json"
```

Where `<scope_key>` is one of: `bathroom_remodel`, `kitchen_remodel`,
`gut_renovation`, `new_construction`, `room_addition`.

Read the output file to get the timeline JSON. If the script fails, fall back to
reading the presets manually from:
`C:\Users\ilouh\.claude\skills\timeline-skill\references\presets.json`
and calculating dates yourself.

#### timeline JSON schema

```json
{
  "project_type": "string",
  "start_date": "string (YYYY-MM-DD)",
  "end_date": "string (YYYY-MM-DD)",
  "total_duration_weeks": "number",
  "phases": [
    {
      "phase": "string",
      "start_date": "string (YYYY-MM-DD)",
      "end_date": "string (YYYY-MM-DD)",
      "duration_weeks": "number"
    }
  ],
  "milestones": [
    {
      "name": "string",
      "date": "string (YYYY-MM-DD)"
    }
  ]
}
```

## Step 5: Cost Estimate (Python script — after parallel block)

After all parallel tasks complete, run the estimate script:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\estimate.py" \
  --type "<scope_key>" \
  --sf <building_area_sf or lot_area_sf> \
  --city "<city>" \
  --state "<state>"
```

This reads `regional_costs.json` and outputs JSON to stdout. Capture it as the
`estimate` section. **No subagent needed — this is pure computation.**

#### estimate JSON schema

```json
{
  "project_type": "string",
  "square_footage": "number",
  "location": "string",
  "regional_multiplier": "number",
  "cost_per_sf": { "low": "number", "mid": "number", "high": "number" },
  "total_cost": { "low": "number", "mid": "number", "high": "number" },
  "soft_costs_pct": "number or null",
  "notes": "string or null"
}
```

## Step 6: Budget (Python script — after estimate)

Run the budget script using the mid-tier total from Step 5:

```bash
python "C:\Users\ilouh\.claude\skills\project-data-skill\scripts\budget.py" \
  --scope "<scope_key>" \
  --total <mid_tier_total_cost>
```

This reads `budget-templates.json` and outputs JSON to stdout. Capture it as the
`budget` section. **No subagent needed — this is pure computation.**

#### budget JSON schema

```json
{
  "scope_of_work": "string",
  "total_budget": "number",
  "line_items": [
    {
      "category": "string",
      "description": "string",
      "amount": "number",
      "pct_of_total": "number"
    }
  ],
  "contingency_pct": "number",
  "notes": "string or null"
}
```

## Assembling the Final JSON

After all steps complete, combine everything into a single JSON object:

```json
{
  "meta": {
    "address": "<full address>",
    "slug": "<SLUG>",
    "generated_at": "<ISO 8601 timestamp>",
    "scope_of_work": "<scope>"
  },
  "property_info": { ... },
  "zoning": { ... },
  "building_code": { ... },
  "permits": { ... },
  "estimate": { ... },
  "budget": { ... },
  "timeline": { ... }
}
```

Save to: `C:\Users\ilouh\.claude\outputs\project-data\<SLUG>.json`

Clean up any temp files (like the timeline output file).

## Display Summary

After saving, display a **brief formatted summary** to the user:

```
## Project Data Report: <address>

| Section | Key Finding |
|---------|------------|
| Property | <lot_area_sf> SF lot, <building_area_sf> SF building, built <year_built> |
| Zoning | <zone_code> — <zone_name>, max height <max_height_ft> ft, FAR <far> |
| Building Code | <occupancy_group> / <construction_type>, sprinkler: <yes/no> |
| Permits | <N> permits required: <list of permit types> |
| Estimate | $<low> – $<high> ($<cost_per_sf_low>–$<cost_per_sf_high>/SF) |
| Budget | $<total_budget> across <N> line items |
| Timeline | <total_duration_weeks> weeks (<start_date> → <end_date>) |

Saved to: `C:\Users\ilouh\.claude\outputs\project-data\<SLUG>.json`
```

Fill in actual values from the collected data. If any value is null or unavailable,
show "N/A" in its place.

## Execution Flow Summary

```
Step 0:  slugify.py + cache check                    <1s
Step 1:  Subagent → property info (web)              ~45s  [SKIPPED if cached]
         ┌─ Subagent → zoning (web)                        [SKIPPED if cached]
Steps    ├─ Subagent → building code (web)           ~2-3min (parallel, limited by slowest)
2-4+7:   ├─ Subagent → permits (web)
         └─ generate_timeline.py                     <1s   (parallel)
Step 5:  estimate.py                                 <1s
Step 6:  budget.py                                   <1s
Save:    Assemble JSON + write file                  <1s
```

**First run:** ~3-4 minutes (limited by parallel web research block)
**Repeat run (same address):** ~2-3 minutes (property + zoning cached)
**Repeat run (same address + same zone in same city):** ~2 minutes

## Important Notes

- **Do not re-search the address** after Step 1. Pass property info forward.
- **Each subagent must return JSON** matching the schemas above. Include explicit
  instructions in each subagent prompt: "Return ONLY a JSON object."
- **If any step fails**, record `null` for that section and note the error in a
  `_errors` array in the meta object. Continue with remaining steps.
- **Do not ask the user intermediate questions** between steps. The goal is a
  single unattended run. Use reasonable defaults (today's date for timeline start,
  mid-tier for budget basis).
- **Limit all subagents to 3 web searches max** to prevent slow, sprawling lookups.
