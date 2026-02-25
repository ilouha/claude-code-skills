# takeoff-skill

Merge Revit schedule exports (CSV/Excel) into a single structured JSON file organized by building element category, with instances grouped by Revit Type. Produces LLM-queryable quantity takeoff data.

## Trigger

Use this skill when the user:
- Uploads or references Revit schedule export files (.csv, .xlsx)
- Asks to merge, combine, or consolidate schedule data
- Wants a quantity takeoff or bill of quantities from schedule files
- Mentions keywords: takeoff, QTO, BOQ, schedule export, merge schedules

## Usage

```bash
# Single file
python "$SKILL_DIR/scripts/takeoff_merge.py" output.json "Wall Schedule.csv" --pretty

# Multiple files (mixed formats)
python "$SKILL_DIR/scripts/takeoff_merge.py" output.json "Wall Schedule.csv" "Doors.xlsx" --pretty

# Multi-sheet Excel workbook
python "$SKILL_DIR/scripts/takeoff_merge.py" output.json "All Schedules.xlsx" --pretty

# Override type column
python "$SKILL_DIR/scripts/takeoff_merge.py" output.json *.csv --type-column "Family and Type" --pretty

# Skip title rows
python "$SKILL_DIR/scripts/takeoff_merge.py" output.json input.xlsx --skip-rows 2 --pretty
```

Where `$SKILL_DIR` = `C:\Users\ilouh\.claude\skills\takeoff-skill`

## Arguments

| Argument | Required | Description |
|---|---|---|
| `output` | Yes | Output JSON file path |
| `inputs` | Yes | One or more CSV or Excel input files |
| `--type-column` | No | Override the column used for type grouping (e.g. "Family and Type") |
| `--pretty` | No | Pretty-print the output JSON (indented) |
| `--skip-rows` | No | Number of leading rows to skip before header detection (default: 0) |

## Dependencies

- **openpyxl** - Required for .xlsx files. Install: `pip install openpyxl`
- All other dependencies are Python stdlib

## Output JSON Structure

```json
{
  "summary": {
    "source_files": ["Wall Schedule.csv", "Doors.xlsx"],
    "categories": {"walls": 45, "doors": 28},
    "total_instances": 73,
    "warnings": [],
    "merged_at": "2026-02-20T..."
  },
  "categories": {
    "walls": {
      "Exterior - 8\" CMU": [
        {"Mark": "W1", "Length": 20.5, "Area": 205.0, ...},
        {"Mark": "W2", "Length": 15.0, "Area": 150.0, ...}
      ],
      "Interior - Partition": [
        {"Mark": "W3", "Length": 8.0, ...}
      ]
    },
    "doors": { ... }
  }
}
```

## How It Works

1. **Reads** all input files (CSV with BOM handling, Excel with `data_only=True`)
2. **Detects** the header row by scanning for rows with 3+ known Revit column names
3. **Detects** the type column (priority: "Type" > "Family and Type" > "Type Name" > contains "type" > "Family")
4. **Filters** out blank rows, subtotals, and grand totals
5. **Converts** imperial dimension strings (e.g. `5' - 3"`) to decimal feet as floats
6. **Coerces** values: Yes/No to booleans, numbers to int/float, imperial dims to decimal feet
7. **Groups** instances by their Revit Type within each category
8. **Normalizes** category names using alias lookup (e.g. "Wall Schedule Export" -> "walls")
9. **Merges** duplicate categories from multiple files
10. **Writes** the structured JSON output

## Imperial Dimension Conversion

All Revit imperial formats are converted to decimal feet:

| Revit String | Decimal Feet |
|---|---|
| `5' - 3"` | `5.25` |
| `1'-6 1/2"` | `1.5417` |
| `3' - 6 3/4"` | `3.5625` |
| `0' - 11 1/4"` | `0.9375` |
| `10' - 0"` | `10.0` |
| `8"` | `0.6667` |
| `12'` | `12.0` |

## Edge Cases

- Title rows before headers are auto-detected and skipped
- Subtotal/Grand Total rows are filtered out
- BOM in CSV files handled via `utf-8-sig` encoding
- Excel formulas resolved via `data_only=True`
- Missing type column: instances grouped under `"_untyped"` + warning
- Category collisions from multiple files: type groups are merged
- Duplicate column names get `_2`, `_3` suffixes
- Empty/placeholder sheets: skipped with a warning
