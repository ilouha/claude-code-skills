---
name: ifc-to-json
description: >
  Convert IFC (Industry Foundation Classes) BIM model files into structured JSON
  for easy querying by LLMs. Use this skill whenever the user uploads an .ifc file,
  mentions Revit/BIM/IFC data, wants to extract building metadata, or wants to
  make architectural model data queryable or searchable. Also trigger when the user
  asks about rooms, walls, doors, floors, MEP elements, materials, or any building
  component data that could come from a BIM model. Even if the user just says
  "convert my model" or "make my building data searchable" — use this skill.
---

# IFC to JSON Conversion Skill

## Purpose

Convert IFC building model files into clean, structured JSON that is optimized
for LLM querying. The JSON output preserves element metadata, property sets,
quantities, materials, spatial hierarchy, and classification — everything an LLM
needs to answer questions about a building without touching geometry.

## When to Use

- User uploads a `.ifc` file
- User asks to "convert", "extract", or "parse" BIM/IFC data
- User wants to query building model data with an LLM
- User mentions Revit export, IFC export, or building information modeling
- User wants a JSON representation of architectural/structural/MEP elements

## Prerequisites

Install IfcOpenShell (the only required dependency):

```bash
pip install ifcopenshell --break-system-packages
```

## Workflow

### Step 1: Identify the IFC File

Check `/mnt/user-data/uploads/` for any `.ifc` files. If multiple are present,
ask the user which one to convert.

### Step 2: Run the Conversion Script

Execute the bundled conversion script:

```bash
python /path/to/this/skill/scripts/ifc_to_json.py <input.ifc> <output.json>
```

Optional flags:
- `--include-geometry` — Include bounding box dimensions (slower, larger output)
- `--split-by-floor` — Output one JSON file per building storey
- `--summary-only` — Output only the model summary index (small file, good for LLM orientation)
- `--pretty` — Pretty-print the JSON (default: compact)

### Step 3: Review and Deliver

1. Copy the output JSON to `/mnt/user-data/outputs/`
2. If the file is very large (>5MB), suggest `--split-by-floor` or `--summary-only`
3. Present the file to the user with a brief summary of what was extracted

## Output Structure

The script produces a JSON file with two top-level keys:

```json
{
  "summary": {
    "file_name": "model.ifc",
    "schema": "IFC4",
    "project_name": "Example Project",
    "site_name": "Example Site",
    "building_name": "Main Building",
    "storeys": ["Level 0", "Level 1", "Level 2", "Roof"],
    "element_counts": {
      "IfcWall": 142,
      "IfcDoor": 38,
      "IfcWindow": 56,
      "IfcSlab": 12,
      "IfcColumn": 24
    },
    "total_elements": 450,
    "property_sets_available": ["Pset_WallCommon", "Dimensions", ...],
    "materials_used": ["Concrete", "Steel", "Glass", ...]
  },
  "elements": [
    {
      "id": "3x4D$sKkz0...",
      "type": "IfcWall",
      "name": "Basic Wall:Exterior - 300mm:12345",
      "description": null,
      "storey": "Level 1",
      "type_name": "Basic Wall:Exterior - 300mm",
      "materials": ["Concrete", "Insulation", "Plaster"],
      "properties": {
        "Pset_WallCommon.IsExternal": true,
        "Pset_WallCommon.FireRating": "2HR",
        "Dimensions.Length": 5400.0,
        "Dimensions.Height": 3000.0
      },
      "quantities": {
        "NetSideArea": 16.2,
        "GrossVolume": 4.86
      },
      "classifications": {
        "Uniclass": "EF_25_10"
      }
    }
  ]
}
```

## Tips for the User

After converting, share these tips with the user:

1. **Start with the summary** — Feed just the `summary` block to an LLM first
   so it understands the model's scope before diving into elements.
2. **Chunk large models** — If the full JSON exceeds your LLM's context window,
   split by floor using `--split-by-floor` and query one floor at a time.
3. **Example LLM queries that work well with this format:**
   - "How many exterior walls are on Level 2?"
   - "What materials are used in the roof slab?"
   - "List all doors with a fire rating above 1 hour"
   - "What is the total net area of all windows?"
   - "Which rooms on Level 1 have concrete floors?"

## Revit Export Advice

If the user hasn't exported from Revit yet, recommend these settings:

- **Format**: IFC4 Reference View (best for metadata extraction; Design Transfer
  View is also fine but produces larger files)
- **Property Sets**: Enable both "Export Revit property sets" AND "Export IFC
  common property sets" — this maximizes queryable data
- **Base quantities**: Enable "Export base quantities" for area/volume data
- **Internal/shared coordinates**: Either works; doesn't affect metadata
- **Phase**: Export the phase relevant to the user's query needs

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: ifcopenshell` | Run `pip install ifcopenshell --break-system-packages` |
| Empty properties in output | User likely didn't enable property set export in Revit — re-export with property sets enabled |
| Very large JSON (>50MB) | Use `--split-by-floor` or `--summary-only` to reduce size |
| Missing spatial info (no storey) | Some IFC exports don't assign elements to storeys — the script will mark these as `"storey": null` |
| IFC2x3 file | The script supports IFC2x3 too, but the output may have fewer properties |

## Advanced: Customizing the Conversion

If the user needs custom extraction (e.g., only MEP elements, or adding
geometric bounding boxes), modify the script's `ELEMENT_TYPES` filter or
enable the `--include-geometry` flag. See `references/advanced-config.md`
for details on customization options.
