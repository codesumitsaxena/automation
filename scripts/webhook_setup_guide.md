# HubSpot Webhook Setup Guide

This guide explains how to configure HubSpot webhooks to automatically trigger company and contact enrichment whenever a new record is created in HubSpot CRM.

---

## Method 1: HubSpot Developer App (Recommended)

This is the standard, production-grade approach supported on free developer test portals and production accounts. It provides an official `Client Secret` for **v3 HMAC SHA-256 signature validation**.

### Step 1: Create a Developer App
1. Log in to your [HubSpot Developer Account](https://app.hubspot.com/developer/).
2. Click **Manage apps** > **Create app**.
3. Set your App name to `Forager Enrichment Engine`.

### Step 2: Configure Scopes
Navigate to the **Auth** tab and add the following required scopes:
- `crm.objects.companies.read`
- `crm.objects.companies.write`
- `crm.objects.contacts.read`
- `crm.objects.contacts.write`
- `crm.schemas.companies.write`
- `crm.schemas.contacts.write`

### Step 3: Copy Your Client Secret
Under the **Auth** tab, find **App Credentials**:
- Copy the **Client Secret** (UUID format).
- Paste it into your `.env` file as:
  ```env
  HUBSPOT_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  VERIFY_WEBHOOK_SIGNATURE=true
  ```

### Step 4: Configure Webhook Subscriptions
1. In your app settings, click the **Webhooks** tab.
2. In the **Target URL** field, enter your public endpoint:
   ```text
   https://your-app-name.up.railway.app/webhooks/hubspot
   ```
   *(For local testing with ngrok: `https://xxxx.ngrok-free.app/webhooks/hubspot`)*
3. Click **Create subscription**:
   - Event type: **Company** > Select **Created** (`company.creation`).
   - Event type: **Contact** > Select **Created** (`contact.creation`).
4. Click **Save**.

---

## Method 2: Testing Webhooks Locally (Without HubSpot Account)

Our application includes a built-in mock testing facility so you can test and record webhooks instantly without needing public tunnels.

Ensure `VERIFY_WEBHOOK_SIGNATURE=false` in your `.env` file, start the local server, and send this cURL command:

```bash
curl -X POST "http://localhost:8000/webhooks/hubspot" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "eventId": 1001,
      "subscriptionType": "company.creation",
      "objectId": "comp_openai_test",
      "portalId": 12345
    }
  ]'
```

### Expected Response:
```json
{
  "status": "success",
  "events_received": 1,
  "events_accepted": 1,
  "duplicates_ignored": 0
}
```

The system will automatically log the event in `webhook_events`, enrich the company in the background, discover 5 executive contacts, and associate them with the company record.

If you run the exact same cURL command a second time, you will observe the deduplication protection:
```json
{
  "status": "success",
  "events_received": 1,
  "events_accepted": 0,
  "duplicates_ignored": 1
}
```
