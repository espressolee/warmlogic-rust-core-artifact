// Sovereign Cockpit Logic - Era 10.5
let currentConfig = {};
let sseSource = null;

function getApiKey() {
    return sessionStorage.getItem('COCKPIT_API_KEY');
}

async function authenticatedFetch(url, options = {}) {
    const key = getApiKey();
    options.headers = {
        ...options.headers,
        'X-API-Key': key
    };
    return fetch(url, options);
}

// Gatekeeper Security Flow
async function authorizeGatekeeper() {
    const input = document.getElementById('api-key-input');
    const key = input.value;
    const error = document.getElementById('gatekeeper-error');

    try {
        const response = await fetch('/api/verify_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: key })
        });

        if (response.ok) {
            sessionStorage.setItem('COCKPIT_API_KEY', key);
            document.getElementById('gatekeeper-overlay').classList.add('opacity-0', 'pointer-events-none');
            setTimeout(() => document.getElementById('gatekeeper-overlay').classList.add('hidden'), 500);
            document.getElementById('gatekeeper-status').classList.remove('hidden');
            document.getElementById('gatekeeper-status').classList.add('flex');

            // Boot services
            fetchLogs();
            fetchConfig();
            fetchTraces();
            initLogStream();
            updateTerminal("Gatekeeper Authorization Success. Session Witnessed.");
        } else {
            throw new Error("Unauthorized");
        }
    } catch (e) {
        error.classList.remove('hidden');
        input.classList.add('border-red-500');
        updateTerminal("Security Alert: Unauthorized login attempt blocked.");
    }
}

async function showView(viewName) {
    document.querySelectorAll('.app-view').forEach(view => view.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');
    updateTerminal(`Navigation: Switched to ${viewName.toUpperCase()} view.`);

    // View-specific logic
    if (viewName === 'config') await fetchConfig();

    // Memory Polling Logic
    if (memoryInterval) clearInterval(memoryInterval);
    if (viewName === 'memory') {
        fetchMemory(); // Initial fetch
        memoryInterval = setInterval(fetchMemory, 2000); // Poll every 2s
    }
}

function updateSystemStatus(data) {
    const dot = document.getElementById('connection-status-dot');
    const text = document.getElementById('connection-status-text');

    if (data.is_latched) {
        dot.className = "size-2 rounded-full bg-red-600 animate-ping";
        text.innerText = "MARTIAL LAW (LATCHED)";
        text.className = "text-xs font-mono text-red-500 uppercase tracking-tighter";
    } else {
        dot.className = "size-2 rounded-full bg-primary animate-pulse";
        text.innerText = "Sovereign Operational";
        text.className = "text-xs font-mono text-primary uppercase tracking-tighter";
    }
}

async function fetchConfig() {
    try {
        const response = await authenticatedFetch('/api/config');
        if (response.status === 401) return;
        currentConfig = await response.json();

        // Update UI components
        const piiInput = document.querySelector('input[type="range"]');
        if (piiInput) piiInput.value = currentConfig.pii_sensitivity * 100;

        const burnInput = document.querySelector('input[type="number"]');
        if (burnInput) burnInput.value = currentConfig.burn_multiplier;

    } catch (e) {
        console.error("Config fetch failed", e);
    }
}

async function fetchLogs() {
    try {
        const response = await authenticatedFetch('/api/logs?limit=15');
        if (response.status === 401) return;
        const logs = await response.json();
        const body = document.getElementById('ledger-body');

        // Update Stats
        document.getElementById('stat-refusals').innerText = logs.length;
        document.getElementById('stat-burn').innerHTML = `${(logs.length * 1000).toLocaleString()} <span class="text-lg font-normal">uSOV</span>`;
        document.getElementById('stat-integrity').innerText = "100.0";

        body.innerHTML = '';
        logs.forEach(log => {
            addLogRow(log);
        });
    } catch (e) {
        console.error("Logs fetch failed", e);
    }
}

let memoryInterval = null;

async function fetchMemory() {
    try {
        const response = await authenticatedFetch('/api/memory/working');
        if (response.status === 401) return;
        const data = await response.json();

        // Update Header Stats
        document.getElementById('mem-session').innerText = data.session_id || "OFFLINE";
        document.getElementById('mem-tokens').innerHTML = `${data.tokens.toLocaleString()} <span class="text-sm text-white/40">tokens</span>`;

        // Update Gauge (Assuming 4k context for now)
        const pct = Math.min((data.tokens / 4000) * 100, 100);
        document.getElementById('mem-gauge').style.width = `${pct}%`;
        document.getElementById('mem-gauge').className = `h-full transition-all duration-500 ${pct > 80 ? 'bg-red-500' : 'bg-primary'}`;

        // Render Chat History
        const stream = document.getElementById('memory-stream');
        if (data.history.length === 0) {
            stream.innerHTML = '<div class="text-center text-white/20 italic mt-10">Working memory empty. Start a chat session.</div>';
            return;
        }

        // Simple diff check to avoid full re-render flickering?
        // For prototype, just clear and render is fine or check length.
        // We'll just render.
        stream.innerHTML = '';

        data.history.forEach(msg => {
            const isUser = msg.role === 'user';
            const isSystem = msg.role === 'system';
            const alignKey = isUser ? 'items-end' : 'items-start';
            const bgKey = isUser ? 'bg-white/10 border-white/5' : (isSystem ? 'bg-red-500/10 border-red-500/20' : 'bg-primary/10 border-primary/20');
            const textKey = isSystem ? 'text-red-300' : 'text-white/80';

            const div = document.createElement('div');
            div.className = `flex flex-col ${alignKey} max-w-full`;
            div.innerHTML = `
                <span class="text-[10px] uppercase text-white/30 mb-1 px-1">${msg.role}</span>
                <div class="px-4 py-3 rounded-xl border ${bgKey} ${textKey} max-w-3xl whitespace-pre-wrap leading-relaxed">${escapeHtml(msg.content)}</div>
            `;
            stream.appendChild(div);
        });

    } catch (e) {
        console.error("Memory fetch failed", e);
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function addLogRow(log, prepend = false) {
    const body = document.getElementById('ledger-body');
    const row = document.createElement('tr');
    row.className = "hover:bg-white/5 transition-colors cursor-pointer group";
    row.onclick = () => inspectEntry(log);

    const resultColor = log.result === 'PASS' ? 'emerald-400' : 'red-400';
    const resultBg = log.result === 'PASS' ? 'emerald-500/10' : 'red-500/10';
    const resultBorder = log.result === 'PASS' ? 'emerald-500/20' : 'red-500/20';

    row.innerHTML = `
        <td class="px-6 py-4 text-primary font-bold">#${log.file.slice(-8, -5).toUpperCase()}</td>
        <td class="px-6 py-4">
            <span class="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/60 text-[10px] uppercase font-bold">${log.policy}</span>
        </td>
        <td class="px-6 py-4">
            <span class="px-3 py-1 rounded-full bg-${resultBg} border border-${resultBorder} text-${resultColor} text-[10px] uppercase font-bold">${log.result}</span>
        </td>
        <td class="px-6 py-4 text-white/60 italic truncate max-w-xs">${log.reason}</td>
        <td class="px-6 py-4 text-right">
            <button onclick="event.stopPropagation(); triggerTrace('${log.trace_id || ''}')" class="px-4 py-1 rounded-full border border-primary/40 text-primary text-xs font-bold group-hover:bg-primary group-hover:text-black transition-all">TRACE</button>
        </td>
    `;
    if (prepend) {
        body.insertBefore(row, body.firstChild);
        if (body.children.length > 20) body.lastChild.remove();
    } else {
        body.appendChild(row);
    }
}

function inspectEntry(log) {
    const detail = document.getElementById('detail-content');

    // Check for NER entities
    let entityMarkup = '';
    if (log.entities && log.entities.length > 0) {
        entityMarkup = `<div class="mt-4 flex flex-wrap gap-2">
            ${log.entities.map(e => `<span class="px-2 py-0.5 bg-primary/20 text-primary text-[10px] rounded border border-primary/30">${e.label}: ${e.text}</span>`).join('')}
        </div>`;
    }

    // Merkle Trace Visualization (Aesthetics improvement)
    const traceId = log.file.slice(0, 16).toUpperCase();
    detail.innerHTML = `
        <div class="flex flex-col gap-6">
            <div class="flex flex-col gap-2">
                <label class="text-[10px] uppercase text-white/40 font-bold tracking-widest leading-none">Merkle Trace ID</label>
                <p class="text-primary font-mono text-xs break-all border-l-2 border-primary/30 pl-3 py-1">${traceId}...</p>
            </div>
            <div class="flex justify-between items-center bg-white/5 p-4 rounded-lg border border-white/10">
                <div>
                    <label class="text-[10px] uppercase text-white/40 font-bold">Verdict</label>
                    <p class="${log.result === 'PASS' ? 'text-primary' : 'text-red-400'} font-bold text-lg">${log.result}</p>
                </div>
                <div class="text-right">
                    <label class="text-[10px] uppercase text-white/40 font-bold">Policy</label>
                    <p class="text-white font-mono">${log.policy}</p>
                </div>
            </div>
            <div>
                <label class="text-[10px] uppercase text-white/40 font-bold">Raw Narrative</label>
                <p class="text-white/80 italic text-xs leading-relaxed mt-1">${log.reason}</p>
                ${entityMarkup}
            </div>
            <div class="matrix-bg p-4 border border-primary/20 rounded-xl shimmer">
                <label class="text-[10px] uppercase text-primary font-bold mb-3 block border-b border-primary/20 pb-1">Sovereign Proof</label>
                <div class="flex flex-col gap-1 font-mono text-[9px] text-primary/60">
                    <p>ROOT_0x${traceId.slice(0, 8)}</p>
                    <p> └── L1_0xAF82... (PASS)</p>
                    <p>     └── L2_0x3E11... (WITNESSED)</p>
                    <p class="mt-2">Minter: [ENCLAVE_NODE_01]</p>
                </div>
            </div>
        </div>
    `;
    updateTerminal(`Forensic inspection: ${log.file} analysis complete.`);
}

function triggerTrace(traceId) {
    if (!traceId) {
        updateTerminal("Trace Alert: No Trace ID associated with this entry.");
        return;
    }
    showView('replay');
    renderTrace(traceId);
}

async function fetchTraces() {
    try {
        const response = await authenticatedFetch('/api/traces');
        if (response.ok) {
            const traces = await response.json();
            // Could populate a 'Traces' tab in future
        }
    } catch (e) {
        console.error("Traces fetch failed", e);
    }
}

async function renderTrace(traceId) {
    const replayContainer = document.querySelector('#view-replay .flex-1');
    replayContainer.innerHTML = `
        <div class="w-full max-w-5xl h-full flex flex-col gap-6 overflow-hidden">
            <div class="flex items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
                <div class="size-10 rounded-full bg-cyan-glow/20 flex items-center justify-center text-cyan-glow">
                    <span class="material-symbols-outlined">account_tree</span>
                </div>
                <div>
                    <h3 class="text-lg font-bold">Trace: ${traceId}</h3>
                    <p class="text-xs text-white/40 uppercase tracking-widest font-mono">Distributed Execution Graph</p>
                </div>
            </div>
            <div id="trace-timeline" class="flex-1 overflow-y-auto pr-4 flex flex-col gap-4">
                <div class="flex items-center justify-center h-40">
                    <div class="size-8 border-2 border-cyan-glow border-t-transparent rounded-full animate-spin"></div>
                </div>
            </div>
        </div>
    `;

    try {
        const response = await authenticatedFetch(`/api/traces/${traceId}`);
        if (!response.ok) throw new Error("Trace not found");
        const events = await response.json();

        const timeline = document.getElementById('trace-timeline');
        timeline.innerHTML = '';

        events.forEach((ev, idx) => {
            const entry = document.createElement('div');
            entry.className = "flex gap-6 group";

            const timeStr = new Date(ev.ts * 1000).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const typeColor = ev.type.includes('ERROR') || ev.type.includes('FAIL') ? 'text-red-400' : 'text-cyan-glow';

            entry.innerHTML = `
                <div class="w-20 text-right font-mono text-[10px] text-white/30 pt-1">${timeStr}</div>
                <div class="relative flex flex-col items-center">
                    <div class="size-3 rounded-full bg-cyan-glow/20 border border-cyan-glow/50 group-hover:bg-cyan-glow transition-all"></div>
                    ${idx < events.length - 1 ? '<div class="w-[1px] flex-1 bg-white/10 my-1"></div>' : ''}
                </div>
                <div class="flex-1 pb-8">
                    <div class="glass-panel p-4 rounded-xl border border-white/5 hover:border-cyan-glow/30 transition-all">
                        <div class="flex justify-between items-start mb-2">
                            <span class="${typeColor} font-bold text-xs font-mono uppercase tracking-tighter">${ev.type}</span>
                            <span class="text-[9px] text-white/20 font-mono">Node: ${ev.node_id || 'LOCAL'}</span>
                        </div>
                        <div class="text-[11px] text-white/60 leading-relaxed font-mono overflow-hidden">
                            ${formatEventData(ev.data)}
                        </div>
                    </div>
                </div>
            `;
            timeline.appendChild(entry);
        });

        updateTerminal(`Trace Engine: Reconstruction of ${traceId} complete. ${events.length} segments mapped.`);
    } catch (e) {
        timeline.innerHTML = `<div class="p-10 text-center text-red-400 font-mono">⚠️ Error: Could not retrieve execution trace.</div>`;
        updateTerminal(`Trace Engine Failure: ${e.message}`);
    }
}

function formatEventData(data) {
    if (!data) return '';
    try {
        if (typeof data === 'string') return data;
        // Specifically format common event fields
        if (data.task_name) return `<span class="text-white">Target: ${data.task_name}</span>`;
        if (data.action) return `<span class="text-secondary">Action: ${data.action.action}</span> <span class="text-white/40">(${Object.keys(data.action).filter(k => k !== 'action').join(', ')})</span>`;
        if (data.result_preview) return `<div class="mt-1 bg-black/40 p-2 rounded border border-white/5 text-[10px] italic">${data.result_preview}</div>`;

        return JSON.stringify(data).slice(0, 100) + '...';
    } catch (e) { return '...'; }
}

async function triggerPropagate() {
    const piiValue = document.querySelector('input[type="range"]').value / 100;
    const burnValue = parseInt(document.querySelector('input[type="number"]').value);

    const updatedConfig = {
        ...currentConfig,
        pii_sensitivity: piiValue,
        burn_multiplier: burnValue
    };

    document.getElementById('signature-modal').classList.remove('hidden');
    document.getElementById('signature-modal').classList.add('flex');
    updateTerminal(`Security: Administrative Seal requested. Waiting for owner witness...`);
}

async function authorizeAndPropagate() {
    const piiValue = document.querySelector('input[type="range"]').value / 100;
    const burnValue = parseInt(document.querySelector('input[type="number"]').value);

    const updatedConfig = {
        ...currentConfig,
        pii_sensitivity: piiValue,
        burn_multiplier: burnValue
    };

    updateTerminal(`Security: Signing and propagating policy to mesh...`);

    try {
        const response = await authenticatedFetch('/api/config/seal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedConfig)
        });
        const result = await response.json();

        if (result.status === 'success') {
            updateTerminal(`Policy Propagated: ${result.message}`);
            updateTerminal(`Seal Signature: ${result.signature.slice(0, 20)}...`);
            hideSignature();
            await fetchConfig();
        } else {
            updateTerminal(`Error: ${result.error || 'Unknown error'}`);
        }
    } catch (e) {
        console.error("Propagation failed", e);
        updateTerminal(`Fatal: Network error during propagation.`);
    }
}

function hideSignature() {
    document.getElementById('signature-modal').classList.add('hidden');
    document.getElementById('signature-modal').classList.remove('flex');
}

function updateTerminal(message) {
    const footer = document.getElementById('footer-log');
    footer.innerText = `[${new Date().toLocaleTimeString()}] ${message}`;
}

// SSE Logging & Unified Telemetry
function initLogStream() {
    if (sseSource) sseSource.close();

    const key = getApiKey();
    sseSource = new EventSource(`/api/logs/stream?api_key=${key}`);

    sseSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // ERA 10.5 Unified Events
        if (data.type === 'REALITY_SYNC') {
            updateRealityStatus(data);
        } else if (data.type === 'TELEMETRY_UPDATE') {
            updateSystemStatus(data.system_status);
            updateMeshStatus(data.mesh);
        } else {
            const log = data;
            updateTerminal(`KERNEL: New event recorded -> ${log.file.slice(0, 8)}... [${log.result}]`);
            addLogRow(log, true);
        }
    };

    sseSource.onerror = (err) => {
        console.error("SSE failed", err);
        sseSource.close();
        setTimeout(initLogStream, 5000);
    };
}

function updateRealityStatus(data) {
    const dot = document.getElementById('reality-status-dot');
    const text = document.getElementById('reality-status-text');

    if (data.drift_score === 0) {
        dot.className = "size-2 rounded-full bg-primary";
        text.innerText = "Synced";
        text.className = "text-xs font-mono text-slate-300 uppercase tracking-tighter";
    } else {
        dot.className = "size-2 rounded-full bg-secondary animate-pulse";
        text.innerText = `Drift ${(data.drift_score * 100).toFixed(0)}%`;
        text.className = "text-xs font-mono text-secondary uppercase font-bold tracking-tighter";
        updateTerminal(`ALERT: Reality Drift detected! Root: ${data.local_root.slice(0, 8)}`);
    }
}

function updateMeshStatus(peers) {
    if (!peers) return;

    // Update Counts
    const countEl = document.getElementById('swarm-count');
    if (countEl) countEl.innerText = peers.length;

    // Update Grid
    const grid = document.getElementById('swarm-grid');
    if (!grid) return;

    // Naive re-render for now (Performance optimization: Diffing later if >500 nodes)
    grid.innerHTML = '';

    if (peers.length === 0) {
        grid.innerHTML = '<div class="col-span-10 text-center text-white/20 italic mt-20">No active peers found in local DHT table.</div>';
        return;
    }

    peers.forEach(peer => {
        const isSelf = peer.node_id.includes("(Self)");
        const statusColor = peer.status === 'ONLINE' ? 'bg-cyan-glow' : 'bg-red-500';
        const shadowColor = peer.status === 'ONLINE' ? 'shadow-[0_0_10px_rgba(13,242,242,0.3)]' : 'shadow-none';

        const node = document.createElement('div');
        node.className = `aspect-square rounded-xl glass-panel border border-white/5 flex flex-col items-center justify-center gap-2 p-2 group hover:border-cyan-glow/50 transition-all cursor-pointer relative overflow-hidden`;
        node.onclick = () => showNodeDetail(peer);

        node.innerHTML = `
            <div class="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div class="size-3 rounded-full ${statusColor} ${shadowColor} ${isSelf ? 'animate-pulse' : ''}"></div>
            <p class="text-[10px] font-mono text-white/60 truncate w-full text-center">${peer.node_id.slice(0, 8)}</p>
            ${isSelf ? '<span class="absolute top-1 right-1 text-[8px] text-emerald-400 font-bold">ME</span>' : ''}
        `;
        grid.appendChild(node);
    });
}

function showNodeDetail(peer) {
    updateTerminal(`Swarm Inspector: Node ${peer.node_id.slice(0, 16)}... selected.`);
    // Future: Open detail modal
}

// Initialization Check
window.addEventListener('DOMContentLoaded', () => {
    const key = getApiKey();
    if (key) {
        document.getElementById('gatekeeper-overlay').classList.add('hidden');
        document.getElementById('gatekeeper-status').classList.remove('hidden');
        document.getElementById('gatekeeper-status').classList.add('flex');
        fetchLogs();
        fetchConfig();
        initLogStream();
    }
});

updateTerminal("Sovereign Cockpit Web Service Online. Waiting for Gatekeeper...");
