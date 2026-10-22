/**
 * Forager x HubSpot Enrichment Automation - Frontend Controller
 */

function getHeaders() {
    return {
        "Content-Type": "application/json",
    };
}


function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function sanitizeUrl(url) {
    if (!url) return "#";
    const clean = String(url).trim();
    if (/^https?:\/\//i.test(clean)) {
        return escapeHtml(clean);
    }
    return "#";
}

// -----------------------------------------------------------------------------
// Toast Notifications
// -----------------------------------------------------------------------------
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    const bgColors = {
        success: "bg-emerald-600 text-white",
        error: "bg-rose-600 text-white",
        info: "bg-brand-600 text-white",
        warning: "bg-amber-600 text-white",
    };

    toast.className = `px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition transform duration-300 translate-y-2 opacity-0 pointer-events-auto flex items-center space-x-2 ${bgColors[type] || bgColors.info}`;
    
    const span = document.createElement("span");
    span.textContent = message;
    toast.appendChild(span);

    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);

    // Dismiss
    setTimeout(() => {
        toast.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// -----------------------------------------------------------------------------
// Status Badge Helpers
// -----------------------------------------------------------------------------
function getStatusBadge(status) {
    const raw = (status || "").toUpperCase();
    const safe = escapeHtml(raw);
    if (raw === "SUCCESS" || raw === "PROCESSED") {
        return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">SUCCESS</span>`;
    }
    if (raw === "DISCOVERED") {
        return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-100 text-indigo-800">DISCOVERED</span>`;
    }
    if (raw === "SKIPPED" || raw === "IGNORED") {
        return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">${safe}</span>`;
    }
    return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800">${safe || 'ERROR'}</span>`;
}

// -----------------------------------------------------------------------------
// Primary Deliverable: Run OpenAI Demo
// -----------------------------------------------------------------------------
async function runOpenAiDemo() {
    const btn = document.getElementById("btn-run-demo");
    const spinner = document.getElementById("demo-spinner");
    const resultsCard = document.getElementById("demo-results-card");

    try {
        btn.disabled = true;
        spinner.classList.remove("hidden");
        showToast("Running OpenAI enrichment and contact discovery...", "info");

        const res = await fetch("/api/demo/openai", {
            method: "POST",
            headers: getHeaders(),
        });
        const data = await res.json();

        if (data.success && data.data) {
            showToast("OpenAI + 5 Contacts enriched and synchronized to HubSpot!", "success");
            renderDemoResults(data.data);
            refreshStats();
        } else {
            showToast("Failed to run demo: " + (data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Network error executing demo: " + e.message, "error");
    } finally {
        btn.disabled = false;
        spinner.classList.add("hidden");
    }
}

function renderDemoResults(demoData) {
    const card = document.getElementById("demo-results-card");
    const company = demoData.company || {};
    const contacts = demoData.contacts || [];

    document.getElementById("demo-company-name").innerText = `${company.name || 'OpenAI'} (${company.domain || 'openai.com'})`;
    document.getElementById("demo-company-meta").innerText = `Headcount: ${company.numberofemployees || '770'} | Revenue: ${company.annualrevenue ? '$' + Number(company.annualrevenue).toLocaleString() : 'N/A'} | HQ: ${company.city}, ${company.state}`;

    const tbody = document.getElementById("demo-contacts-table-body");
    tbody.innerHTML = "";

    contacts.forEach(c => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50 transition";
        const linkedinLink = c.linkedin_url
            ? `<a href="${sanitizeUrl(c.linkedin_url)}" target="_blank" rel="noopener noreferrer" class="text-xs text-brand-600 hover:underline">LinkedIn ↗</a>`
            : "-";

        tr.innerHTML = `
            <td class="py-3 px-4 font-semibold text-slate-900">${escapeHtml(c.name)}</td>
            <td class="py-3 px-4 text-slate-700">${escapeHtml(c.job_title)}</td>
            <td class="py-3 px-4 text-brand-600 font-mono text-xs">${escapeHtml(c.email || 'N/A')}</td>
            <td class="py-3 px-4 text-slate-600 font-mono text-xs">${escapeHtml(c.phone || 'N/A')}</td>
            <td class="py-3 px-4 text-slate-600">${escapeHtml(c.location)}</td>
            <td class="py-3 px-4">
                ${linkedinLink}
            </td>
        `;
        tbody.appendChild(tr);
    });

    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// -----------------------------------------------------------------------------
// Interactive Tool: Enrich Company
// -----------------------------------------------------------------------------
async function handleEnrichCompany(event) {
    event.preventDefault();
    const domainInput = document.getElementById("enrich-domain-input");
    const btn = document.getElementById("btn-enrich-comp");
    const spinner = document.getElementById("enrich-comp-spinner");
    const output = document.getElementById("enrich-comp-output");

    const domain = domainInput.value.trim();
    if (!domain) return;

    btn.disabled = true;
    spinner.classList.remove("hidden");

    try {
        const res = await fetch("/api/companies/enrich", {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({ domain: domain }),
        });
        const data = await res.json();

        if (data.success && data.data) {
            const comp = data.data.normalized || {};
            showToast(`Company ${domain} enriched successfully!`, "success");
            output.classList.remove("hidden");
            document.getElementById("comp-out-name").innerText = `${comp.name || domain} - ${comp.industry || 'Tech'}`;
            document.getElementById("comp-out-details").innerText = `Employees: ${comp.numberofemployees || 'N/A'} | Revenue: ${comp.annualrevenue || 'N/A'} | Location: ${comp.city || 'N/A'}, ${comp.state || ''}`;
            document.getElementById("comp-out-desc").innerText = comp.description || "No description provided.";
            refreshStats();
        } else {
            showToast("Failed to enrich company: " + (data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error enriching company: " + e.message, "error");
    } finally {
        btn.disabled = false;
        spinner.classList.add("hidden");
    }
}

// -----------------------------------------------------------------------------
// Interactive Tool: Find Contacts
// -----------------------------------------------------------------------------
async function handleFindContacts(event) {
    event.preventDefault();
    const domainInput = document.getElementById("find-domain-input");
    const limitInput = document.getElementById("find-limit-input");
    const titlesInput = document.getElementById("find-titles-input");
    const btn = document.getElementById("btn-find-contacts");
    const spinner = document.getElementById("find-contacts-spinner");
    const summary = document.getElementById("find-contacts-summary");

    const domain = domainInput.value.trim();
    const limit = parseInt(limitInput.value) || 5;
    const titles = titlesInput.value.split(",").map(t => t.trim()).filter(Boolean);

    btn.disabled = true;
    spinner.classList.remove("hidden");

    try {
        const res = await fetch("/api/contacts/find", {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
                company_domain: domain,
                job_titles: titles,
                limit: limit,
                add_to_hubspot: true,
            }),
        });
        const data = await res.json();

        if (data.success && data.data) {
            showToast(`Discovered and linked ${data.data.length} contacts!`, "success");
            summary.classList.remove("hidden");
            summary.innerText = `✓ Found and created ${data.data.length} contacts matching filters in HubSpot CRM.`;
            refreshStats();
        } else {
            showToast("Error finding contacts: " + (data.message || "Unknown"), "error");
        }
    } catch (e) {
        showToast("Error finding contacts: " + e.message, "error");
    } finally {
        btn.disabled = false;
        spinner.classList.add("hidden");
    }
}

// -----------------------------------------------------------------------------
// Live Auto-Refresh Functions (Logs, Webhooks & Stats)
// -----------------------------------------------------------------------------
async function refreshStats() {
    try {
        const res = await fetch("/api/stats", { headers: getHeaders() });
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("stat-credits-used").innerText = data.credits_used;
        document.getElementById("header-credits-remaining").innerText = `${data.credits_remaining} / 50`;
        document.getElementById("stat-companies").innerText = data.companies_enriched;
        document.getElementById("stat-contacts").innerText = data.contacts_enriched;
        document.getElementById("stat-webhooks").innerText = data.webhooks_received;

        refreshLogs();
        refreshWebhooks();
    } catch (e) {
        console.error("Failed to refresh stats:", e);
    }
}

async function refreshLogs() {
    try {
        const res = await fetch("/api/logs?limit=15", { headers: getHeaders() });
        if (!res.ok) return;
        const logs = await res.json();

        const tbody = document.getElementById("logs-table-body");
        if (!tbody) return;
        tbody.innerHTML = "";

        logs.forEach(l => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50/80 transition";
            const timePart = l.created_at ? (l.created_at.split(" ")[1] || l.created_at) : "";
            tr.innerHTML = `
                <td class="py-3 px-6 text-slate-500 font-mono text-[11px]">${escapeHtml(timePart)}</td>
                <td class="py-3 px-6 font-semibold uppercase text-[11px] text-slate-700">${escapeHtml(l.entity_type)}</td>
                <td class="py-3 px-6 font-medium text-slate-900">${escapeHtml(l.identifier)}</td>
                <td class="py-3 px-6">${getStatusBadge(l.status)}</td>
                <td class="py-3 px-6 text-slate-600 truncate max-w-xs">${escapeHtml(l.message)}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to refresh logs:", e);
    }
}

async function refreshWebhooks() {
    try {
        const res = await fetch("/api/webhooks?limit=10", { headers: getHeaders() });
        if (!res.ok) return;
        const events = await res.json();

        const tbody = document.getElementById("webhooks-table-body");
        if (!tbody) return;
        tbody.innerHTML = "";

        events.forEach(ev => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50/80 transition";
            const timePart = ev.received_at ? (ev.received_at.split(" ")[1] || ev.received_at) : "";
            tr.innerHTML = `
                <td class="py-3 px-6 text-slate-500 font-mono text-[11px]">${escapeHtml(timePart)}</td>
                <td class="py-3 px-6 font-mono text-[11px] text-slate-600">${escapeHtml(ev.event_id)}</td>
                <td class="py-3 px-6 font-semibold text-slate-800">${escapeHtml(ev.subscription_type)}</td>
                <td class="py-3 px-6 font-mono text-slate-700">${escapeHtml(ev.object_id)}</td>
                <td class="py-3 px-6">${getStatusBadge(ev.status)}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to refresh webhooks:", e);
    }
}

// Auto-refresh interval (5 seconds)
setInterval(refreshStats, 5000);

// Initial load
document.addEventListener("DOMContentLoaded", () => {
    refreshStats();
});
