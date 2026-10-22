# Forager API: Interesting Extra Details Flagged for Discussion

**Project:** `forager-hubspot-enrichment`  
**Author:** AI Automation Engineer  
**Context:** ONEGTM LAB Hiring Evaluation Task  

---

## 1. Executive Summary & Context

During our deep inspection of the Forager.ai API payload specifications (specifically `person_detail_lookup`, `person_role_search`, and `organization_search`), we identified a wealth of high-value metadata returned by Forager beyond the bare-minimum required fields (Name, Email, Phone, Location, Domain).

Per engineering instructions, these extra fields have been **flagged for architectural discussion** rather than silently decided or merged into standard fields. They are currently captured in dedicated custom properties in the `Forager Enrichment` property group so reviewers can evaluate their business utility and CRM footprint.

---

## 2. Contact Extra Fields

| Field Name | Forager Source Path | HubSpot Custom Property | Description | Value & Discussion Point |
|---|---|---|---|---|
| **Professional Headline** | `headline` | `forager_headline` | Full LinkedIn professional headline (e.g., *"CEO at OpenAI \| Former President at Y Combinator"*). | **High Value for SDRs.** Much more descriptive than simple title. Immediately gives sales reps personalized talking points without opening LinkedIn. |
| **Profile "About" Summary** | `about` or `summary` | `forager_about` | The narrative summary written by the person on their professional profile. | **High Value for AI Messaging.** Excellent for LLM prompt context to draft hyper-personalized cold outreach emails. Requires textarea property type. |
| **Skills & Expertise** | `skills` (Array of strings) | `forager_skills` | Normalized list of professional competencies (e.g. `["Deep Learning", "Distributed Systems"]`). | **Medium Value.** Useful for lead routing (e.g., routing technical buyers to sales engineers). Stored as a comma-separated string. |
| **Seniority Level** | `seniority` | `forager_seniority` | Normalized tier: `c_level`, `vp`, `director`, `manager`, `senior`, `entry`. | **High Value for CRM Filtering.** Allows HubSpot list segmentation by seniority without relying on brittle regex on title strings. |
| **Forager Source ID** | `id` or `person_id` | `forager_source_id` | Forager's internal entity identifier. | **Engineering Provenance.** Enables direct reverse-caching and idempotency lookups without re-running search algorithms. |

---

## 3. Company Extra Fields

| Field Name | Forager Source Path | HubSpot Custom Property | Description | Value & Discussion Point |
|---|---|---|---|---|
| **Tech Stack** | `technologies` (Array of strings) | `forager_tech_stack` | Detected software, cloud providers, and libraries (e.g., Python, Kubernetes, React, Azure). | **Extremely High Value for B2B Tech Sales.** Enables technographic ICP qualification (e.g., only prospect companies using Azure or Python). |
| **Total Funding Raised** | `funding.total_funding_usd` | `forager_funding_total` | Cumulative venture capital raised formatted in USD. | **Financial Health Indicator.** Helps determine enterprise spending capacity and deal sizing. |
| **Latest Funding Round** | `funding.latest_round` | `forager_latest_funding_round` | Series A, B, C, Secondary Market, Debt, etc. | **Growth Signal.** Recent funding rounds correlate strongly with active purchasing cycles. |
| **Secondary Domains** | `domains` (Array) | `forager_alternative_domains` | Aliases and associated domains (e.g. `chatgpt.com` alongside `openai.com`). | **Prevents Duplicate Companies.** Ensures leads from sub-brands map to the same parent company. |

---

## 4. Engineering Trade-Offs & Discussion Questions

### Question 1: Textarea vs. Standard Text Limits in HubSpot
* **Issue:** HubSpot single-line text properties are limited to 65,536 characters, but UI tables only render the first ~100 characters cleanly.
* **Our Implementation:** We mapped narrative text (`about`, `tech_stack`) into textarea properties, and summary identifiers into single-line text properties.

### Question 2: Should Skills Be a Multi-Checkbox Property or Delimited String?
* **Issue:** HubSpot multi-checkbox fields require predefined enumeration options upfront. Forager returns arbitrary skills.
* **Our Recommendation:** Store as a comma-delimited string in CRM for inspection, but keep a normalized tag list in local SQLite for structured querying.

### Question 3: Technographic Refresh Frequency
* **Issue:** Technologies evolve. Firmographics (headcount, revenue) change quarterly.
* **Our Implementation:** We stamped `forager_enriched_at` on every company and contact. We propose a 90-day stale policy before re-enriching existing records.
