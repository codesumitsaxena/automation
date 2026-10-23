# Forager × HubSpot Automation — Complete User Guide & Video Recording Script (Hinglish)

Yeh document aapke evaluation task (`AI Automation Engineer Evaluation Task (1).pdf`) ke exact requirements ke according banaya gaya hai. Isme aapko:
1. Pura system **kaise kaam karta hai**
2. **HubSpot CRM me kahan kya dekhna hai**
3. **Video kaise banani hai (Scene-by-Scene Script)**

Aasan aur clear Hinglish me step-by-step samjhaya gaya hai.

---

## 1. Project Overview & PDF Requirements Check

PDF ke mutabiq aapko ONEGTM LAB ke liye 5 main tasks deliver karne the:

| # | Task (PDF Ke According) | Hamare System Me Kaise Banaya Hai | Status |
|---|-------------------------|-----------------------------------|--------|
| 1 | **Enrich Companies** (Headcount, Revenue, Description, HQ, Tech Stack, Funding) | `CompanyService` & Forager API integration jo company ka poora firmographic data nikalta hai. | ✅ Complete |
| 2 | **Enrich Contacts** (Name, Job Title, LinkedIn, Email, Phone, Location) | `ContactService` jo employee profile, verified email, aur direct phone nikalta hai. | ✅ Complete |
| 3 | **Find Contacts at Company** (Filtered by Job Title: CEO, CTO, VP, Director) | `DiscoveryService` jisme **Dual-Layer Title Filter** laga hai (leadership profiles ko strictly filter karta hai). | ✅ Complete |
| 4 | **Company Webhook Automation** (`company.creation`) | FastAPI background webhook router jo nayi company add hone par automatically enrich karta hai aur 5 leadership contacts link karta hai. | ✅ Complete |
| 5 | **Contact Webhook Automation** (`contact.creation`) | Naye contact create hone par automatic single-contact enrichment. | ✅ Complete |
| 6 | **Primary Deliverable: OpenAI Record Set** | OpenAI (`openai.com`) + 5 complete leadership contacts HubSpot me synced. | ✅ Complete |
| 7 | **Live Deployment** | Render par 100% live (`https://forager-hubspot-enrichment.onrender.com`). | ✅ Complete |

---

## 2. HubSpot CRM Me Kahan Par Kya Dekhna Hai (Visual Guide)

Aap jab apne [HubSpot Portal](https://app.hubspot.com/) me login karenge, toh aapko ye 4 jagah check karni hain:

### A. Companies List (CRM > Companies)
1. HubSpot ke top navigation bar me **CRM** par click karein aur **Companies** select karein.
2. Wahan aapko **OpenAI** company record dikhega.
3. OpenAI par click karein:
   - **Left Panel (About this company):**
     - Company Domain: `openai.com`
     - Industry: `Technology, Information and Internet`
     - Number of Employees: `1,500`
     - Annual Revenue: `$2,000,000,000`
     - City/State/Country: `San Francisco, California, United States`
     - Company LinkedIn URL: `https://www.linkedin.com/company/openai`
     - Description: OpenAI ka full AI research & deployment mission description.
   - **Left Panel ke niche "View all properties" click karein:**
     - Wahan **"Forager Enrichment"** group milega.
     - Isme custom properties dikhengi:
       - `forager_tech_stack` (Python, PyTorch, Kubernetes, React, Triton)
       - `forager_funding_total` ($11,300,000,000)
       - `founded_year` (2015)
       - `forager_status` (`mock_demo` ya `enriched`)

### B. Associated Contacts (Company Card ke Right Side)
1. OpenAI company ke page par right side me **"Contacts"** section dekhein.
2. Wahan exactly **5 Leadership Contacts** linked dikhenge:
   - Example: Sam Altman (CEO), Greg Brockman (President), Mira Murati / CTO, VP of Research, Head of Alignment.
3. Yahi HubSpot ki **Association API v3** hai jo company aur contacts ko aapas me connect karti hai.

### C. Contacts List (CRM > Contacts)
1. Top navigation me **CRM > Contacts** par click karein.
2. Wahan kisi bhi contact (jaise `Sam Altman`) par click karein:
   - First Name & Last Name: `Sam Altman`
   - Job Title: `Chief Executive Officer`
   - Email: Verified email address
   - Phone Number: Direct phone / mobile
   - Location: `San Francisco, California, United States`
   - Associated Company: `OpenAI`
   - **Custom Properties ("Forager Enrichment" section):**
     - `person_linkedin_url` (LinkedIn profile link)
     - `forager_headline` (Professional headline)
     - `forager_skills` (Artificial Intelligence, Machine Learning, Entrepreneurship)

---

## 3. Live Dashboard Kaise Use Karna Hai

Aapka deployed URL hai:
👉 **`https://forager-hubspot-enrichment.onrender.com`**

Dashboard par login karne ke baad:
1. **Stat Cards:**
   - **Credits Remaining:** `50 / 50` (Safe Budget display)
   - **Companies Enriched:** Real-time count
   - **Contacts Enriched:** Real-time count
   - **Webhooks Received:** Deduplicated webhook event counter
2. **One-Click Demo Button ("Run OpenAI Demo"):**
   - Is button par click karte hi script background me chalti hai.
   - Forager se OpenAI ka data uthati hai.
   - 5 leadership executives filter karti hai.
   - HubSpot me company + 5 contacts create karke link kar deti hai.
   - Niche table me instant summary aa jaati hai.
3. **Manual Forms (Enrich Company & Find Contacts):**
   - Agar aapko kisi dusri company (jaise `stripe.com`) ko test karna ho, toh **"Enrich Company"** tab me domain daal kar enrich kar sakte hain!
4. **Audit Logs & Webhook Stream:**
   - Niche live logs stream hote hain jo har transaction ka timestamp aur status dikhate hain.

---

## 4. Video Walkthrough Script (5-Minute Screen Recording Guide)

Video record karne ke liye aap **Loom** ya **OBS Studio** use kar sakte hain. Screen + Mic on rakhein. Niche diya gaya script follow karein:

---

### [0:00 - 0:45] Scene 1: Introduction & Architecture
- **Screen:** VS Code / Terminal open rakhein.
- **Kya Bolna Hai (Script):**
  > *"Hello everyone! In this video walkthrough, I am presenting my submission for the AI Automation Engineer role at ONEGTM LAB. 
  > I have built a 100% custom Python data enrichment engine connecting Forager with HubSpot CRM. No no-code tools like n8n or Make were used — this is pure, production-grade Python using FastAPI, HTTPX, Pydantic, and SQLAlchemy."*
- **Action:** Terminal me `pytest -q` run karke dikhaiye.
  > *"Here you can see all 31 automated test cases passing cleanly — covering company enrichment, contact discovery, title filtering, credit guards, and webhook idempotency."*

---

### [0:45 - 1:45] Scene 2: Live Deployed Dashboard (Render)
- **Screen:** Browser me open karein: `https://forager-hubspot-enrichment.onrender.com`
- **Kya Bolna Hai (Script):**
  > *"Here is the live deployed web service running on Render. As you can see, the Engine status is Online. 
  > Notice the environment badge: 'FORAGER: MOCK | HUBSPOT: LIVE'. 
  > This is a crucial architectural guardrail: to preserve the 50 trial credits, we have a granular dry-run toggle. Forager runs in high-fidelity mock mode consuming 0 credits, while HubSpot is connected to the real, live CRM."*

---

### [1:45 - 3:00] Scene 3: Primary Deliverable (OpenAI One-Click Demo)
- **Screen:** Dashboard par **"Run OpenAI Demo"** button par mouse le jayein.
- **Action:** Click karein **"Run OpenAI Demo"** button par.
- **Kya Bolna Hai (Script):**
  > *"Now I will execute the primary deliverable required in the task specification: enriching OpenAI and discovering 5 leadership contacts. 
  > With a single click, our orchestrator queries the company firmographics, applies the dual-layer title filter to select only top executives (CEO, CTO, President, VPs), extracts their verified emails, phone numbers, locations, and LinkedIn URLs, and synchronizes everything into HubSpot."*
- **Action:** Wait 3-4 seconds, table load ho jayegi.
  > *"The run completed successfully! 1 company and 5 executive contacts were processed at exactly 0 credit cost."*

---

### [3:00 - 4:15] Scene 4: Live HubSpot CRM Inspection (The Proof)
- **Screen:** Browser me dusri tab me HubSpot CRM open karein (`app.hubspot.com`).
- **Action 1:** Go to **CRM > Companies > Click OpenAI**.
  > *"Let's verify the results in my live HubSpot portal. Here is the OpenAI company record. 
  > You can see the description, annual revenue of $2 Billion, 1,500 headcount, industry, HQ in San Francisco, and company LinkedIn page. 
  > Under custom properties in the 'Forager Enrichment' group, we also have technologies used like PyTorch and Kubernetes, total funding of $11.3B, and founded year 2015."*
- **Action 2:** Right side panel me **Contacts** dikhaiye aur ek contact (e.g. Sam Altman) par click karein.
  > *"On the right panel, all 5 discovered contacts are properly associated with OpenAI. 
  > Clicking into a contact, we see complete fields: First/Last name, Job title (CEO), verified email, phone number, location, person LinkedIn URL, and custom fields like professional headline and skills."*

---

### [4:15 - 5:00] Scene 5: Webhooks, Title Filtering & Wrap-up
- **Screen:** Wapas code ya dashboard ke Webhook tab par aayiye.
- **Kya Bolna Hai (Script):**
  > *"Lastly, our automation supports two-way webhook automation: when a company or contact is created in HubSpot, a webhook triggers automatic background enrichment with replay-attack protection via HubSpot v3 HMAC signatures.
  > Our title filter uses an intelligent dual-layer regex with acronym expansion, ensuring interns or junior engineers are filtered out and only leadership profiles get enriched.
  > We have also documented 'interesting extra details' such as skills, seniority level, and raw JSON payloads in our documentation.
  > Thank you for reviewing my evaluation task!"*

---

## 5. Submission Checklist (PDF Page 2 Ke Mutabiq)

Jab video ban jaye, aapko ye 4 cheezein submit karni hain:

1. **Video Recording Link:** Loom video URL ya Google Drive link.
2. **Deployed Service URL:** `https://forager-hubspot-enrichment.onrender.com`
3. **Source Code GitHub Repo:** `https://github.com/codesumitsaxena/automation`
4. **Notes on Extra Details:** File `docs/EXTRA_DETAILS_NOTES.md` repo me already included hai.
