#!/usr/bin/env python3
"""
IFC to JSON Converter — Spatial Hierarchy Mode
Extracts structured metadata from IFC building models into a spatially nested JSON.

Hierarchy: Project > Site > Building > Storey > Elements (grouped by type)

Each element includes: property sets, quantities, materials, and classifications.
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
    return list(dict.fromkeys(materials))


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


def extract_element(element):
    """Extract all metadata from a single IFC element."""
    entry = {
        "id": element.GlobalId,
        "ifc_type": element.is_a(),
        "name": element.Name,
        "description": element.Description,
        "type_name": get_type_name(element),
        "materials": get_materials(element),
        "properties": get_property_sets(element),
        "quantities": get_quantities(element),
        "classifications": get_classifications(element),
    }
    # Remove empty fields to keep JSON clean
    return {k: v for k, v in entry.items() if v is not None and v != {} and v != []}


def get_storey_for_element(element):
    """Get the IfcBuildingStorey object that contains this element."""
    try:
        for rel in element.ContainedInStructure:
            structure = rel.RelatingStructure
            if structure.is_a("IfcBuildingStorey"):
                return structure
            if structure.is_a("IfcSpace"):
                for parent_rel in structure.ContainedInStructure:
                    parent = parent_rel.RelatingStructure
                    if parent.is_a("IfcBuildingStorey"):
                        return parent
    except (AttributeError, TypeError):
        pass
    try:
        for rel in element.Decomposes:
            parent = rel.RelatingObject
            if parent.is_a("IfcBuildingStorey"):
                return parent
    except (AttributeError, TypeError):
        pass
    return None


def get_spatial_properties(spatial_element):
    """Extract properties from a spatial structure element (site, building, storey)."""
    props = get_property_sets(spatial_element)
    quants = get_quantities(spatial_element)
    result = {}
    if props:
        result["properties"] = props
    if quants:
        result["quantities"] = quants
    return result


def build_spatial_hierarchy(model):
    """Build the full spatial hierarchy: Project > Site > Building > Storey > Elements."""
    start = time.time()

    # Get the project
    projects = model.by_type("IfcProject")
    if not projects:
        print("  WARNING: No IfcProject found in model")
        return {}
    project = projects[0]

    # Collect all units info
    units_info = {}
    try:
        for rel in project.IsDecomposedBy if hasattr(project, "IsDecomposedBy") else []:
            pass
        # Get unit assignments
        if project.UnitsInContext:
            for unit in project.UnitsInContext.Units:
                try:
                    if unit.is_a("IfcSIUnit"):
                        units_info[unit.UnitType] = {
                            "type": "SI",
                            "name": unit.Name,
                            "prefix": str(unit.Prefix) if unit.Prefix else None,
                        }
                    elif unit.is_a("IfcConversionBasedUnit"):
                        units_info[unit.UnitType] = {
                            "type": "ConversionBased",
                            "name": unit.Name,
                        }
                except Exception:
                    continue
    except (AttributeError, TypeError):
        pass

    # Build element index: storey GlobalId -> list of elements
    print("  Indexing elements to storeys...")
    storey_elements = {}  # storey.GlobalId -> [element_data, ...]
    unassigned_elements = []
    processed = 0

    for element in model.by_type("IfcProduct"):
        # Skip spatial structure elements (except IfcSpace — we keep spaces)
        if element.is_a("IfcSpatialStructureElement") and not element.is_a("IfcSpace"):
            continue

        storey = get_storey_for_element(element)
        entry = extract_element(element)

        if storey:
            gid = storey.GlobalId
            if gid not in storey_elements:
                storey_elements[gid] = []
            storey_elements[gid].append(entry)
        else:
            unassigned_elements.append(entry)

        processed += 1
        if processed % 500 == 0:
            print(f"    Processed {processed} elements...")

    print(f"    Total: {processed} elements indexed")

    # Now build the hierarchy
    print("  Assembling spatial hierarchy...")

    def group_elements_by_type(elements):
        """Group a list of element dicts by their ifc_type."""
        groups = {}
        for elem in elements:
            ifc_type = elem.get("ifc_type", "Unknown")
            if ifc_type not in groups:
                groups[ifc_type] = []
            groups[ifc_type].append(elem)
        return groups

    def build_storey_node(storey_obj):
        gid = storey_obj.GlobalId
        elements = storey_elements.get(gid, [])
        grouped = group_elements_by_type(elements)

        node = {
            "id": gid,
            "name": storey_obj.Name,
            "elevation": storey_obj.Elevation,
            "element_count": len(elements),
        }

        # Add spatial properties of the storey itself
        sp = get_spatial_properties(storey_obj)
        node.update(sp)

        # Sorted type groups
        node["elements_by_type"] = dict(
            sorted(grouped.items(), key=lambda x: -len(x[1]))
        )
        return node

    def build_building_node(building_obj):
        node = {
            "id": building_obj.GlobalId,
            "name": building_obj.Name,
            "description": building_obj.Description,
        }
        sp = get_spatial_properties(building_obj)
        node.update(sp)

        # Get storeys for this building
        storeys = []
        try:
            for rel in building_obj.IsDecomposedBy:
                for child in rel.RelatedObjects:
                    if child.is_a("IfcBuildingStorey"):
                        storeys.append(child)
        except (AttributeError, TypeError):
            pass

        # Sort storeys by elevation
        storeys.sort(key=lambda s: s.Elevation if s.Elevation is not None else 0)

        node["storeys"] = [build_storey_node(s) for s in storeys]
        return node

    def build_site_node(site_obj):
        node = {
            "id": site_obj.GlobalId,
            "name": site_obj.Name,
            "description": site_obj.Description,
        }

        # Site lat/long if available
        try:
            if site_obj.RefLatitude:
                lat_parts = list(site_obj.RefLatitude)
                node["latitude"] = lat_parts
            if site_obj.RefLongitude:
                lon_parts = list(site_obj.RefLongitude)
                node["longitude"] = lon_parts
        except (AttributeError, TypeError):
            pass

        sp = get_spatial_properties(site_obj)
        node.update(sp)

        # Get buildings for this site
        buildings = []
        try:
            for rel in site_obj.IsDecomposedBy:
                for child in rel.RelatedObjects:
                    if child.is_a("IfcBuilding"):
                        buildings.append(child)
        except (AttributeError, TypeError):
            pass

        node["buildings"] = [build_building_node(b) for b in buildings]
        return node

    # Build from project down
    result = {
        "project": {
            "id": project.GlobalId,
            "name": project.Name,
            "description": project.Description,
            "units": units_info,
        }
    }

    # Get sites
    sites = []
    try:
        for rel in project.IsDecomposedBy:
            for child in rel.RelatedObjects:
                if child.is_a("IfcSite"):
                    sites.append(child)
    except (AttributeError, TypeError):
        pass

    result["project"]["sites"] = [build_site_node(s) for s in sites]

    # Unassigned elements (not linked to any storey)
    if unassigned_elements:
        result["unassigned_elements"] = {
            "count": len(unassigned_elements),
            "elements_by_type": dict(
                sorted(
                    group_elements_by_type(unassigned_elements).items(),
                    key=lambda x: -len(x[1]),
                )
            ),
        }

    # Global stats
    all_materials = set()
    all_psets = set()
    type_counts = {}
    all_elements = []
    for gid, elems in storey_elements.items():
        all_elements.extend(elems)
    all_elements.extend(unassigned_elements)

    for elem in all_elements:
        t = elem.get("ifc_type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        for mat in elem.get("materials", []):
            all_materials.add(mat)
        for key in elem.get("properties", {}):
            pset = key.split(".")[0] if "." in key else key
            all_psets.add(pset)

    result["global_summary"] = {
        "total_elements": len(all_elements),
        "element_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
        "property_sets_available": sorted(all_psets),
        "materials_used": sorted(all_materials),
    }

    elapsed = time.time() - start
    print(f"  Hierarchy built in {elapsed:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Convert IFC building model to spatially hierarchical JSON"
    )
    parser.add_argument("input", help="Path to input .ifc file")
    parser.add_argument("output", help="Path for output .json file")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    print(f"Opening IFC file: {args.input}")
    start = time.time()
    model = ifcopenshell.open(args.input)
    print(f"  Loaded in {time.time() - start:.1f}s — Schema: {model.schema}")

    hierarchy = build_spatial_hierarchy(model)

    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, indent=indent, default=str, ensure_ascii=False)

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    elapsed = time.time() - start
    print(f"Written to {args.output} ({size_mb:.1f} MB) in {elapsed:.1f}s total")


if __name__ == "__main__":
    main()
