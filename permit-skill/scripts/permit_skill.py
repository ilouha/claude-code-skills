"""
Permit Skill Helper — pure functions for permit requirement identification.

Provides helpers for:
- Loading the permit type definitions (skills/permit-skill/assets/permit-types.json)
- Loading the keyword trigger config (skills/permit-skill/assets/permit-skill-config.json)
- Detecting permit-related keywords in user text
- Extracting the jurisdiction from an address or free-text message
- Building a full permit summary (AHJ, permits required, next steps) for a given
  scope of work and jurisdiction

No DB access, no LangGraph state management. Purely functional so each
piece is independently testable.

Called by:
    - agents/helpers/permit_skill.py (bridge module re-exports everything here)
    - agents/nodes/shared_nodes.py (permit_skill_node — email & chat graphs)
    - agents/graphs/onboarding_graph.py (permit check during NUX)

Update History:
    - 2026-02-18: Initial creation for permit-skill feature
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
_PERMIT_TYPES_PATH = _CONFIG_DIR / "permit-types.json"
_SKILL_CONFIG_PATH = _CONFIG_DIR / "permit-skill-config.json"

# ---------------------------------------------------------------------------
# Scope normalization — maps free-text scope to canonical keys
# ---------------------------------------------------------------------------
SCOPE_ALIASES: dict[str, str] = {
    "kitchen": "kitchen",
    "kitchen remodel": "kitchen",
    "kitchen renovation": "kitchen",
    "bathroom": "bathroom",
    "bath": "bathroom",
    "bathroom remodel": "bathroom",
    "whole house": "whole_house",
    "whole_house": "whole_house",
    "gut renovation": "whole_house",
    "gut rehab": "whole_house",
    "full rehab": "whole_house",
    "full renovation": "whole_house",
    "new construction": "new_construction",
    "new_construction": "new_construction",
    "ground up": "new_construction",
    "ground-up": "new_construction",
    "new build": "new_construction",
    "addition": "addition",
    "room addition": "addition",
    "home addition": "addition",
    "adu": "adu",
    "accessory dwelling unit": "adu",
    "granny flat": "adu",
    "garage conversion": "adu",
}


# ---------------------------------------------------------------------------
# Loaders (cached so files are read once per process lifetime)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_permit_types() -> dict:
    """
    Load and cache the permit type definitions from JSON.

    Returns:
        dict: Full permit types mapping. Empty dict on file/parse error.
    """
    try:
        with open(_PERMIT_TYPES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"🏛️ Loaded permit types: {list(data.get('jurisdictions', {}).keys())}")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load permit-types.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_permit_skill_config() -> dict:
    """
    Load and cache the permit skill keyword trigger config from JSON.

    Returns:
        dict: Config dict. Returns {"trigger_keywords": []} on error.
    """
    try:
        with open(_SKILL_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"🏛️ Loaded permit skill config: {len(data.get('trigger_keywords', []))} keywords")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load permit-skill-config.json: {e}")
        return {"trigger_keywords": []}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def detect_permit_keywords(text: str) -> bool:
    """
    Return True if any permit trigger keyword is found in text.

    Performs case-insensitive substring matching. A single match is enough
    to return True. Returns False on empty text or empty keyword list.

    Args:
        text (str): The email body or chat input to scan.

    Returns:
        bool: True if at least one trigger keyword matched.
    """
    if not text:
        return False
    lower_text = text.lower()
    keywords = load_permit_skill_config().get("trigger_keywords", [])
    for kw in keywords:
        if kw.lower() in lower_text:
            logger.debug(f"🏛️ Permit keyword matched: '{kw}'")
            return True
    return False


def extract_jurisdiction(address_or_text: str) -> str:
    """
    Attempt to identify the jurisdiction key from an address or free-text message.

    Scans the text against known address keywords from permit-types.json.
    Returns "generic" if no jurisdiction can be identified.

    Args:
        address_or_text (str): Full address or any text containing location info.

    Returns:
        str: Jurisdiction key (e.g. "los_angeles_city", "new_york_city", "generic").
    """
    if not address_or_text:
        return "generic"

    lower = address_or_text.lower()
    data = load_permit_types()
    address_keywords = data.get("address_keywords", {})

    for keyword, jurisdiction_key in address_keywords.items():
        if keyword in lower:
            logger.debug(f"🏛️ Jurisdiction matched: '{keyword}' → '{jurisdiction_key}'")
            return jurisdiction_key

    logger.debug("🏛️ No jurisdiction matched — defaulting to 'generic'")
    return "generic"


def normalize_scope(scope_or_text: str) -> str:
    """
    Normalize a free-text scope description to a canonical scope key.

    Checks both SCOPE_ALIASES and substring matching. Falls back to
    "new_construction" if nothing matches.

    Args:
        scope_or_text (str): Scope string like "kitchen remodel", "ground up", etc.

    Returns:
        str: Canonical scope key.
    """
    lower = scope_or_text.lower().strip()

    # Direct alias lookup
    if lower in SCOPE_ALIASES:
        return SCOPE_ALIASES[lower]

    # Substring match
    for alias, canonical in SCOPE_ALIASES.items():
        if alias in lower:
            return canonical

    logger.debug(f"🏛️ Scope '{scope_or_text}' not matched — defaulting to 'new_construction'")
    return "new_construction"


def get_permit_requirements(scope_of_work: str, jurisdiction_key: str) -> dict | None:
    """
    Return the permit requirements dict for a given scope and jurisdiction.

    Looks up the jurisdiction in permit-types.json, then finds the matching
    scope entry. Falls back to the "generic" jurisdiction if the specific
    jurisdiction does not have an entry for the given scope.

    Args:
        scope_of_work (str): Canonical scope key (e.g. "kitchen", "new_construction").
        jurisdiction_key (str): Jurisdiction key (e.g. "los_angeles_city").

    Returns:
        dict | None: Requirements dict with keys: permits_required, typical_timeline,
            typical_fees, next_steps. None on failure.
    """
    data = load_permit_types()
    jurisdictions = data.get("jurisdictions", {})

    # Try specific jurisdiction first, fall back to generic
    for jkey in [jurisdiction_key, "generic"]:
        jurisdiction = jurisdictions.get(jkey, {})
        scopes = jurisdiction.get("scopes", {})
        if scope_of_work in scopes:
            if jkey == "generic" and jkey != jurisdiction_key:
                logger.warning(
                    f"🏛️ Scope '{scope_of_work}' not found in '{jurisdiction_key}' — "
                    f"falling back to generic"
                )
            return scopes[scope_of_work]

    logger.warning(f"🏛️ No permit requirements found for scope='{scope_of_work}' in any jurisdiction")
    return None


def build_permit_summary(
    scope_of_work: str,
    address_or_text: str,
    total_budget: float = 0.0,
) -> dict:
    """
    Build a complete permit summary for a project.

    Identifies the jurisdiction from the address, looks up the AHJ and permit
    requirements for the given scope, and returns a structured summary dict
    ready for display or storage.

    Args:
        scope_of_work (str): Free-text or canonical scope (e.g. "ground up", "kitchen").
        address_or_text (str): Project address or any text containing location info.
        total_budget (float): Total project budget in dollars (used for fee estimates).

    Returns:
        dict: {
            "jurisdiction_key":   str,
            "jurisdiction_name":  str,
            "ahj":                str,
            "website":            str | None,
            "portal":             str | None,
            "phone":              str,
            "notes":              str,
            "scope":              str,
            "permits_required":   list[dict],
            "typical_timeline":   str,
            "typical_fees":       str,
            "estimated_fee_range": str | None,
            "next_steps":         list[str],
        }
    """
    scope = normalize_scope(scope_of_work)
    jurisdiction_key = extract_jurisdiction(address_or_text)

    data = load_permit_types()
    jurisdictions = data.get("jurisdictions", {})

    # Use the matched jurisdiction, or generic
    jdata = jurisdictions.get(jurisdiction_key) or jurisdictions.get("generic", {})
    requirements = get_permit_requirements(scope, jurisdiction_key) or {}

    # Estimate fee range if budget provided
    estimated_fee_range = None
    if total_budget > 0 and requirements:
        fee_str = requirements.get("typical_fees", "")
        # Parse percentage range if present (e.g. "1–2%")
        import re
        pct_match = re.search(r"([\d.]+)[–-]([\d.]+)%", fee_str)
        if pct_match:
            lo_pct = float(pct_match.group(1)) / 100
            hi_pct = float(pct_match.group(2)) / 100
            estimated_fee_range = (
                f"${total_budget * lo_pct:,.0f} – ${total_budget * hi_pct:,.0f} "
                f"(based on ${total_budget:,.0f} budget)"
            )

    summary = {
        "jurisdiction_key":       jurisdiction_key,
        "jurisdiction_name":      jdata.get("name", "Unknown"),
        "ahj":                    jdata.get("ahj", "Unknown"),
        "website":                jdata.get("website"),
        "portal":                 jdata.get("portal"),
        "permit_center_url":      jdata.get("permit_center_url"),
        "phone":                  jdata.get("phone", "Contact local building department"),
        "notes":                  jdata.get("notes", ""),
        "submittal_requirements": jdata.get("submittal_requirements", []),
        "scope":                  scope,
        "permits_required":       requirements.get("permits_required", []),
        "typical_timeline":       requirements.get("typical_timeline", "Unknown"),
        "typical_fees":           requirements.get("typical_fees", "Unknown"),
        "estimated_fee_range":    estimated_fee_range,
        "next_steps":             requirements.get("next_steps", []),
    }

    logger.debug(
        f"🏛️ Permit summary built: jurisdiction='{jurisdiction_key}' scope='{scope}' "
        f"permits={len(summary['permits_required'])}"
    )
    return summary


def format_permit_summary(summary: dict) -> str:
    """
    Format a permit summary dict into a human-readable text block.

    Args:
        summary (dict): Output from build_permit_summary().

    Returns:
        str: Formatted multi-line permit summary.
    """
    lines = [
        "PERMIT REQUIREMENTS SUMMARY",
        "=" * 50,
        "",
        f"Jurisdiction:      {summary['jurisdiction_name']}",
        f"AHJ:               {summary['ahj']}",
        f"Phone:             {summary['phone']}",
        f"Website:           {summary['website'] or 'N/A'}",
        f"Permit Center:     {summary['permit_center_url'] or 'N/A'}",
        "",
    ]

    if summary.get("notes"):
        lines += [f"Note: {summary['notes']}", ""]

    if summary.get("submittal_requirements"):
        lines += ["SUBMITTAL REQUIREMENTS", "-" * 40]
        for i, req in enumerate(summary["submittal_requirements"], 1):
            lines.append(f"{i}. {req}")
        lines.append("")

    lines += ["PERMITS REQUIRED", "-" * 40]
    for i, permit in enumerate(summary["permits_required"], 1):
        lines.append(f"{i}. {permit['type']}")
        lines.append(f"   Authority: {permit['authority']}")
        if permit.get("notes"):
            lines.append(f"   Note: {permit['notes']}")
        lines.append("")

    lines += [
        "TIMELINE & FEES",
        "-" * 40,
        f"Typical Timeline: {summary['typical_timeline']}",
        f"Typical Fees:     {summary['typical_fees']}",
    ]
    if summary.get("estimated_fee_range"):
        lines.append(f"Est. Fee Range:   {summary['estimated_fee_range']}")

    lines += ["", "NEXT STEPS", "-" * 40]
    for i, step in enumerate(summary["next_steps"], 1):
        lines.append(f"{i}. {step}")

    return "\n".join(lines)
