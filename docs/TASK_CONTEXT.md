# TASK CONTEXT: Forager x HubSpot Enrichment Automation

## 1. Project Overview & Objective
- **Project Name:** `forager-hubspot-enrichment`
- **Role:** AI Automation Engineer Evaluation Task (ONEGTM LAB)
- **Objective:** Build, deploy, and demo a production-grade, custom Python backend automation connecting **Forager** (B2B data enrichment platform) with **HubSpot CRM**, end-to-end.
- **Rule:** 100% custom Python code only (FastAPI, httpx, pydantic, sqlite). No-code/workflow tools (n8n, Make, Zapier) are strictly disallowed.

---

## 2. Full Scope of Work

| # | Task | Description |
|---|------|-------------|
| 1 | **Enrich Companies** | Pull full company details (description, annual revenue, headcount/employees, industry, founded year, HQ location, company LinkedIn URL, website, phone, funding, tech stack). |
| 2 | **Enrich Contacts** | Fill in all required contact fields (names, job title, person LinkedIn URL, employer name, domain, employer LinkedIn URL, work/personal email, phone, city, state, country). |
| 3 | **Find Contacts at a Company** | Discover new employee profiles at a company, strictly filtered and controlled by **Job Title** (e.g., CEO, CTO, VP, Head of, Director). |
| 4 | **Company Webhook Automation** | When a new company is added to HubSpot, a webhook fires and the automation enriches that company. If its contacts already exist in HubSpot, they get enriched; if they don't exist, we discover them via Forager (up to a configured limit), create them in HubSpot, and associate them with the company. |
| 5 | **Contact Webhook Automation** | When a new contact is added to HubSpot, a webhook fires and the automation enriches that contact (by email, LinkedIn URL, or name + company). |

---

## 3. Required Fields Specification

### Enriched Contact Fields
- **First & Last Name** (`firstname`, `lastname`)
- **Person LinkedIn URL** (`person_linkedin_url` custom property / `hs_linkedin_url`)
- **Job Title** (`jobtitle`)
- **Company Name** (`company`)
- **Company Domain** (`company_domain` custom property)
- **Company LinkedIn URL** (`company_linkedin_url` custom property)
- **Email** (`email` - verified work email or personal email)
- **Phone** (`phone` / `mobilephone`)
- **Location**: City (`city`), State/Region (`state`), Country (`country`)
- **Nice-to-Have Extra Details (Flagged for Discussion in `docs/EXTRA_DETAILS_NOTES.md`):**
  - Person Headline (`forager_headline`)
  - "About" / Summary section (`forager_about`)
  - Professional Skills (`forager_skills`)
  - Seniority Level (`forager_seniority`)
  - Status & Enrichment Timestamp (`forager_status`, `forager_enriched_at`)

### Enriched Company Fields
- **Company Name** (`name`)
- **Domain** (`domain`)
- **Website URL** (`website`)
- **Description** (`description`)
- **Headcount / Employees** (`numberofemployees`)
- **Annual Revenue** (`annualrevenue`)
- **Industry** (`industry`)
- **Company LinkedIn URL** (`linkedin_company_page`)
- **Founded Year** (`founded_year` / custom property)
- **Phone Number** (`phone`)
- **HQ Location**: City (`city`), State/Region (`state`), Country (`country`)
- **Technologies / Tech Stack** (`forager_tech_stack` custom property)
- **Total Funding Raised** (`forager_funding_total` custom property)

---

## 4. Primary Deliverable: OpenAI Demo Record Set

Reviewers will evaluate the system primarily by inspecting the completed record set in HubSpot:
1. **Target Company:** OpenAI (`openai.com`).
2. **Contacts:** Exactly **5 employees** discovered and enriched under OpenAI.
3. **Completeness:** Each contact must have email, phone, city, state, country, LinkedIn URL, job title, and employer association.
4. **Data Integrity:** Clean, complete, and demo-ready records. If a contact in live search lacks verified email or phone, the automation gracefully skips to the next qualified candidate matching the title criteria to ensure 100% complete records without faking data.

---

## 5. Critical Constraints & Architectural Guardrails

### A. Forager API & Extreme Credit Preservation
- **Account Budget:** 50 credits total on the trial account.
- **Credit Costs:**
  - Company firmographics lookup: ~1 credit
  - Person search / discovery: ~1 credit
  - Person profile detail lookup: ~1 credit
  - Work email reveal: ~5 credits
  - Mobile phone reveal: ~15 credits
  - *Note:* Revealing 5 phone numbers alone would cost 75 credits (exceeding the 50 credit limit).
- **Credit Protection Design:**
  1. `DRY_RUN=true` mode: Default mode! Uses realistic mock responses (`mocks/`) for OpenAI and 5 executives. Consumes 0 real credits.
  2. **SQLite Cache:** Every real Forager request/response is cached indefinitely by SHA-256 hash of the request parameters. The exact same lookup is never paid for twice.
  3. `CreditGuard` service: Enforces `MAX_CREDITS_PER_RUN` (default: 30) and tracks cumulative usage in the database.
  4. Pre-run credit cost estimation: Prints expected credit expenditure in terminal and requires confirmation before any live paid call.
  5. `ENABLE_EMAIL_PHONE_REVEAL`: Boolean flag controlling whether high-cost email (5 credits) and phone (15 credits) reveals are triggered.
  6. **Zero Guessing Rule:** All API paths, request shapes, and response parsers reside in a single mapping module (`app/clients/forager_client.py` and `app/services/mapper.py`).

### B. HubSpot Webhook Integration & Reality Check
- **Webhook Subscriptions:**
  - Standard Approach: HubSpot Developer App (free developer portal) subscribing to `contact.creation` and `company.creation`.
  - Fallback Approach 1: HubSpot Private App with Webhook subscriptions (where supported in current UI).
  - Fallback Approach 2: Polling endpoint (`POST /api/sync/poll-new-records`) that checks for newly created records lacking `forager_status`.
- **Security:**
  - Full **HubSpot v3 Signature Validation** (`X-HubSpot-Signature-v3` HMAC SHA-256 with timestamp replay attack prevention).
  - Configurable toggle `VERIFY_WEBHOOK_SIGNATURE=false` for local offline/mock testing.
- **Idempotency & Infinite Loop Prevention:**
  - Custom property `forager_status` (`enriched`, `discovered`, `pending`) and `forager_enriched_at`.
  - SQLite `enrichment_cache` and `webhook_events` tracking table keyed by `eventId`.
  - Immediate HTTP 200 response to HubSpot, dispatching enrichment to FastAPI `BackgroundTasks`.
  - When discovery creates contacts in HubSpot, it sets `forager_status='discovered'` to prevent contact-creation webhook loops.
  - Safe updates: Non-destructive field mapping (only overwrite when Forager returns non-empty values).

---

## 6. What Will Be Submitted
1. **Video Demo:** Walkthrough showing enrichment running, webhook firing, records in HubSpot, and job-title filtering.
2. **Deployed Service URL & Git Repo:** Live URL (Railway) and public/clean GitHub repository.
3. **OpenAI Demo Records:** Live enriched company & 5 associated contacts visible in HubSpot CRM.
4. **Extra Details Notes:** `docs/EXTRA_DETAILS_NOTES.md` outlining rich Forager fields for discussion.
