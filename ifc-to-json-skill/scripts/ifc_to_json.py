#!/usr/bin/env python3
"""
IFC to JSON Converter
Extracts structured metadata from IFC building models into LLM-queryable JSON.

Usage:
    python ifc_to_json.py input.ifc output.json [options]

Options:
    --include-geometry   Include bounding box dimensions per element
    --split-by-floor     Output one JSON file per building storey
    --summary-only       Output only the model summary (no element details)
    --pretty             Pretty-print JSON output
"""

import argparse
import json
import os
import sys
import time

try:
    import ifcopenshell
    import ifcopenshell.util.element as element_util
except ImportError:
    print("ERROR: ifcopenshell is required. Install with:")
    print("  pip install ifcopenshell --break-system-packages")
    sys.exit(1)

# Element types to extract (covers architectural, structural, and MEP)
ELEMENT_TYPES = [
    "IfcWall", "IfcWallStandardCase",
    "IfcDoor", "IfcWindow",
    "IfcSlab", "IfcRoof",
    "IfcColumn", "IfcBeam", "IfcMember",
    "IfcStair", "IfcStairFlight", "IfcRailing",
    "IfcRamp", "IfcRampFlight",
    "IfcCurtainWall",
    "IfcPlate",
    "IfcFooting", "IfcPile",
    "IfcSpace", "IfcZone",
    "IfcFurnishingElement", "IfcFurniture",
    "IfcCovering",
    "IfcBuildingElementProxy",
    # MEP elements
    "IfcDistributionElement",
    "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
    "IfcFlowController", "IfcFlowMovingDevice",
    "IfcEnergyConversionDevice",
    "IfcSanitaryTerminal",
    "IfcLightFixture",
    "IfcOutlet",
    "IfcSwitchingDevice",
]


def get_property_sets(element):
    """Extract all property sets from an element as a flat dict."""
    properties = {}
    try:
        for definition in element.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByProperties"):
                prop_set = definition.RelatingPropertyDefinition
                if prop_set.is_a("IfcPropertySet"):
                    ps_name = prop_set.Name or "UnnamedPset"
                    for prop in prop_set.HasProperties:
                        try:
                            if prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                                val = prop.NominalValue.wrappedValue
                                properties[f"{ps_name}.{prop.Name}"] = val
                            elif prop.is_a("IfcPropertyEnumeratedValue") and prop.EnumerationValues:
                                vals = [v.wrappedValue for v in prop.EnumerationValues]
                                properties[f"{ps_name}.{prop.Name}"] = vals if len(vals) > 1 else vals[0]
                            elif prop.is_a("IfcPropertyBoundedValue"):
                                bounded = {}
                                if prop.UpperBoundValue:
                                    bounded["upper"] = prop.UpperBoundValue.wrappedValue
                                if prop.LowerBoundValue:
                                    bounded["lower"] = prop.LowerBoundValue.wrappedValue
                                if bounded:
                                    properties[f"{ps_name}.{prop.Name}"] = bounded
                            elif prop.is_a("IfcPropertyListValue") and prop.ListValues:
                                properties[f"{ps_name}.{prop.Name}"] = [
                                    v.wrappedValue for v in prop.ListValues
                                ]
                        except Exception:
                            continue
    except (AttributeError, TypeError):
        pass
    return properties


def get_quantities(element):
    """Extract quantities (area, volume, length, etc.) from an element."""
    quantities = {}
    try:
        for definition in element.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByProperties"):
                prop_set = definition.RelatingPropertyDefinition
                if prop_set.is_a("IfcElementQuantity"):
                    for q in prop_set.Quantities:
                        try:
                            if q.is_a("IfcQuantityLength"):
                                quantities[q.Name] = q.LengthValue
                            elif q.is_a("IfcQuantityArea"):
                                quantities[q.Name] = q.AreaValue
                            elif q.is_a("IfcQuantityVolume"):
                                quantities[q.Name] = q.VolumeValue
                            elif q.is_a("IfcQuantityWeight"):
                                quantities[q.Name] = q.WeightValue
                            elif q.is_a("IfcQuantityCount"):
                                quantities[q.Name] = q.CountValue
                            elif q.is_a("IfcQuantityTime"):
                                quantities[q.Name] = q.TimeValue
                        except Exception:
                            continue
    except (AttributeError, TypeError):
        pass
    return quantities


def get_type_name(element):
    """Get the type/family name of an element."""
    try:
        for definition in element.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByType"):
                type_obj = definition.RelatingType
                return type_obj.Name
    except (AttributeError, TypeError):
        pass
    return None


def get_storey(element):
    """Get the building storey that contains this element."""
    try:
        for rel in element.ContainedInStructure:
            structure = rel.RelatingStructure
            if structure.is_a("IfcBuildingStorey"):
                return structure.Name
            # Sometimes elements are in a space which is on a storey
            if structure.is_a("IfcSpace"):
                for parent_rel in structure.ContainedInStructure:
                    parent = parent_rel.RelatingStructure
                    if parent.is_a("IfcBuildingStorey"):
                        return parent.Name
    except (AttributeError, TypeError):
        pass

    # Try via spatial decomposition
    try:
        for rel in element.Decomposes:
            parent = rel.RelatingObject
            if parent.is_a("IfcBuildingStorey"):
                return parent.Name
    except (AttributeError, TypeError):
        pass

    return None


def get_materials(element):
    """Extract material names from an element."""
    materials = []
    try:
        for rel in getattr(element, "HasAssociations", []):
            if rel.is_a("IfcRelAssociatesMaterial"):
                mat = rel.RelatingMaterial
                if mat.is_a("IfcMaterial"):
                    materials.append(mat.Name)
                elif mat.is_a("IfcMaterialList"):
                    for m in mat.Materials:
                        materials.append(m.Name)
                elif mat.is_a("IfcMaterialLayerSetUsage"):
                    for layer in mat.ForLayerSet.MaterialLayers:
                        if layer.Material:
                            materials.append(layer.Material.Name)
                elif mat.is_a("IfcMaterialLayerSet"):
                    for layer in mat.MaterialLayers:
                        if layer.Material:
                            materials.append(layer.Material.Name)
                elif mat.is_a("IfcMaterialConstituentSet"):
                    for constituent in mat.MaterialConstituents:
                        if constituent.Material:
                            materials.append(constituent.Material.Name)
                elif mat.is_a("IfcMaterialProfileSetUsage"):
                    for profile in mat.ForProfileSet.MaterialProfiles:
                        if profile.Material:
                            materials.append(profile.Material.Name)
                elif mat.is_a("IfcMaterialProfileSet"):
                    for profile in mat.MaterialProfiles:
                        if profile.Material:
                            materials.append(profile.Material.Name)
    except (AttributeError, TypeError):
        pass
    return list(dict.fromkeys(materials))  # deduplicate while preserving order


def get_classifications(element):
    """Extract classification references (Uniclass, OmniClass, etc.)."""
    classifications = {}
    try:
        for rel in getattr(element, "HasAssociations", []):
            if rel.is_a("IfcRelAssociatesClassification"):
                ref = rel.RelatingClassification
                if ref.is_a("IfcClassificationReference"):
                    source_name = "Classification"
                    if ref.ReferencedSource:
                        source_name = ref.ReferencedSource.Name or "Classification"
                    classifications[source_name] = ref.Identification or ref.Name
    except (AttributeError, TypeError):
        pass
    return classifications


def get_bounding_box(element):
    """Get bounding box dimensions if geometry representation exists."""
    try:
        if element.Representation:
            for rep in element.Representation.Representations:
                for item in rep.Items:
                    if item.is_a("IfcBoundingBox"):
                        return {
                            "x_dim": item.XDim,
                            "y_dim": item.YDim,
                            "z_dim": item.ZDim,
                        }
    except (AttributeError, TypeError):
        pass
    return None


def extract_element(element, include_geometry=False):
    """Extract all metadata from a single IFC element."""
    entry = {
        "id": element.GlobalId,
        "type": element.is_a(),
        "name": element.Name,
        "description": element.Description,
        "storey": get_storey(element),
        "type_name": get_type_name(element),
        "materials": get_materials(element),
        "properties": get_property_sets(element),
        "quantities": get_quantities(element),
        "classifications": get_classifications(element),
    }

    if include_geometry:
        bbox = get_bounding_box(element)
        if bbox:
            entry["bounding_box"] = bbox

    # Remove empty fields to keep JSON clean
    return {k: v for k, v in entry.items() if v is not None and v != {} and v != []}


def build_summary(model, elements_data):
    """Build a summary/index of the model."""
    # Project info
    projects = model.by_type("IfcProject")
    project_name = projects[0].Name if projects else None

    sites = model.by_type("IfcSite")
    site_name = sites[0].Name if sites else None

    buildings = model.by_type("IfcBuilding")
    building_name = buildings[0].Name if buildings else None

    storeys = model.by_type("IfcBuildingStorey")
    storey_names = sorted(
        [s.Name for s in storeys if s.Name],
        key=lambda x: next(
            (s.Elevation for s in storeys if s.Name == x and s.Elevation is not None),
            0
        )
    )

    # Count elements by type
    type_counts = {}
    for elem in elements_data:
        t = elem.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Collect all unique property set names
    all_psets = set()
    for elem in elements_data:
        for key in elem.get("properties", {}):
            pset = key.split(".")[0] if "." in key else key
            all_psets.add(pset)

    # Collect all unique materials
    all_materials = set()
    for elem in elements_data:
        for mat in elem.get("materials", []):
            all_materials.add(mat)

    return {
        "file_name": os.path.basename(model.wrapped_data.header.file_name.name)
        if hasattr(model.wrapped_data, "header") else None,
        "schema": model.schema,
        "project_name": project_name,
        "site_name": site_name,
        "building_name": building_name,
        "storeys": storey_names,
        "element_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
        "total_elements": len(elements_data),
        "property_sets_available": sorted(all_psets),
        "materials_used": sorted(all_materials),
    }


def convert_ifc_to_json(
    input_path,
    output_path,
    include_geometry=False,
    split_by_floor=False,
    summary_only=False,
    pretty=False,
):
    """Main conversion function."""
    print(f"Opening IFC file: {input_path}")
    start = time.time()
    model = ifcopenshell.open(input_path)
    print(f"  Loaded in {time.time() - start:.1f}s — Schema: {model.schema}")

    # Extract all product elements
    print("Extracting elements...")
    elements_data = []
    processed = 0

    for element in model.by_type("IfcProduct"):
        # Skip spatial structure elements (buildings, storeys, sites)
        if element.is_a("IfcSpatialStructureElement") and not element.is_a("IfcSpace"):
            continue

        entry = extract_element(element, include_geometry)
        elements_data.append(entry)
        processed += 1
        if processed % 500 == 0:
            print(f"  Processed {processed} elements...")

    print(f"  Total elements extracted: {len(elements_data)}")

    # Build summary
    summary = build_summary(model, elements_data)

    indent = 2 if pretty else None

    if summary_only:
        output = {"summary": summary}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=indent, default=str, ensure_ascii=False)
        print(f"Summary written to {output_path}")
        return

    if split_by_floor:
        # Group elements by storey
        floors = {}
        no_floor = []
        for elem in elements_data:
            storey = elem.get("storey")
            if storey:
                floors.setdefault(storey, []).append(elem)
            else:
                no_floor.append(elem)

        base, ext = os.path.splitext(output_path)
        written_files = []

        for storey_name, storey_elements in floors.items():
            safe_name = storey_name.replace(" ", "_").replace("/", "-")
            floor_path = f"{base}_{safe_name}{ext}"
            floor_summary = build_summary(model, storey_elements)
            floor_summary["storey_filter"] = storey_name
            output = {"summary": floor_summary, "elements": storey_elements}
            with open(floor_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=indent, default=str, ensure_ascii=False)
            written_files.append(floor_path)
            print(f"  {storey_name}: {len(storey_elements)} elements -> {floor_path}")

        if no_floor:
            unassigned_path = f"{base}_unassigned{ext}"
            output = {"summary": build_summary(model, no_floor), "elements": no_floor}
            with open(unassigned_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=indent, default=str, ensure_ascii=False)
            written_files.append(unassigned_path)
            print(f"  Unassigned: {len(no_floor)} elements -> {unassigned_path}")

        # Also write the full summary
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "floor_files": written_files}, f, indent=indent, default=str, ensure_ascii=False)
        print(f"Summary index written to {output_path}")
    else:
        output = {"summary": summary, "elements": elements_data}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=indent, default=str, ensure_ascii=False)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Written to {output_path} ({size_mb:.1f} MB)")
        if size_mb > 5:
            print(f"  TIP: File is large. Consider --split-by-floor or --summary-only")

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Convert IFC building model to LLM-queryable JSON"
    )
    parser.add_argument("input", help="Path to input .ifc file")
    parser.add_argument("output", help="Path for output .json file")
    parser.add_argument(
        "--include-geometry",
        action="store_true",
        help="Include bounding box dimensions per element",
    )
    parser.add_argument(
        "--split-by-floor",
        action="store_true",
        help="Output one JSON file per building storey",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Output only the model summary index",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    convert_ifc_to_json(
        input_path=args.input,
        output_path=args.output,
        include_geometry=args.include_geometry,
        split_by_floor=args.split_by_floor,
        summary_only=args.summary_only,
        pretty=args.pretty,
    )


if __name__ == "__main__":
    main()
