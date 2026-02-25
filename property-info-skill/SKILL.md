---
name: property-info-skill
description: >
  Look up property records from county/city assessor databases given a street address.
  Returns structured property info including lot area, building area, legal description,
  and a direct link to the assessor record. Use this skill whenever the user provides a
  property address and wants assessor data, parcel info, lot size, square footage, zoning,
  legal description, or a link to public property records. Also trigger when the user says
  things like "look up this property", "what's the lot size of...", "find the assessor
  record for...", "property details for...", or "pull up the parcel info". This skill
  covers major US jurisdictions and learns new ones over time.
---

# Property Records Lookup

This skill retrieves public property assessment data for a given US street address by
querying official county and city assessor portals. It returns a structured summary and
a direct link to the official record.

## CRITICAL RULE: Official Sources Only

**NEVER use third-party property websites.** This includes but is not limited to:
- PropertyShark, Zillow, Redfin, Realtor.com, Homes.com, Trulia
- Regrid, ATTOM, CountyOffice.org, PropertyRadar
- Any real estate brokerage or aggregator site

**ONLY use these source types:**
- Official county/city assessor portals (e.g., `portal.assessor.lacounty.gov`)
- Official assessor REST APIs (e.g., `portal.assessor.lacounty.gov/api/...`)
- Official county GIS/map tools (e.g., `maps.assessor.lacounty.gov`)
- Official open data portals (e.g., `data.lacounty.gov`)
- Official property tax portals (e.g., `propertytax.lacounty.gov`)

If the only results from a web search are third-party sites, **do not use them**. Instead,
navigate directly to the official assessor portal for that jurisdiction.

## Workflow

### 1. Parse the Address

Extract these components from the user's input:
- **Street number and name**
- **City**
- **State**
- **ZIP code** (if provided)

If the address is ambiguous or incomplete (e.g. missing city/state), ask the user to
clarify before proceeding. If only a city and state are given without a street address,
let the user know you need a specific property address.

### 2. Identify the Jurisdiction

Determine which county or assessment authority covers the address. Use this priority:

1. Check `references/assessor_sources.json` for a matching jurisdiction (by county or
   city name in `cities_served`).
2. If no match, use web search to identify the county for the given city/state, then
   check again.
3. If still no match in the reference file, search the web for
   `"[county name] county assessor property search"` (restrict to `.gov` domains) to
   find the correct official portal.

### 3. Search the Assessor Portal

**CRITICAL: Always check the reference file's `search_method` and `api` fields first.**
Many jurisdictions have direct API endpoints that return structured JSON — these are
far more reliable than web scraping.

#### Priority A: Direct API (preferred)

If the jurisdiction entry in `assessor_sources.json` has an `"api"` block:

1. **Step 1 — Search:** `web_fetch` the `api.search_endpoint` URL, substituting the
   street address into the `{address}` placeholder.
2. **Step 2 — Match:** Parse the JSON response. The first result in the `Parcels` array
   is typically the correct match. Verify the `SitusStreet` contains the expected address.
3. **Step 3 — Detail:** Extract the parcel ID (e.g., `AIN`) from the matched result,
   then `web_fetch` the `api.detail_endpoint` URL with that ID.
4. **Step 4 — Extract:** Parse the detail JSON using the `field_mappings` to populate
   the output table.

**Example (LA County):**
```
Search:  web_fetch https://portal.assessor.lacounty.gov/api/search?search=1161+Hartzell+St
Result:  {"TotalCount":446,"Parcels":[{"AIN":"4423005017","SitusStreet":"1161 HARTZELL ST",...}]}
Detail:  web_fetch https://portal.assessor.lacounty.gov/api/parceldetail?ain=4423005017
Result:  Full property record with lot size, year built, assessed values, zoning, etc.
```

#### Priority B: Web Fetch (assessor portal page)

If the reference file includes a `search_url` but no API:

1. Try `web_fetch` on the assessor's property search URL if it supports query-string
   lookups.
2. Parse the HTML response for property data fields.

**Note:** Many assessor portals are JavaScript-heavy (Angular, React) and will NOT
return data via simple web_fetch. If the response is empty/framework-only, fall back
to Priority C.

#### Priority C: Official Web Search (last resort)

If neither API nor direct fetch works:

1. Use `web_search` with a query targeting ONLY the official assessor domain:
   `site:[assessor-domain] "[street number] [street name]"`
2. If that fails, broaden slightly:
   `"[full address]" [county] assessor parcel site:.gov`
3. Fetch the most promising official result with `web_fetch` to extract data.

**NEVER broaden the search to include non-official sites.**

### Field Reference

When extracting data, look for these fields (not all will be available in every
jurisdiction):

| Field | Common Labels |
|---|---|
| **Parcel Number / APN** | Parcel ID, APN, AIN, PIN, Tax Map ID |
| **Lot Area** | Lot Size, Land Area, Parcel Size |
| **Building Area** | Living Area, Gross Area, Main Building Sq Ft |
| **Legal Description** | Legal Desc, Legal, Subdivision + Lot + Block |
| **Property Use / Zoning** | Use Code, Zoning, Property Class |
| **Year Built** | Year Built, Effective Year |
| **Assessed Value** | Land Value, Improvement Value, Total Assessed |
| **Owner Name** | Owner, Taxpayer (include only if clearly public record) |
| **Lot Dimensions** | Lot Width, Lot Depth |
| **Bedrooms / Bathrooms** | Bedrooms, Bathrooms |

### 4. Present Results

Always present results as a **structured summary table** in this format:

```
## Property Summary: [Address]

| Field | Value |
|---|---|
| **Parcel / APN** | [value or "Not found"] |
| **Lot Area** | [value, include units] |
| **Lot Dimensions** | [width x depth, if available] |
| **Building Area** | [value, include units] |
| **Bedrooms / Baths** | [value, if available] |
| **Legal Description** | [value or "Not available"] |
| **Year Built** | [value] |
| **Zoning / Use** | [value] |
| **Assessed Value** | [breakdown: Land + Improvements = Total] |

**Source:** [Jurisdiction Name] Assessor
**Direct Link:** [URL to the property record page]
```

If a field isn't available from the source, show "Not available" rather than omitting
it — the user should see what was and wasn't found. Add a brief note below the table
if anything is unusual (e.g., the parcel has multiple addresses, the record seems
outdated, Misfortune & Calamity designation, etc.).

### 5. Update the Reference File (Silent Auto-Update)

After every successful lookup, check whether the jurisdiction is already well-represented
in `references/assessor_sources.json`. If you used a new assessor portal, or discovered
a better search URL, API endpoint, or new field mappings, **update the reference file
automatically**:

1. Read the current `references/assessor_sources.json`
2. Add or update the jurisdiction entry with:
   - The working assessor base URL and API endpoints
   - The search URL pattern or API endpoint (if discoverable)
   - Field mappings you observed (which JSON keys/HTML labels map to standard fields)
   - Any new cities to add to `cities_served`
   - The date you last verified the source works
3. Write the updated file back

This is silent — don't mention the update to the user unless they ask about it. The
goal is for the reference file to grow organically so future lookups in the same
jurisdiction are faster and more reliable.

**Priority for discovery:** When encountering a new jurisdiction, actively look for
REST API endpoints behind JavaScript-heavy portals. Check browser-style API paths
like `/api/search`, `/api/parcel`, `/api/property`, etc. These are far more reliable
than trying to scrape rendered HTML.

## Important Notes

- **Official sources only.** NEVER use third-party property data sites. All data must
  come from official government assessor portals, APIs, or open data endpoints.
- **Public records only.** Do not scrape gated or login-required content.
- **Data freshness.** Assessor data can lag. If the record shows a "last updated" date,
  include it. Otherwise note that assessor data may not reflect very recent changes.
- **Multiple results.** If the search returns multiple parcels for the same address
  (common with condos or subdivisions), present the top match and note that others exist.
- **Fallback.** If you truly cannot find the assessor record after reasonable effort,
  tell the user what you tried, suggest they search the assessor portal directly (provide
  the URL), and still update the reference file with whatever you learned about that
  jurisdiction's portal.

## Implementation Files

```
skills/property-info-skill/
├── SKILL.md                              <- this file
└── references/
    └── assessor_sources.json             <- assessor portal URLs, API endpoints, and field mappings by jurisdiction
```
