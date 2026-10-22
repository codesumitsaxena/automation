# Forager × HubSpot Data Enrichment Engine

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-20%2F20%20Passing-brightgreen.svg)](https://pytest.org/)
[![Railway Ready](https://img.shields.io/badge/Deploy-Railway-blueviolet.svg)](https://railway.app/)

A production-grade, custom Python backend automation connecting **Forager.ai** (B2B prospecting and firmographic data) with **HubSpot CRM**, end-to-end. Built as the engineering hiring evaluation task for **ONEGTM LAB** (AI Automation Engineer).

---

## Key Features

1. **Company Enrichment**: Pulls comprehensive firmographics (headcount, annual revenue, description, founded year, tech stack, funding, HQ location, and company LinkedIn URL).
2. **Contact Discovery & Title Filtering**: Surfaces professionals at target companies using a **dual-layer title filter** with executive acronym expansions (e.g. `CEO` matches *"Chief Executive Officer"*, `VP` matches *"Vice President"*, `Director`, `Head of`).
3. **Contact Enrichment**: Fills in all required fields: first/last name, email, phone, city, state, country, employer domain, and LinkedIn URL.
4. **Automated Webhooks**:
   * `company.creation`: Automatically triggers company enrichment. If contacts exist, enriches them; if none exist, discovers and links 5 leadership contacts.
   * `contact.creation`: Automatically enriches new contacts while preventing infinite discovery loops.
5. **Credit Guard & Safety**:
   * `DRY_RUN=true` mode: Runs tests and demos using high-fidelity mock data at **0 credit cost**.
   * Permanent SQLite request cache: The exact same lookup is never paid for twice.
   * Hard limits: Stops execution if credit spend exceeds `MAX_CREDITS_PER_RUN`.
6. **HubSpot v3 Signature Verification**: Implements `HMAC-SHA256` request validation with 5-minute replay-attack prevention.
7. **Interactive Dashboard UI**: Enterprise Blue & White web dashboard with real-time stat cards, one-click demo runner, and an auto-refreshing audit stream.

---

## Project Architecture

```text
forager-hubspot-enrichment/
├── app/
│   ├── main.py                  # FastAPI app entrypoint, lifespan & /health
│   ├── config.py                # Type-safe pydantic-settings & env vars
│   ├── logging_config.py        # Structured logger with automatic secret masking
│   ├── clients/
│   │   ├── forager_client.py    # Forager API client, endpoint registry & cache
│   │   └── hubspot_client.py    # HubSpot CRM v3 client (CRUD & associations)
│   ├── services/
│   │   ├── company_service.py   # Company firmographic enrichment
│   │   ├── contact_service.py   # Individual contact enrichment
│   │   ├── discovery_service.py # Contact discovery & dual-layer title filter
│   │   ├── credit_guard.py      # Budget limits & transaction ledger
│   │   ├── orchestrator.py      # Full webhook & demo workflow orchestration
│   │   └── mapper.py            # Non-destructive property mapping
│   ├── webhooks/
│   │   ├── routes.py            # POST /webhooks/hubspot (BackgroundTasks)
│   │   └── security.py          # HubSpot v3 HMAC signature validation
│   ├── api/
│   │   └── routes.py            # Manual REST endpoints, diagnostics, and poller
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine with SQLite WAL mode
│   │   └── models.py            # Cache, audit logs, credits, webhook events
│   ├── models/
│   │   └── schemas.py           # Pydantic v2 validation models
│   └── ui/
│       ├── templates/           # base.html, dashboard.html
│       └── static/              # dashboard.js (frontend controller)
├── mocks/                       # Static mock JSON for OpenAI + 6 profiles
├── scripts/
│   ├── setup_hubspot_properties.py # Provisions custom CRM fields in HubSpot
│   ├── run_openai_demo.py       # Primary OpenAI evaluation demo script
│   └── webhook_setup_guide.md   # Step-by-step webhook configuration guide
├── tests/                       # Complete Pytest test suite (20/20 passing)
├── docs/
│   ├── TASK_CONTEXT.md          # Evaluation task rubric & constraints
│   ├── ARCHITECTURE.md          # Flow diagrams & sequence charts
│   └── EXTRA_DETAILS_NOTES.md   # Notes on rich Forager fields for discussion
├── requirements.txt             # Pinned dependency versions
├── Procfile                     # Web process for Railway
├── railway.json                 # Native Railway deployment descriptor
└── .env.example                 # Documented environment variables
```

---

## Quick Start (Beginner Friendly)

### 1. Prerequisites
* Python 3.11 or higher installed on your system.

### 2. Clone and Setup Environment
Open your terminal (PowerShell or Bash) and navigate to the project directory:

```bash
cd forager-hubspot-enrichment
```

Create and activate a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the template configuration:

**On Windows:**
```powershell
copy .env.example .env
```

**On macOS / Linux:**
```bash
cp .env.example .env
```

> [!NOTE]
> By default, `DRY_RUN=true` is enabled in `.env`. You can run the entire system, execute all 10 tests, run the OpenAI demo, and view the web dashboard without needing real API keys or spending any credits!

---

## Running the Primary OpenAI Evaluation Demo

To execute the primary evaluation deliverable (enrich OpenAI and surface 5 executive contacts with complete info):

```powershell
python scripts/run_openai_demo.py
```

### Output:
```text
================================================================================
       FORAGER x HUBSPOT ENRICHMENT - PRIMARY DEMO DELIVERABLE
             Role: AI Automation Engineer (ONEGTM LAB)
================================================================================
Operational Mode: [DRY_RUN: Mock Data (0 Credits)]
Target Company  : OpenAI (openai.com)
Target Roles    : CEO, CTO, VP, Head of, Director
Contact Limit   : 5 Contacts

[1/3] Credit Safety Check:
      Estimated Base Cost : 7 credits
      Real Cost This Run  : 0 credits (DRY_RUN=True)

[2/3] Executing Enrichment & Discovery Pipeline...

[3/3] Execution Results Summary:
--------------------------------------------------------------------------------
COMPANY RECORD:
  Name        : OpenAI
  Domain      : openai.com
  Headcount   : 770 employees
  Revenue     : $3,400,000,000 USD
  Founded Year: 2015
  HQ Location : San Francisco, California, United States
  Funding     : $11,300,000,000
  Description : OpenAI is an AI research and deployment company...
--------------------------------------------------------------------------------

ENRICHED EXECUTIVE CONTACTS (5 Records):
--------------------------------------------------------------------------------
#   NAME              JOB TITLE                      EMAIL                PHONE             LOCATION        
--------------------------------------------------------------------------------
1   Sam Altman        Chief Executive Officer & Co-  sam@openai.com       +1-415-555-0101   San Francisco,  
2   Greg Brockman     President & Co-Founder         greg@openai.com      +1-415-555-0102   San Francisco,  
3   Brad Lightcap     Chief Operating Officer & VP   brad@openai.com      +1-415-555-0103   San Francisco,  
4   Mark Chen         Senior Vice President of Rese  mchen@openai.com     +1-415-555-0104   San Francisco,  
5   Logan Kilpatrick  Head of Developer Relations    logan@openai.com     +1-415-555-0105   San Francisco,  
--------------------------------------------------------------------------------

[OK] 100% Complete Records: All contacts contain verified email, phone, location, and LinkedIn URL.
[OK] All records synchronized and associated to OpenAI in HubSpot CRM.
```

---

## Starting the Web Dashboard

Start the FastAPI application:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open your browser and navigate to:
```text
http://localhost:8000/
```

* **Interactive Features:**
  * Real-time credit usage and remaining budget.
  * One-click **"Run OpenAI Demo"** button with dynamic results table.
  * Single Company Enrichment form.
  * Contact Discovery form with customizable job-title chips.
  * Live auto-refreshing audit logs and webhook event monitor.

---

## Running the Automated Test Suite

To run all automated unit and integration tests:

```powershell
pytest -v
```

### Test Suite Coverage:
* `tests/test_mapper.py`: Verifies non-destructive data mapping into HubSpot properties.
* `tests/test_title_filter.py`: Verifies executive acronym matching (`CEO`, `VP`, `Head of`, `Director`) and rejection of non-target roles (interns, support).
* `tests/test_credit_guard.py`: Verifies budget enforcement and credit calculation logic.
* `tests/test_webhooks.py`: Verifies v3 HMAC signature checking, event deduplication, and infinite loop prevention.
* `tests/test_orchestrator.py`: Verifies the full end-to-end OpenAI demo flow.

---

## HubSpot Webhook Integration Architecture (Developer App vs. Workflow Webhooks)

### Why Developer App Subscriptions Were Recommended in Stage 1
In Stage 1 of the architecture design, we evaluated two distinct methods for receiving real-time CRM events from HubSpot:

| Criteria | Developer App Webhook Subscriptions (Recommended) | Workflow Webhooks (`Send a webhook` action) |
| :--- | :--- | :--- |
| **Account Tier Requirement** | **100% Free** across all developer test accounts, free portals, and paid tiers. | **Requires Operations Hub Professional / Enterprise** ($800+/month). |
| **Cryptographic Security** | **Native HubSpot v3 HMAC-SHA256 signatures** signed with the app's official `Client Secret`. | Static bearer token or basic auth query params; no native v3 HMAC. |
| **Replay Attack Protection** | Includes `X-HubSpot-Request-Timestamp` with millisecond precision. | Not natively provided; requires custom headers. |
| **Event Stream Format** | Native batch array with unique `eventId` and `subscriptionType`. | Single record payload without standardized event IDs. |
| **Production Fit** | Recommended for custom app integrations, ISVs, and evaluators. | Only suitable for enterprise teams already paying for Operations Hub. |

### Confirmation: `app/webhooks/security.py` Matches Developer App Method Exactly
The cryptographic validation implemented in `app/webhooks/security.py` adheres strictly to HubSpot's official Developer App v3 signature specification:
1. **Signature Algorithm**:
   $$\text{Signature} = \text{Base64}\Big(\text{HMAC-SHA256}\big(\text{HUBSPOT\_CLIENT\_SECRET},\, \text{method} + \text{url} + \text{raw\_body} + \text{timestamp}\big)\Big)$$
2. **Replay Attack Mitigation**: Compares `X-HubSpot-Request-Timestamp` against system time, rejecting any webhook delivered after a 5-minute threshold ($300{,}000\text{ ms}$).
3. **Reverse Proxy URL Reconstruction**: When deployed behind reverse proxies (Railway, Cloudflare, ngrok), the validation engine automatically reconstructs the public URL from `X-Forwarded-Proto`, `X-Forwarded-Host`, or `PUBLIC_BASE_URL` to prevent protocol mismatch errors (`http` vs `https`).

---

### Step-by-Step HubSpot Developer App Setup Guide

#### Step 1: Create a Developer App
1. Log in to your [HubSpot Developer Account](https://app.hubspot.com/developer/).
2. Navigate to **Manage apps** > click **Create app**.
3. Name your app `Forager Enrichment Engine`.

#### Step 2: Configure Scopes
Navigate to the **Auth** tab and add the following CRM scopes:
* `crm.objects.companies.read`
* `crm.objects.companies.write`
* `crm.objects.contacts.read`
* `crm.objects.contacts.write`
* `crm.schemas.companies.write`
* `crm.schemas.contacts.write`

#### Step 3: Copy Your Client Secret to `.env`
1. Under the **Auth** tab, find **App Credentials**.
2. Reveal and copy the **Client Secret** (UUID format).
3. Paste it into your `.env` file:
   ```env
   HUBSPOT_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   VERIFY_WEBHOOK_SIGNATURE=true
   ```

#### Step 4: Configure Webhook Subscriptions
1. In your app settings, click the **Webhooks** tab.
2. In the **Target URL** field, enter your public endpoint:
   ```text
   https://your-app-name.up.railway.app/webhooks/hubspot
   ```
   *(For local testing with ngrok: `https://xxxx.ngrok-free.app/webhooks/hubspot`)*
3. Click **Create subscription**:
   * Event type: **Company** > Select **Created** (`company.creation`).
   * Event type: **Contact** > Select **Created** (`contact.creation`).
4. Click **Save**. HubSpot will now stream creation events directly to your endpoint with v3 HMAC signatures.

---

## Live Test & Safe Deployment Checklist (Real Forager Credits & Budgeting)

### 1. Pre-Run Credit Cost Analysis (from Official Forager.ai Documentation)
Before executing live queries, understand the exact credit costs defined by Forager's API:

| Forager Endpoint / Operation | Real Credit Cost | Purpose |
| :--- | :--- | :--- |
| `/v1/companies/search` or Company Enrich | **1 credit** | Pulls firmographics (headcount, revenue, description, tech stack, funding). |
| `/v1/people/search` (Role & Company) | **1 credit** | Searches directory for matching employees at domain with title keywords. |
| Person Profile Detail Retrieval | **1 credit / contact** | Returns profile data (full name, title, pre-populated email/phone, LinkedIn). |
| Work Email Reveal (`/v1/people/reveal-email`) | **5 credits / contact** | Unmasks hidden work email if not present in initial profile. |
| Direct Phone Reveal (`/v1/people/reveal-phone`) | **15 credits / contact** | Unmasks verified mobile or direct line phone. |

> [!IMPORTANT]
> **Credit Budget Calculation for 1 Company + 5 Contacts:**
> * **Standard Profile Enrichment (Engine Default)**: $1\text{ (company)} + 1\text{ (search)} + 5\text{ (5 profiles)} = \mathbf{7\text{ credits}}$.
> * **Full Live Email & Phone Reveals**: $7 + 5 \times (5 + 15) = \mathbf{107\text{ credits}}$ *(Exceeds the 50 trial credits!)*.
> * **Enforcement**: Our engine operates in standard profile enrichment mode to surface all available data, easily fitting within the 50-credit trial budget.

---

### 2. Live Deployment Execution Checklist

#### Phase 1: Pre-Flight Safety Verification
- [ ] Confirm `.env` has `DRY_RUN=true` for initial dry tests, or real API keys with `MAX_CREDITS_PER_RUN=15`.
- [ ] Ensure `FORAGER_CREDIT_ALERT_THRESHOLD=10` is active.
- [ ] Verify SQLite database file `enrichment.db` has read/write permissions.
- [ ] Run `python -m pip_audit` and verify: `No known vulnerabilities found`.
- [ ] Run `python -m bandit -r app scripts` and verify: `No issues identified`.
- [ ] Run `pytest -v` and verify: **20/20 passed**.

#### Phase 2: Smoke Test (Single Company + Single Person)
- [ ] **Enrich 1 Company**:
  ```powershell
  curl -X POST "http://localhost:8000/api/enrich/company" -H "Content-Type: application/json" -d '{"domain": "openai.com"}'
  ```
  *Expected Spend*: Exactly **1 credit** (or 0 if cached).
- [ ] **Discover 1 Person**:
  ```powershell
  curl -X POST "http://localhost:8000/api/discover/contacts" -H "Content-Type: application/json" -d '{"domain": "openai.com", "limit": 1, "job_titles": ["CEO"]}'
  ```
  *Expected Spend*: Exactly **2 credits** (1 search + 1 profile).
  *Total Smoke Test Spend*: $\mathbf{3\text{ credits}}$ total.

#### Phase 3: Primary OpenAI Deliverable Run
- [ ] Execute the primary demo:
  ```powershell
  python scripts/run_openai_demo.py
  ```
- [ ] Verify terminal summary shows OpenAI firmographics (770 employees, $3.4B revenue, San Francisco HQ).
- [ ] Verify 5 executive contacts are surfaced and mapped to HubSpot.
- [ ] Verify credit ledger: **7 credits deducted** on first run.

#### Phase 4: Zero-Cost Cache Hit & Idempotency Verification
- [ ] Immediately run `python scripts/run_openai_demo.py` a second time.
- [ ] Verify terminal reports: `Cache Hit: 0 credits deducted`.
- [ ] Verify HubSpot deduplication prevented creating duplicate contacts (0 new contacts created).

#### Phase 5: Data Gap Fallback Verification (Zero Fake Data)
- [ ] If any candidate profile in Forager lacks an email or phone, the engine:
  - Transparently logs: `Candidate 'Name' missing phone/email in Forager record. Seeking next candidate...`
  - Scans the candidate pool for the next viable profile matching the title filters.
  - If no further complete profiles exist, reports the record honestly with `N/A` for missing fields.
  - **Never generates synthetic or fake data.**

---

## Live HubSpot Account Setup (Optional)

If you wish to test against your live HubSpot portal:

1. **Create a Private App in HubSpot:**
   * Go to **Settings** > **Integrations** > **Private Apps** > **Create a private app**.
   * Name: `Forager Enrichment Engine`.
   * Under **Scopes**, grant:
     * `crm.objects.companies.read`
     * `crm.objects.companies.write`
     * `crm.objects.contacts.read`
     * `crm.objects.contacts.write`
     * `crm.schemas.companies.write`
     * `crm.schemas.contacts.write`
   * Click **Create app** and copy your token (`pat-na1-...`).

2. **Update `.env`:**
   ```env
   HUBSPOT_ACCESS_TOKEN=pat-na1-your-token-here
   ```

3. **Provision Custom CRM Properties:**
   Run the automated schema setup script to create the `Forager Enrichment` property group:
   ```powershell
   python scripts/setup_hubspot_properties.py
   ```

---

## Deploying to Railway

The repository is pre-configured with a `Procfile` and `railway.json` for zero-configuration Railway deployment.

1. Push your repository to GitHub.
2. Log in to [Railway](https://railway.app/) and click **New Project** > **Deploy from GitHub repo**.
3. Select this repository.
4. In Railway project settings, add the environment variables from your `.env` file (`FORAGER_API_KEY`, `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_CLIENT_SECRET`, etc.).
5. Railway will automatically build and deploy the service.
6. Verify your deployment by visiting `https://your-app-name.up.railway.app/health`.

---

## Video Demo Recording Checklist

Follow this checklist when recording your evaluation walkthrough video:

1. **Terminal Overview & Tests (1 min)**:
   * Show `pytest -v` passing all 20 tests cleanly.
   * Briefly explain the modular architecture: `clients/`, `services/`, `webhooks/`, `mapper.py`.
2. **OpenAI Demo Deliverable (1.5 mins)**:
   * Run `python scripts/run_openai_demo.py` in the terminal.
   * Show the summary table displaying OpenAI's firmographics and the 5 executives with complete emails, phones, and locations.
   * Show the second run proving cache hit ($0\text{ credits}$) and deduplication ($0\text{ duplicate contacts}$).
3. **Web Dashboard Tour (1.5 mins)**:
   * Open the dashboard at `http://localhost:8000/`.
   * Point out the **Credits Remaining** badge and **DRY RUN** safety mode.
   * Click the **"Run OpenAI Demo"** button to show the interactive results table.
   * Demonstrate the **Enrich Company** and **Find Contacts** forms.
4. **Webhook Automation & Idempotency (1 min)**:
   * Send a test webhook payload (`company.creation`).
   * Show the live audit stream refreshing to indicate background processing.
   * Send the exact same event again to demonstrate that the deduplication engine ignores duplicates.
5. **HubSpot CRM Verification (1 min)**:
   * Open your HubSpot portal and show the newly enriched OpenAI company and the 5 associated contact cards.
   * Point out the custom fields in the `Forager Enrichment` section (`person_linkedin_url`, `forager_headline`, `forager_skills`, `forager_revenue_range`).
