# Advanced Configuration Reference

## Filtering by Element Type

To extract only specific element types (e.g., only MEP or only structural),
edit the `ELEMENT_TYPES` list in `scripts/ifc_to_json.py`.

### Architectural Only
```python
ELEMENT_TYPES = [
    "IfcWall", "IfcWallStandardCase", "IfcDoor", "IfcWindow",
    "IfcSlab", "IfcRoof", "IfcStair", "IfcRailing", "IfcCurtainWall",
    "IfcSpace", "IfcCovering", "IfcFurnishingElement",
]
```

### Structural Only
```python
ELEMENT_TYPES = [
    "IfcColumn", "IfcBeam", "IfcMember", "IfcSlab",
    "IfcFooting", "IfcPile", "IfcPlate", "IfcWall",
]
```

### MEP Only
```python
ELEMENT_TYPES = [
    "IfcDistributionElement",
    "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
    "IfcFlowController", "IfcFlowMovingDevice",
    "IfcEnergyConversionDevice", "IfcSanitaryTerminal",
    "IfcLightFixture", "IfcOutlet", "IfcSwitchingDevice",
]
```

## Geometry Options

### Bounding Box (`--include-geometry`)

Adds a `bounding_box` field to each element with `x_dim`, `y_dim`, `z_dim`
in model units (usually millimeters). Useful for rough size queries like
"which walls are longer than 5 meters?"

### Placement Coordinates (Custom)

To extract element placement coordinates (origin point + rotation), add this
function to the script:

```python
def get_placement(element):
    """Get the local placement origin of an element."""
    try:
        placement = element.ObjectPlacement
        if placement and placement.is_a("IfcLocalPlacement"):
            rel_placement = placement.RelativePlacement
            if rel_placement and rel_placement.is_a("IfcAxis2Placement3D"):
                loc = rel_placement.Location
                return {
                    "x": loc.Coordinates[0],
                    "y": loc.Coordinates[1],
                    "z": loc.Coordinates[2],
                }
    except (AttributeError, TypeError, IndexError):
        pass
    return None
```

Then add `"placement": get_placement(element)` in the `extract_element` function.

## Custom Property Extraction

### Extracting Only Specific Property Sets

If you only want certain property sets (to reduce JSON size), add a filter:

```python
WANTED_PSETS = {"Pset_WallCommon", "Pset_DoorCommon", "Pset_WindowCommon", "Dimensions"}

def get_property_sets(element):
    properties = {}
    for definition in element.IsDefinedBy:
        if definition.is_a("IfcRelDefinesByProperties"):
            prop_set = definition.RelatingPropertyDefinition
            if prop_set.is_a("IfcPropertySet") and prop_set.Name in WANTED_PSETS:
                # ... extraction logic ...
```

### Flattening Property Names

For simpler LLM queries, you can flatten property names by removing the
property set prefix:

```python
# Instead of "Pset_WallCommon.IsExternal": true
# Produce "IsExternal": true
properties[prop.Name] = val  # instead of f"{ps_name}.{prop.Name}"
```

Be aware this can cause name collisions if different property sets share
property names.

## Spatial Hierarchy Mode

For a nested output organized by building > floor > space > elements,
you can restructure the output:

```python
def build_hierarchy(model, elements_data):
    """Build nested spatial hierarchy."""
    hierarchy = {}
    for building in model.by_type("IfcBuilding"):
        bldg = {"name": building.Name, "storeys": {}}
        for rel in building.IsDecomposedBy:
            for storey in rel.RelatedObjects:
                if storey.is_a("IfcBuildingStorey"):
                    storey_elements = [
                        e for e in elements_data
                        if e.get("storey") == storey.Name
                    ]
                    bldg["storeys"][storey.Name] = {
                        "elevation": storey.Elevation,
                        "elements": storey_elements,
                        "element_count": len(storey_elements),
                    }
        hierarchy[building.Name or "Unnamed"] = bldg
    return hierarchy
```

## Performance Tips for Large Models

- Models >100MB IFC may take several minutes to parse
- Use `--summary-only` first to understand the model scope
- Use `--split-by-floor` to break output into manageable chunks
- If JSON exceeds your LLM context window, consider:
  1. Querying one floor at a time
  2. Filtering to specific element types
  3. Using the summary to identify which floor/type to zoom into
  4. Removing the `properties` field if you only need element names and counts
