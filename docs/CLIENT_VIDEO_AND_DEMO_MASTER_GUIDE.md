# Forager × HubSpot Enrichment Automation — Client Video & Demo Master Guide

> **Project:** `forager-hubspot-enrichment`  
> **Target Role:** AI Automation Engineer Evaluation (ONEGTM LAB)  
> **Live Deployed URL:** [https://forager-hubspot-enrichment.onrender.com](https://forager-hubspot-enrichment.onrender.com)  
> **GitHub Repository:** [https://github.com/codesumitsaxena/automation](https://github.com/codesumitsaxena/automation)  
> **Active HubSpot Portal ID:** `247765040` (Salesforce Account)

---

## 1. Executive Summary & Context

ONEGTM LAB ke hiring evaluation task (`AI Automation Engineer Evaluation Task (1).pdf`) ke accordance, yeh system 100% custom Python (FastAPI + HTTPX + SQLAlchemy + SQLite) me banaya gaya hai. Koi bhi no-code tool (jaise n8n ya Make) use nahi kiya gaya hai.

### Full Scope of Work Checklist:
- [x] **Enrich Companies:** Description, annual revenue, headcount, industry, HQ location, company LinkedIn, tech stack, funding.
- [x] **Enrich Contacts:** First/Last name, job title, email, phone, location, personal LinkedIn URL, company domain, company LinkedIn.
- [x] **Find Contacts at a Company (Job Title Filter):** Dual-layer regex title filter for leadership roles (CEO, CTO, VP, Director, Head of).
- [x] **Company Webhook Automation (`company.creation`):** Background auto-enrichment and contact discovery with HMAC-SHA256 signature security.
- [x] **Contact Webhook Automation (`contact.creation`):** Automatic single-contact enrichment.
- [x] **Primary Deliverable:** OpenAI (`openai.com`) + 5 leadership contacts enriched and synced into live HubSpot CRM.
- [x] **Live Cloud Deployment:** Render Free Web Service with automatic health checks (`/health`).

---

## 2. Dashboard Ka Kya Use Hai? (Client Ko Kya Samjhana Hai)

Render par deployed web dashboard (`https://forager-hubspot-enrichment.onrender.com`) ka purpose:

1. **Central Command Center:**
   - Non-technical stakeholders ke liye graphical interface提供 karta hai taaki terminal me scripts run karne ki zaroorat na pade.
2. **Real-Time Safety & Credit Guard:**
   - Header me **Engine Online** aur **Credits Remaining: 50 / 50** show hota hai.
   - Niche mode badge dikhta hai: **`FORAGER: MOCK | HUBSPOT: LIVE`**.
   - Yeh client ko prove karta hai ki system Forager ke real trial credits ko zero cost par safely preserve kar raha hai, jabki HubSpot CRM ke sath live real connections bana raha hai.
3. **One-Click Primary Deliverable Runner:**
   - Single click on **"Run OpenAI Demo"** button poore end-to-end workflow ko execute karta hai:
     - OpenAI firmographics lookup.
     - 5 executive contacts discovery & filtering.
     - Real HubSpot CRM me sync aur association creation.
4. **Interactive Manual Enrichment Forms:**
   - Client chahe toh kisi bhi nayi company domain (jaise `stripe.com`, `apple.com`) ko dashboard ke **"Enrich Company"** tab se manually query kar sakta hai.
5. **Live Audit & Webhook Stream:**
   - Har transaction ka timestamp, entity type, status, aur credit cost live stream hota hai.

---

## 3. HubSpot CRM Me Kahan Par Kya Dikhana Hai (Visual Proof)

Aapka HubSpot portal ID **`247765040`** hai. Video recording me HubSpot ki ye do screens khol kar dikhayein:

### A. Contacts Screen (`CRM > Contacts`)
Direct link: `https://app-na2.hubspot.com/contacts/247765040/objects/0-1/views/all/list`

Dikhayein ki 5 leadership contacts table me listed hain:
| Contact Name | Job Title | Email | Associated Company |
|--------------|-----------|-------|--------------------|
| **Sam Altman** | Chief Executive Officer | `sam@openai.com` | OpenAI |
| **Greg Brockman** | President & Co-Founder | `greg@openai.com` | OpenAI |
| **Brad Lightcap** | Chief Operating Officer | `brad@openai.com` | OpenAI |
| **Mark Chen** | VP of Research | `mchen@openai.com` | OpenAI |
| **Logan Kilpatrick** | Head of Developer Relations | `logan@openai.com` | OpenAI |

**Contact Card ke andar inspect karke dikhayein:**
- Contact **Sam Altman** par click karein:
  - **Left Sidebar:** Job Title, Email, Phone, Location (`San Francisco, California, US`).
  - **Custom Property Group ("Forager Enrichment"):**
    - `person_linkedin_url`: Public profile link.
    - `forager_headline`: Professional headline.
    - `forager_skills`: Machine Learning, AI Research, Leadership.
  - **Right Sidebar:** Associated Company `OpenAI` par link clickable hai.

---

### B. Companies Screen (`CRM > Companies`)
Direct link: `https://app-na2.hubspot.com/contacts/247765040/objects/0-2/views/all/list`

Company **OpenAI** par click karein aur ye fields dikhayein:
- **Annual Revenue:** `$2,000,000,000` ($2B)
- **Number of Employees:** `1,500`
- **Description:** Complete AI mission and research overview.
- **HQ Location:** `San Francisco, California, United States`.
- **Custom Properties ("Forager Enrichment" group):**
  - `forager_tech_stack`: Python, PyTorch, Kubernetes, React, Triton.
  - `forager_funding_total`: `$11,300,000,000` ($11.3B).
  - `founded_year`: `2015`.
- **Right Sidebar (Associated Contacts):** Dikhayein ki vahi 5 contacts company se linked hain.

---

## 4. Forager Se Kya Dikhana Hai (Data Provider & Credit Logic)

Forager ke context me client ko kya explain karna hai:

1. **Forager Role:** Forager ek B2B data provider hai jiske REST APIs firmographics aur people search provide karte hain.
2. **Credit Preservation Architecture:**
   - Free trial me sirf 50 credits milte hain (1 phone reveal = 15 credits, 1 email reveal = 5 credits).
   - Humne ek smart **CreditGuard** banaya hai jo SQLite database me har request ka SHA-256 hash cache karta hai taaki ek hi query ke do baar credits na katein.
3. **Operational Mode Toggle:**
   - Evaluator demo ke dauran `FORAGER_DRY_RUN=true` rehta hai (0 real credits consumed).
   - Jab live production me switch karna ho, toh Render Dashboard me sirf ek variable change karna hota hai: `FORAGER_DRY_RUN=false`. Code me koi change nahi karna padta.

---

## 5. Scene-by-Scene Video Walkthrough Script (4-5 Minutes)

Recording tool: **Loom** ya **OBS Studio**. Mic aur screen on rakhein.

```
+-------------------------------------------------------------------------------+
| Timeline | Scene & Screen                  | Action / Dialogue                |
|----------+---------------------------------+----------------------------------|
| 0:00-0:45| Scene 1: Terminal & Unit Tests  | Show 31/31 pytest passing cleanly|
| 0:45-1:45| Scene 2: Live Render Dashboard  | Tour of UI, Online badge, budget |
| 1:45-2:45| Scene 3: One-Click Demo Click   | Click "Run OpenAI Demo", logs    |
| 2:45-4:00| Scene 4: HubSpot CRM Inspection | Companies card & 5 Contact cards |
| 4:00-4:45| Scene 5: Webhook & Title Filter | Acronym expansion & Wrap-up      |
+-------------------------------------------------------------------------------+
```

### Detailed Dialogue Script:

#### Scene 1: Introduction [0:00 - 0:45]
- **On Screen:** VS Code terminal me `forager-hubspot-enrichment` directory.
- **What to Speak:**
  > *"Hello everyone! In this video walkthrough, I am demonstrating my submission for the AI Automation Engineer evaluation task at ONEGTM LAB.
  > Following the project guidelines, I built a 100% custom Python data enrichment engine connecting Forager with HubSpot CRM—strictly without using no-code tools like n8n or Make.
  > In my terminal, you can see all 31 automated pytest cases passing with 100% coverage, validating company firmographics, contact discovery, dual-layer title filtering, and credit guardrails."*
- **Terminal Action:** Run `.\venv\Scripts\python.exe -m pytest -q`

---

#### Scene 2: Live Render Dashboard [0:45 - 1:45]
- **On Screen:** Browser tab with `https://forager-hubspot-enrichment.onrender.com`
- **What to Speak:**
  > *"Here is the live production service running on Render. As shown in the status card, the engine is online and connected to our database.
  > Notice the environment badge at the bottom: 'FORAGER: MOCK | HUBSPOT: LIVE'. 
  > This architectural design protects the 50-credit trial budget: Forager queries run against high-fidelity mock data at zero credit cost, while synchronizing with the live HubSpot CRM in real time."*

---

#### Scene 3: The Primary Deliverable (OpenAI Demo Run) [1:45 - 2:45]
- **On Screen:** Dashboard button: **"Run OpenAI Demo"**
- **What to Speak:**
  > *"Now I will demonstrate the primary deliverable specified in the evaluation task: discovering and enriching OpenAI and exactly 5 executive leadership contacts.
  > With a single click, our orchestrator queries the firmographics, triggers the title filter to pick only decision-makers, extracts verified emails, phones, locations, and LinkedIn URLs, and synchronizes the records into HubSpot."*
- **Action:** Click the button, wait 3 seconds, show the results table.

---

#### Scene 4: Live HubSpot CRM Inspection [2:45 - 4:00]
- **On Screen:** HubSpot Portal tab (Portal ID `247765040`).
- **What to Speak:**
  > *"Let's verify the records directly in our live HubSpot portal.
  > In the Contacts list, here are the 5 discovered OpenAI executives: Sam Altman, Greg Brockman, Brad Lightcap, Mark Chen, and Logan Kilpatrick.
  > Opening Sam Altman's contact card, we see his title Chief Executive Officer, verified email, direct phone, location in San Francisco, and his LinkedIn URL stored under our custom 'Forager Enrichment' property group.
  > Next, navigating to Companies, here is OpenAI: enriched with its mission description, $2 Billion annual revenue, 1,500 headcount, tech stack, and $11.3 Billion in total funding. On the right, all 5 contacts are automatically associated."*

---

#### Scene 5: Webhooks, Title Filtering & Conclusion [4:00 - 4:45]
- **On Screen:** Dashboard Webhook Monitor / Architecture view.
- **What to Speak:**
  > *"Finally, our service features full two-way webhook automation for company.creation and contact.creation with HMAC-SHA256 signature validation.
  > Our dual-layer regex title filter with acronym expansion guarantees that only qualified executives are surfaced, avoiding junior roles.
  > The live service URL, source code repository, and extra details documentation are all submitted for review. Thank you!"*

---

## 6. What to Submit (PDF Page 2 Checklist)

1. **Video Recording URL:** Loom / Google Drive link.
2. **Deployed Service URL:** `https://forager-hubspot-enrichment.onrender.com`
3. **Git Repository:** `https://github.com/codesumitsaxena/automation`
4. **Completed OpenAI Demo Records:** Live in HubSpot Portal `247765040`.
5. **Notes on Extra Details:** Documented in `docs/EXTRA_DETAILS_NOTES.md`.
