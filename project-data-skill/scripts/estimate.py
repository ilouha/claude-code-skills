#!/usr/bin/env python3
"""Calculate construction cost estimates from regional_costs.json.

Usage:
    python estimate.py --type gut_renovation --sf 4359 --city "Beverly Hills" --state CA

Outputs a JSON object to stdout.
"""

import argparse
import json
import os
import sys
from math import ceil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COSTS_FILE = os.path.join(
    os.path.dirname(SCRIPT_DIR),
    "..",
    "estimate-skill",
    "references",
    "regional_costs.json",
)
# Normalize the path
COSTS_FILE = os.path.normpath(COSTS_FILE)

# Mapping of common scope keywords to project_types keys (category.subtype)
SCOPE_MAP = {
    "gut_renovation": ("residential", "renovations_major"),
    "gut_reno": ("residential", "renovations_major"),
    "renovations_major": ("residential", "renovations_major"),
    "cosmetic_renovation": ("residential", "renovations_cosmetic"),
    "kitchen_remodel": ("residential", "kitchen_remodel"),
    "kitchen_reno": ("residential", "kitchen_remodel"),
    "bathroom_remodel": ("residential", "bathroom_remodel"),
    "bath_remodel": ("residential", "bathroom_remodel"),
    "new_construction": ("residential", "custom_homes"),
    "custom_home": ("residential", "custom_homes"),
    "room_addition": ("residential", "additions"),
    "addition": ("residential", "additions"),
    "adu": ("residential", "adu_detached"),
    "adu_detached": ("residential", "adu_detached"),
    "adu_conversion": ("residential", "adu_attached_conversion"),
    "luxury_home": ("residential", "luxury_homes"),
    "production_home": ("residential", "production_homes"),
}

# Cities that deserve a premium bump beyond their metro multiplier
PREMIUM_CITIES = {
    "beverly hills": {"metro": "los_angeles", "multiplier": 1.45},
    "malibu": {"metro": "los_angeles", "multiplier": 1.45},
    "palo alto": {"metro": "san_francisco", "multiplier": 1.55},
    "manhattan": {"metro": "new_york_city", "multiplier": 1.60},
    "brooklyn": {"metro": "new_york_city", "multiplier": 1.40},
    "greenwich": {"metro": "new_york_city", "multiplier": 1.40},
    "aspen": {"metro": "denver", "multiplier": 1.40},
}


def load_costs():
    with open(COSTS_FILE, "r") as f:
        return json.load(f)


def find_multiplier(data, city, state):
    """Find the best regional multiplier for a city/state."""
    city_lower = city.lower().strip()

    # Check premium cities first
    if city_lower in PREMIUM_CITIES:
        return PREMIUM_CITIES[city_lower]["multiplier"], city

    # Check metro areas
    city_slug = city_lower.replace(" ", "_").replace("-", "_")
    for region_name, region in data["regions"].items():
        for metro, info in region.get("metros", {}).items():
            if metro == city_slug or city_lower in metro.replace("_", " "):
                return info["multiplier"], metro.replace("_", " ").title()

    # Fall back to state → region default
    state_upper = state.upper().strip()
    region_name = data.get("state_to_region", {}).get(state_upper)
    if region_name and region_name in data["regions"]:
        mult = data["regions"][region_name]["default_multiplier"]
        return mult, f"{region_name} regional default"

    # Ultimate fallback
    return 1.0, "national average (no region match)"


def find_project_type(data, scope_key):
    """Look up base costs for a project type."""
    scope_lower = scope_key.lower().strip().replace(" ", "_").replace("-", "_")

    # Try the scope map first
    if scope_lower in SCOPE_MAP:
        category, subtype = SCOPE_MAP[scope_lower]
        pt = data["project_types"].get(category, {}).get(subtype)
        if pt:
            return pt

    # Brute-force search across all categories
    for category in data["project_types"].values():
        if isinstance(category, dict):
            for key, val in category.items():
                if key == scope_lower or scope_lower in key:
                    return val

    return None


def main():
    parser = argparse.ArgumentParser(description="Construction cost estimator")
    parser.add_argument("--type", required=True, help="Project type / scope of work")
    parser.add_argument("--sf", required=True, type=float, help="Square footage")
    parser.add_argument("--city", required=True, help="City name")
    parser.add_argument("--state", required=True, help="Two-letter state code")
    args = parser.parse_args()

    data = load_costs()

    project = find_project_type(data, args.type)
    if not project:
        print(json.dumps({"error": f"Unknown project type: {args.type}"}))
        sys.exit(1)

    multiplier, source = find_multiplier(data, args.city, args.state)

    result = {
        "project_type": args.type.lower().replace(" ", "_"),
        "square_footage": args.sf,
        "location": f"{args.city}, {args.state}",
        "regional_multiplier": multiplier,
        "cost_per_sf": {
            "low": round(project["low"] * multiplier, 2),
            "mid": round(project["mid"] * multiplier, 2),
            "high": round(project["high"] * multiplier, 2),
        },
        "total_cost": {
            "low": round(project["low"] * multiplier * args.sf, 2),
            "mid": round(project["mid"] * multiplier * args.sf, 2),
            "high": round(project["high"] * multiplier * args.sf, 2),
        },
        "soft_costs_pct": 40 if "renovation" in args.type.lower() or "reno" in args.type.lower() else 30,
        "notes": f"Hard costs only. Base rates: ${project['low']}-${project['high']}/SF national. "
                 f"Multiplier {multiplier} ({source}). "
                 f"Data vintage: {data.get('data_vintage', 'unknown')}. "
                 f"{project.get('notes', '')}",
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
