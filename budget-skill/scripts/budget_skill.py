"""
Budget Skill Helper — pure functions for budget template seeding.

Provides helpers for:
- Loading the budget template config (skills/budget-skill/assets/budget-templates.json)
- Loading the keyword trigger config (skills/budget-skill/assets/budget-skill-config.json)
- Detecting budget-related keywords in user text
- Building FinancialItem-compatible line-item dicts from a template
- Detecting atypical project signals (luxury, high-COL city, large budget, etc.)
- Generating contextual budget commentary when template assumptions don't fit

No DB access, no LangGraph state management. Purely functional so each
piece is independently testable.

Called by:
    - agents/helpers/budget_skill.py (bridge module re-exports everything here)
    - agents/nodes/shared_nodes.py (budget_skill_node — email & chat graphs)
    - agents/graphs/onboarding_graph.py (store_onboarding_data — NUX trigger)

Update History:
    - 2026-02-18: Initial creation for budget-skill feature
    - 2026-02-18: Moved to skills/budget-skill/scripts/ per Anthropic skill convention
    - 2026-02-18: Added detect_atypical_signals + generate_budget_commentary
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_CONFIG_DIR = Path(__file__).parent.parent / "assets"
_TEMPLATES_PATH = _CONFIG_DIR / "budget-templates.json"
_SKILL_CONFIG_PATH = _CONFIG_DIR / "budget-skill-config.json"

# ---------------------------------------------------------------------------
# NUX scope → template key mapping
# ---------------------------------------------------------------------------
SCOPE_TO_TEMPLATE: dict[str, str | None] = {
    "kitchen": "Kitchen Remodel",
    "bathroom": "Bathroom Remodel",
    "whole_house": "Gut Renovation",
    "new_construction": "Ground Up",
    "addition": "Room Addition",
    "adu": "Ground Up",                # closest available proxy
    "other": None,                     # no template — skip
}


# ---------------------------------------------------------------------------
# Loaders (cached so files are read once per process lifetime)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_budget_templates() -> dict:
    """
    Load and cache the budget template definitions from JSON.

    Reads skills/budget-skill/assets/budget-templates.json exactly once per
    process, then returns the cached result on subsequent calls. Structure:

        {
          "Kitchen Remodel": {
            "soft_costs": { "subtotal_pct": 5.0, "items": [...] },
            "hard_costs":  { "subtotal_pct": 95.0, "items": [...] },
            "total_pct": 100.0
          },
          ...
        }

    Called by: get_template_for_scope, build_estimate_line_items

    Returns:
        dict: Full template mapping. Empty dict on file/parse error.
    """
    try:
        with open(_TEMPLATES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"💰 Loaded budget templates: {list(data.keys())}")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load budget-templates.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_budget_skill_config() -> dict:
    """
    Load and cache the budget skill keyword trigger config from JSON.

    Reads skills/budget-skill/assets/budget-skill-config.json exactly once
    per process. Structure:

        { "trigger_keywords": ["budget", "create budget", ...] }

    Called by: detect_budget_keywords

    Returns:
        dict: Config dict. Returns {"trigger_keywords": []} on error.
    """
    try:
        with open(_SKILL_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"💰 Loaded budget skill config: {len(data.get('trigger_keywords', []))} keywords")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load budget-skill-config.json: {e}")
        return {"trigger_keywords": []}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def detect_budget_keywords(text: str) -> bool:
    """
    Return True if any budget trigger keyword is found in text.

    Performs case-insensitive substring matching. A single match is enough
    to return True. Returns False on empty text or empty keyword list.

    Called by: agents/nodes/shared_nodes.py (budget_skill_node)

    Args:
        text (str): The email body or chat input to scan.

    Returns:
        bool: True if at least one trigger keyword matched.
    """
    if not text:
        return False
    lower_text = text.lower()
    keywords = load_budget_skill_config().get("trigger_keywords", [])
    for kw in keywords:
        if kw.lower() in lower_text:
            logger.debug(f"💰 Budget keyword matched: '{kw}'")
            return True
    return False


def get_template_for_scope(scope_of_work: str) -> dict | None:
    """
    Map a NUX scope_of_work value to the matching budget template dict.

    Uses SCOPE_TO_TEMPLATE to translate the short scope code to a template
    key, then returns the corresponding section from budget-templates.json.

    Called by: build_estimate_line_items

    Args:
        scope_of_work (str): NUX scope code, e.g. "kitchen", "bathroom",
            "whole_house", "new_construction", "addition", "adu", "other".

    Returns:
        dict | None: Template dict with "soft_costs"/"hard_costs" keys,
            or None if no template matches the scope.
    """
    template_key = SCOPE_TO_TEMPLATE.get(scope_of_work)
    if template_key is None:
        logger.debug(f"💰 No template for scope '{scope_of_work}' (expected, e.g. 'other')")
        return None
    templates = load_budget_templates()
    template = templates.get(template_key)
    if template is None:
        logger.warning(f"💰 Template key '{template_key}' not found in budget-templates.json")
    return template


def build_estimate_line_items(scope_of_work: str) -> list[dict]:
    """
    Build a flat list of FinancialItem-compatible dicts from the scope template.

    Iterates over both soft_costs and hard_costs sections of the matching
    template and returns one dict per line item. Items are compatible with
    the existing financial_data.estimates[] schema used by the frontend's
    extractEstimates() function.

    Each returned item:
        {
          "description":        "<line_item>",
          "amount":             0,
          "status":             "pending",
          "category":           "<category>",
          "vendor":             None,
          "source":             "budget_template",
          "cost_type":          "soft" | "hard",
          "pct_of_total_budget": <float>,
          "notes":              "<notes>"
        }

    The extra fields (cost_type, pct_of_total_budget, notes) are stored but
    currently ignored by the frontend — available for future use.

    Called by:
        - agents/nodes/shared_nodes.py (budget_skill_node)
        - agents/graphs/onboarding_graph.py (store_onboarding_data)

    Args:
        scope_of_work (str): NUX scope code used to select the template.

    Returns:
        list[dict]: Flat list of estimate line items. Empty list if no template
            matches the scope or the template has no items.
    """
    template = get_template_for_scope(scope_of_work)
    if not template:
        return []

    items: list[dict] = []
    for cost_type, section_key in [("soft", "soft_costs"), ("hard", "hard_costs")]:
        section = template.get(section_key, {})
        for raw in section.get("items", []):
            items.append({
                "description": raw.get("line_item", ""),
                "amount": 0,
                "status": "pending",
                "category": raw.get("category", ""),
                "vendor": None,
                "source": "budget_template",
                "cost_type": cost_type,
                "pct_of_total_budget": raw.get("pct_of_total_budget", 0.0),
                "notes": raw.get("notes", ""),
            })

    logger.debug(f"💰 Built {len(items)} line items for scope '{scope_of_work}'")
    return items


# ---------------------------------------------------------------------------
# Atypical project signal detection & commentary
# ---------------------------------------------------------------------------

_LUXURY_KEYWORDS = {
    "luxury", "high-end", "high end", "premium", "soho", "tribeca",
    "beverly hills", "malibu", "high spec", "bespoke", "upscale",
}
_HIGH_COL_CITIES = {
    "new york", "nyc", "manhattan", "brooklyn", "san francisco", "sf",
    "los angeles", "miami", "boston", "seattle", "chicago",
}
_ATYPICAL_TYPES = {
    "loft", "historic", "landmarked", "landmark", "hillside",
    "below grade", "below-grade", "conversion", "penthouse", "warehouse",
}
_CLIENT_STATED = {
    "assume higher", "luxury build", "high-end finishes",
    "premium finishes", "higher soft costs", "high end project",
}
_LARGE_BUDGET_THRESHOLD = 750_000


def detect_atypical_signals(text: str, total_budget: float = 0.0) -> list[str]:
    """
    Detect signals that indicate a project is outside standard template assumptions.

    Checks the user text and budget for known atypical indicators. Returns a list
    of signal category strings. Empty list means no atypical signals detected.

    Signal categories:
        "luxury_market"  — luxury/high-end keywords or locations
        "high_col_city"  — high cost-of-living city detected
        "atypical_type"  — atypical project type (loft, historic, etc.)
        "client_stated"  — user explicitly stated non-standard assumptions
        "large_budget"   — total_budget >= $750k for a single scope

    Args:
        text (str): User message / project description to scan.
        total_budget (float): Total project budget in dollars.

    Returns:
        list[str]: Detected signal categories (may be empty).
    """
    signals = []
    lower = text.lower() if text else ""

    if any(kw in lower for kw in _LUXURY_KEYWORDS):
        signals.append("luxury_market")
    if any(city in lower for city in _HIGH_COL_CITIES):
        signals.append("high_col_city")
    if any(t in lower for t in _ATYPICAL_TYPES):
        signals.append("atypical_type")
    if any(s in lower for s in _CLIENT_STATED):
        signals.append("client_stated")
    if total_budget >= _LARGE_BUDGET_THRESHOLD:
        signals.append("large_budget")

    if signals:
        logger.debug(f"💰 Atypical signals detected: {signals}")
    return signals


def generate_budget_commentary(
    scope_of_work: str,
    total_budget: float,
    signals: list[str],
    text: str = "",
) -> str | None:
    """
    Generate a contextual commentary block when atypical project signals are present.

    Returns a formatted ⚠️ Budget Commentary string highlighting where the standard
    template percentages may underrepresent real-world costs for this project type.
    Returns None if no signals are detected (standard project — no commentary needed).

    Called by: agents/nodes/shared_nodes.py, agents/graphs/onboarding_graph.py

    Args:
        scope_of_work (str): NUX scope code used to identify the template.
        total_budget (float): Total project budget in dollars.
        signals (list[str]): Signal categories from detect_atypical_signals().
        text (str): Original user message for additional keyword matching.

    Returns:
        str | None: Commentary string, or None if no signals.
    """
    if not signals:
        return None

    template = get_template_for_scope(scope_of_work) or {}
    lower_text = text.lower()

    soft_pct = template.get("soft_costs", {}).get("subtotal_pct", 0.0)

    all_items = [
        i
        for section_key in ("soft_costs", "hard_costs")
        for i in template.get(section_key, {}).get("items", [])
    ]
    gc_item          = next((i for i in all_items if "general contractor" in i.get("line_item", "").lower()), None)
    contingency_item = next((i for i in all_items if "contingency"        in i.get("line_item", "").lower()), None)
    permit_item      = next((i for i in all_items if "permit"             in i.get("line_item", "").lower()), None)

    is_luxury   = "luxury_market" in signals
    is_high_col = "high_col_city" in signals
    is_atypical = "atypical_type" in signals
    is_large    = "large_budget"   in signals
    is_loft     = "loft" in lower_text
    is_nyc      = any(c in lower_text for c in ("new york", "nyc", "manhattan", "brooklyn", "soho", "tribeca"))

    lines = [
        "⚠️  Budget Commentary",
        "",
        "This budget was generated using the standard template. Based on the project",
        "description, the following may not reflect real-world costs for this project:",
        "",
    ]

    # Soft costs
    if is_luxury or is_high_col or is_large:
        rec = "18–22%" if is_high_col else "15–18%"
        rec_lo = total_budget * (0.18 if is_high_col else 0.15)
        rec_hi = total_budget * (0.22 if is_high_col else 0.18)
        lines.append(
            f"• Soft Costs ({soft_pct:.0f}% / ${total_budget * soft_pct / 100:,.0f}): "
            f"{'High cost-of-living markets' if is_high_col else 'High-end projects'} typically "
            f"require {rec} in soft costs (${rec_lo:,.0f}–${rec_hi:,.0f}). "
            f"This template allocates {soft_pct:.0f}%."
        )

    # GC markup
    if gc_item and (is_luxury or is_high_col):
        gc_pct = gc_item["pct_of_total_budget"]
        rec_gc = "18–25%" if is_nyc else "15–20%"
        lines.append(
            f"• GC Overhead & Profit ({gc_pct:.0f}% / ${total_budget * gc_pct / 100:,.0f}): "
            f"{'NYC' if is_nyc else 'Luxury market'} GC markup typically runs {rec_gc}. "
            f"This template allocates {gc_pct:.0f}%."
        )

    # Missing line items
    missing = []
    if is_luxury or is_high_col:
        missing.append("Interior Designer — not in template; luxury projects typically budget $50k–$150k+")
    if is_high_col:
        missing.append("Permit Expediter — required for complex filings in high-COL municipalities; budget $10k–$25k")
    if is_atypical or is_loft:
        missing.append("MEP Engineer — often required for loft conversions and atypical structures; budget $15k–$30k")
    if is_loft:
        missing.append("Acoustic Consultant — common for open-plan loft projects; budget $5k–$15k")
    if missing:
        lines.append("• Missing line items not covered by this template:")
        for m in missing:
            lines.append(f"    - {m}")

    # Permit exposure
    if is_high_col and permit_item:
        permit_amt = total_budget * permit_item["pct_of_total_budget"] / 100
        lines.append(
            f"• Permits (${permit_amt:,.0f}): In high cost-of-living cities, permit fees + "
            f"expediter for a project this size typically run ${total_budget * 0.04:,.0f}–${total_budget * 0.06:,.0f}."
        )

    # Contingency
    if contingency_item and (is_atypical or is_loft or is_large):
        cont_pct = contingency_item["pct_of_total_budget"]
        rec_cont = "12–15%" if (is_atypical or is_loft) else "10–12%"
        reason = "atypical structures like lofts with unknown hidden conditions" if (is_atypical or is_loft) else "large complex projects"
        lines.append(
            f"• Contingency ({cont_pct:.0f}% / ${total_budget * cont_pct / 100:,.0f}): "
            f"For {reason}, {rec_cont} is recommended."
        )

    logger.debug(f"💰 Budget commentary generated ({len(lines)} lines) for signals: {signals}")
    return "\n".join(lines)


def template_already_applied(project_data: dict) -> bool:
    """
    Return True if a budget template has already been seeded for this project.

    Checks whether any item in financial_data.estimates[] has
    source == "budget_template". Used as a guard to prevent double-seeding
    when the user sends a second budget-keyword message.

    Called by:
        - agents/nodes/shared_nodes.py (budget_skill_node)
        - agents/graphs/onboarding_graph.py (store_onboarding_data)

    Args:
        project_data (dict): The project.data JSONB dict.

    Returns:
        bool: True if at least one template-sourced estimate already exists.
    """
    estimates = (
        project_data
        .get("financial_data", {})
        .get("estimates", [])
    )
    return any(item.get("source") == "budget_template" for item in estimates)
