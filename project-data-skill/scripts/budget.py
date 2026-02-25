#!/usr/bin/env python3
"""Apply a budget template to a total budget amount.

Usage:
    python budget.py --scope gut_renovation --total 1580138

Outputs a JSON object to stdout.
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_FILE = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "..", "budget-skill", "assets", "budget-templates.json")
)

# Map scope keywords to template names in budget-templates.json
SCOPE_TO_TEMPLATE = {
    "gut_renovation": "Gut Renovation",
    "gut_reno": "Gut Renovation",
    "full_rehab": "Gut Renovation",
    "kitchen_remodel": "Kitchen Remodel",
    "kitchen_reno": "Kitchen Remodel",
    "bathroom_remodel": "Bathroom Remodel",
    "bath_remodel": "Bathroom Remodel",
    "new_construction": "Ground Up",
    "ground_up": "Ground Up",
    "custom_home": "Ground Up",
    "room_addition": "Room Addition",
    "addition": "Room Addition",
}


def load_templates():
    with open(TEMPLATES_FILE, "r") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Budget template applicator")
    parser.add_argument("--scope", required=True, help="Scope of work")
    parser.add_argument("--total", required=True, type=float, help="Total budget amount")
    args = parser.parse_args()

    templates = load_templates()

    scope_key = args.scope.lower().strip().replace(" ", "_").replace("-", "_")
    template_name = SCOPE_TO_TEMPLATE.get(scope_key)

    if not template_name or template_name not in templates:
        # Try fuzzy match on template names
        for key, name in SCOPE_TO_TEMPLATE.items():
            if key in scope_key or scope_key in key:
                template_name = name
                break

    if not template_name or template_name not in templates:
        print(json.dumps({"error": f"No budget template found for scope: {args.scope}"}))
        sys.exit(1)

    template = templates[template_name]
    total = args.total

    # Build line items from both soft_costs and hard_costs
    line_items = []
    running_total = 0

    all_items = template["soft_costs"]["items"] + template["hard_costs"]["items"]

    for i, item in enumerate(all_items):
        pct = item["pct_of_total_budget"]
        if i == len(all_items) - 1:
            # Last item absorbs rounding difference
            amount = round(total - running_total)
        else:
            amount = round(total * pct / 100)
        running_total += amount

        line_items.append({
            "category": item["category"],
            "description": f"{item['line_item']} — {item['description']}",
            "amount": amount,
            "pct_of_total": pct,
        })

    # Find contingency percentage
    contingency_pct = 0
    for item in all_items:
        if "contingency" in item["category"].lower() or "contingency" in item["line_item"].lower():
            contingency_pct = item["pct_of_total_budget"]

    result = {
        "scope_of_work": scope_key,
        "total_budget": round(total),
        "line_items": line_items,
        "contingency_pct": contingency_pct,
        "notes": f"Budget generated from '{template_name}' template. "
                 f"Soft costs: {template['soft_costs']['subtotal_pct']}%, "
                 f"Hard costs: {template['hard_costs']['subtotal_pct']}%. "
                 f"{len(line_items)} line items.",
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
