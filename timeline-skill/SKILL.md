---
name: timeline-skill
description: Use this skill whenever the user discusses a construction or renovation project and needs a timeline, schedule, or milestone plan. Triggers include any mention of project scheduling, timelines, milestones, phases, construction schedules, renovation planning, or when the user describes a scope of work for a bathroom remodel, kitchen remodel, gut renovation, full rehab, ground-up new construction, or room addition. Also trigger when the user wants to update, adjust, or edit an existing project timeline. If the user mentions "Archie" and a project type, this skill should activate. Even if the user just says something like "this is a kitchen reno" or "we're doing a gut job on this brownstone," use this skill to generate or suggest a timeline.
---

# Timeline Skill — Construction Project Milestone Generator

This skill generates editable construction timelines with milestone JSON output. It matches a project to one of 5 preset schedule types, calculates dates from a user-provided start date, and outputs a structured milestone JSON file for dashboard rendering.

## How It Works

1. **Identify the project type** from conversation context
2. **Get the start date** from the user
3. **Load the matching preset** from `references/presets.json`
4. **Generate the milestone JSON** using `scripts/generate_timeline.py`
5. **Present the timeline** to the user for review and editing

## Step-by-Step

### 1. Determine Project Type

Map what the user describes to one of these 5 types:

| Preset Key | Typical Triggers |
|---|---|
| `bathroom_remodel` | Bathroom reno, bath remodel, shower replacement, full bath gut |
| `kitchen_remodel` | Kitchen reno, kitchen remodel, new kitchen, cabinet replacement |
| `gut_renovation` | Gut reno, full rehab, full gut, whole-house renovation, apartment renovation |
| `new_construction` | Ground up, new build, new construction, custom home, building from scratch |
| `room_addition` | Addition, bump-out, extension, adding a room, adding a floor |

If ambiguous, ask the user which type best fits. Don't guess.

### 2. Collect Inputs

You need two things:
- **Project type** (from step 1)
- **Start date** (ask the user — format: YYYY-MM-DD)

Optional:
- **Project name** (e.g., "Smith Kitchen Remodel") — if not provided, generate from type
- **Custom overrides** — the user may want to adjust phase durations before generating

### 3. Generate the Timeline

Read the preset data:
```
cat references/presets.json
```

Then run the generation script:
```bash
python3 scripts/generate_timeline.py \
  --type kitchen_remodel \
  --start-date 2026-03-15 \
  --project-name "Smith Kitchen Remodel" \
  --output /path/to/milestones.json
```

The script reads presets.json, calculates sequential dates for each phase, and outputs the milestone JSON.

### 4. Present & Edit

Show the user the generated timeline as a readable summary (phase name, start → end, duration). If they want to adjust any phase durations, edit the output JSON directly and recalculate downstream dates by re-running the script with `--overrides` or by manually adjusting the JSON.

### 5. Output

The final deliverable is a `milestones.json` file. Always save to `/mnt/user-data/outputs/milestones.json` and present it to the user.

## Output JSON Schema

```json
{
  "project": {
    "name": "Smith Kitchen Remodel",
    "type": "kitchen_remodel",
    "start_date": "2026-03-15",
    "end_date": "2026-07-04",
    "total_duration_weeks": 16,
    "generated_at": "2026-02-20T12:00:00Z"
  },
  "milestones": [
    {
      "id": "phase_1",
      "phase": "Design & Planning",
      "start_date": "2026-03-15",
      "end_date": "2026-04-04",
      "duration_weeks": 3,
      "status": "not_started",
      "dependencies": [],
      "tasks": [
        "Initial consultation & measurements",
        "Layout and material selections",
        "Final design approval"
      ]
    }
  ]
}
```

**Field reference:**
- `id` — Unique phase identifier (`phase_1`, `phase_2`, etc.)
- `phase` — Human-readable phase name
- `start_date` / `end_date` — ISO 8601 date strings (YYYY-MM-DD)
- `duration_weeks` — Length of this phase in weeks
- `status` — One of: `not_started`, `in_progress`, `completed`, `delayed`
- `dependencies` — Array of phase IDs that must complete before this one starts
- `tasks` — Key tasks or deliverables within this phase

## Editing Timelines

When the user wants to modify a timeline:
1. Load the existing `milestones.json`
2. Apply their changes (adjust durations, add/remove phases, rename)
3. Recalculate all downstream dates — phases are sequential, so pushing one phase shifts everything after it
4. Regenerate and output the updated file
