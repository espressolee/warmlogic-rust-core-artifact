document.addEventListener('DOMContentLoaded', async () => {
    const identityDisplay = document.getElementById('identity-display');
    const messageInput = document.getElementById('message-input');
    const signButton = document.getElementById('sign-button');
    const resultCard = document.getElementById('result-card');
    const statusLight = document.getElementById('status-light');
    const statusText = document.getElementById('status-text');
    const signatureDisplay = document.getElementById('signature-display');
    const socialFeed = document.getElementById('social-feed');

    // Modal Elements
    const proofModal = document.getElementById('proof-modal');
    const closeModal = document.querySelector('.close-modal');
    const proofId = document.getElementById('proof-id');
    const proofSig = document.getElementById('proof-sig');

    // Fetch Identity on Load
    try {
        const response = await fetch('/api/identity');
        const data = await response.json();
        identityDisplay.textContent = `ID: ${data.identity}`;
    } catch (e) {
        identityDisplay.textContent = 'Kernel Offline';
    }

    // Handle Signing & Social Posting
    signButton.addEventListener('click', async () => {
        const message = messageInput.value;
        if (!message) return;

        signButton.disabled = true;
        signButton.textContent = 'Signing & Validating...';

        try {
            // 1. Local Verification (Internal SDK flow)
            const verifyRes = await fetch('/api/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });
            const packet = await verifyRes.json();

            // Update Verification Board
            resultCard.style.display = 'block';
            signatureDisplay.textContent = `SIG: ${packet.signature.substring(0, 32)}...`;

            if (packet.verified) {
                statusLight.className = 'status-indicator valid';
                statusText.textContent = 'Silicon Verified';
                statusText.style.color = '#00ff88';

                // 2. Broadcast to Logic Society (Persistent Store)
                await fetch('/api/social/post', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                await fetchFeed();
            } else {
                statusLight.className = 'status-indicator invalid';
                statusText.textContent = 'Verification Failed';
                statusText.style.color = '#ff4444';
            }
        } catch (e) {
            alert('Service Error: ' + e.message);
        } finally {
            signButton.disabled = false;
            signButton.textContent = 'Sign for Silicon Truth';
            messageInput.value = '';
        }
    });

    // Close Modal Logic
    closeModal.onclick = () => proofModal.style.display = "none";
    window.onclick = (event) => {
        if (event.target == proofModal) {
            proofModal.style.display = "none";
        }
    }

    // Feed Fetching & Rendering
    async function fetchFeed() {
        try {
            const response = await fetch('/api/social/feed');
            const messages = await response.json();

            socialFeed.innerHTML = messages.map(msg => `
                <div class="message-item" onclick="openProof('${msg.sender_id}', '${msg.signature}')">
                    <div class="msg-header">
                        <div class="flex-row">
                            <div class="avatar" style="background: #${msg.id_hash} linear-gradient(135deg, rgba(255,255,255,0.1), rgba(0,0,0,0.1))"></div>
                            <span class="msg-id">${msg.sender_id.substring(0, 20)}...</span>
                        </div>
                        <span>${new Date(msg.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div class="msg-content">${msg.content}</div>
                </div>
            `).join('');
        } catch (e) {
            console.error('Feed error:', e);
        }
    }

    // Expose openProof to global scope for HTML onclick
    window.openProof = (id, sig) => {
        proofId.textContent = id;
        proofSig.textContent = sig;
        proofModal.style.display = "block";
    };

    // Mesh Network Status
    const peerCountEl = document.getElementById('peer-count');
    const syncIndicator = document.getElementById('sync-indicator');
    const canvas = document.getElementById('network-graph');
    const ctx = canvas ? canvas.getContext('2d') : null;

    async function fetchMeshStatus() {
        try {
            const response = await fetch('/api/mesh/peers');
            const data = await response.json();

            const peerCount = data.active_peers || 0;
            peerCountEl.textContent = `${peerCount} Peer${peerCount !== 1 ? 's' : ''}`;

            // Pulse animation on sync
            if (data.sync_stats && data.sync_stats.sync_count > 0) {
                syncIndicator.classList.add('syncing');
                setTimeout(() => syncIndicator.classList.remove('syncing'), 1000);
            }

            if (ctx) drawNetworkGraph(data.peers);
        } catch (e) {
            peerCountEl.textContent = 'Offline';
        }
    }

    function drawNetworkGraph(peers) {
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;

        // Draw Self (Center)
        ctx.beginPath();
        ctx.arc(centerX, centerY, 8, 0, 2 * Math.PI);
        ctx.fillStyle = '#00f2fe';
        ctx.fill();
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#00f2fe';

        // Draw Peers
        const radius = 50;
        peers.forEach((peer, index) => {
            const angle = (index / peers.length) * 2 * Math.PI;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);

            // Draw Edge
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(x, y);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.lineWidth = 1;
            ctx.stroke();

            // Draw Node
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = '#00ff88';
            ctx.fill();
            ctx.shadowBlur = 5;
            ctx.shadowColor = '#00ff88';
        });

        // Reset Shadow
        ctx.shadowBlur = 0;
    }

    // Initial Load & Polling
    await fetchFeed();
    await fetchMeshStatus();
    setInterval(fetchFeed, 5000);
    setInterval(fetchMeshStatus, 3000);
});
