/**
 * Deepbuster GUI Controller Application Script
 * Orchestrates navigation tabs, dynamic scans control APIs, live results rendering,
 * visual capture screenshot elements, file browser dialogue modals, and history listings.
 */

document.addEventListener("DOMContentLoaded", () => {
    window.currentAiWords = [];

    // Navigation Tabs Routing
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    const tabContexts = {
        scan: {
            title: "Scan Workspace",
            subtitle: "Configure directives and execute intelligence discovery"
        },
        graph: {
            title: "Network Topology Map",
            subtitle: "Real-time visual path mapping and node relationship graph"
        },
        visual: {
            title: "Visual Capture Evidence",
            subtitle: "Automated browser screenshots queue and rendering pipeline"
        },
        history: {
            title: "Scan History & Database Logs",
            subtitle: "Audit previous executions, findings, and metadata history"
        },
        evasion: {
            title: "Settings & Configuration",
            subtitle: "Fine-tune evasive request configurations and API connection options"
        }
    };

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");

            navButtons.forEach(b => b.classList.remove("active"));
            tabPanels.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const activePanel = document.getElementById(`tab-${targetTab}`);
            if (activePanel) {
                activePanel.classList.add("active");
            }

            // Update top header dynamically based on active tab context
            const context = tabContexts[targetTab];
            if (context) {
                const headerTitle = document.getElementById("headerTitle");
                const headerSubtitle = document.getElementById("headerSubtitle");
                if (headerTitle) headerTitle.textContent = context.title;
                if (headerSubtitle) headerSubtitle.textContent = context.subtitle;
            }

            // Trigger Vis graph canvas redraw if active
            if (targetTab === 'graph' && window.liveGraph && window.liveGraph.network) {
                setTimeout(() => {
                    window.liveGraph.network.fit();
                }, 100);
            }
        });
    });

    // Toggle Audio Setting Handler
    const audioToggle = document.getElementById("audioToggle");
    if (audioToggle) {
        audioToggle.addEventListener("change", () => {
            if (window.synth) {
                window.synth.enabled = audioToggle.checked;
            }
        });
    }

    // Toggle custom extensions options
    const enableExtensions = document.getElementById("enableExtensions");
    const extensionsBlock = document.getElementById("extensionsBlock");
    const extSourceInput = document.getElementById("extSourceInput");
    const extSourceFile = document.getElementById("extSourceFile");
    const extensionsInput = document.getElementById("extensionsInput");
    const extensionsFilePath = document.getElementById("extensionsFilePath");
    const btnBrowseExtensions = document.getElementById("btnBrowseExtensions");

    if (enableExtensions && extensionsBlock) {
        enableExtensions.addEventListener("change", () => {
            extensionsBlock.style.display = enableExtensions.checked ? "block" : "none";
        });
    }

    if (extSourceInput && extSourceFile && extensionsInput && extensionsFilePath && btnBrowseExtensions) {
        const toggleRadioSource = () => {
            extensionsInput.disabled = !extSourceInput.checked;
            extensionsFilePath.disabled = !extSourceFile.checked;
            btnBrowseExtensions.disabled = !extSourceFile.checked;
        };
        extSourceInput.addEventListener("change", toggleRadioSource);
        extSourceFile.addEventListener("change", toggleRadioSource);
    }

    // Advanced accordion toggle
    const btnAccordionTrigger = document.getElementById("btnAccordionTrigger");
    const accordionContainer = document.querySelector(".accordion-container");
    if (btnAccordionTrigger && accordionContainer) {
        btnAccordionTrigger.addEventListener("click", (e) => {
            e.preventDefault();
            accordionContainer.classList.toggle("active");
        });
    }

    // UI Fields
    const targetUrlInput = document.getElementById("targetUrl");
    const wordlistPathInput = document.getElementById("wordlistPath");
    const threadsInput = document.getElementById("threads");
    const threadsVal = document.getElementById("threadsVal");

    // Sliders displays
    if (threadsInput && threadsVal) {
        threadsInput.addEventListener("input", () => {
            threadsVal.textContent = threadsInput.value;
        });
    }

    // Wordlist Category Auto-population Helper
    const wordlistCategorySelect = document.getElementById("wordlistCategory");
    const wordlistPathLabel = document.querySelector("label[for='wordlistPath']");
    if (wordlistCategorySelect && wordlistPathInput) {
        wordlistCategorySelect.addEventListener("change", () => {
            const category = wordlistCategorySelect.value;
            const btnBrowse = document.querySelector(".btn-browse");

            // Adjust label text, placeholder, and browse button visibility dynamically
            if (category === "url") {
                if (wordlistPathLabel) {
                    wordlistPathLabel.textContent = "Wordlist URL";
                }
                wordlistPathInput.placeholder = "http://example.com/wordlist.txt";
                if (btnBrowse) {
                    btnBrowse.style.display = "none";
                }
            } else {
                if (wordlistPathLabel) {
                    wordlistPathLabel.textContent = "Full File Path";
                }
                wordlistPathInput.placeholder = "/home/kali/mylist.txt";
                if (btnBrowse) {
                    btnBrowse.style.display = "";
                }
            }
            // Clear the input value so the placeholder is visible
            wordlistPathInput.value = "";
        });
    }

    // Control buttons
    const btnStart = document.getElementById("btnStart");
    const btnPause = document.getElementById("btnPause");
    const btnResume = document.getElementById("btnResume");
    const btnStop = document.getElementById("btnStop");
    // const btnNext = document.getElementById("btnNext");

    // Stat displays
    const statRequests = document.getElementById("statRequests");
    const statQueue = document.getElementById("statQueue");
    const statDirectory = document.getElementById("statDirectory");
    const progressBarFill = document.getElementById("progressBarFill");
    const progressPercent = document.getElementById("progressPercent");
    const aiStatusText = document.getElementById("aiStatusText");
    const aiWordsText = document.getElementById("aiWordsText");
    const btnViewAiWords = document.getElementById("btnViewAiWords");
    const aiWordsModal = document.getElementById("aiWordsModal");
    const closeAiWords = document.getElementById("closeAiWords");
    const btnCloseAiWordsFooter = document.getElementById("btnCloseAiWordsFooter");
    const aiWordsListContainer = document.getElementById("aiWordsListContainer");
    const statusMessage = document.getElementById("statusMessage");

    const count2xx = document.getElementById("count2xx");
    const count3xx = document.getElementById("count3xx");
    const count4xx = document.getElementById("count4xx");
    const count5xx = document.getElementById("count5xx");

    const statusIndicator = document.getElementById("statusIndicator");
    const statusIndicatorText = document.getElementById("statusIndicatorText");

    function setEngineStatus(status, text) {
        if (!statusIndicator) return;
        statusIndicator.className = "indicator " + status;
        if (statusIndicatorText) {
            statusIndicatorText.textContent = text;
        }
    }

    // Disabling/enabling Custom User Agent input when Rotate UAs is checked
    const optRotateUserAgents = document.getElementById("optRotateUserAgents");
    const optUserAgent = document.getElementById("optUserAgent");
    if (optRotateUserAgents && optUserAgent) {
        optRotateUserAgents.addEventListener("change", () => {
            optUserAgent.disabled = optRotateUserAgents.checked;
            if (optRotateUserAgents.checked) {
                optUserAgent.value = "";
                optUserAgent.placeholder = "User-Agent Rotation Active";
            } else {
                optUserAgent.placeholder = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...";
            }
        });
    }

    // Live state mapping
    let pollInterval = null;
    let knownPaths = new Set();
    let currentScanId = null;

    // Start Scan Trigger
    if (btnStart) {
        btnStart.addEventListener("click", async () => {
            const payload = {
                targetUrl: targetUrlInput.value.trim(),
                wordlistPath: wordlistPathInput.value.trim(),
                threads: parseInt(threadsInput.value),
                delay: parseInt(document.getElementById("optDelay").value || 50),
                userAgent: document.getElementById("optUserAgent").value.trim() || null,
                cookies: document.getElementById("optCookies").value.trim() || null,
                headers: document.getElementById("optHeaders").value.trim() || null,
                proxy: document.getElementById("optProxy").value.trim() || null,
                proxyUser: document.getElementById("optProxyUser").value.trim() || null,
                proxyPass: document.getElementById("optProxyPass").value.trim() || null,
                httpUser: document.getElementById("optHttpUser").value.trim() || null,
                httpPass: document.getElementById("optHttpPass").value.trim() || null,
                noRecursive: document.getElementById("optNoRecursive").checked,
                dontForceSlash: document.getElementById("optDontForceSlash").checked,
                dontStopOnWarning: document.getElementById("optDontStopOnWarning").checked,
                ignoreCase: !document.getElementById("optCaseSensitive").checked,
                ignoreCodes: document.getElementById("optIgnoreCodes").value.trim(),
                certPath: document.getElementById("optCertPath").value.trim() || null,
                aiEnabled: document.getElementById("aiEnabled").checked,
                outputFile: document.getElementById("optOutputFile").value.trim() || null,
                followRedirects: document.getElementById("optFollowRedirects").checked,
                fineTune404: document.getElementById("optFineTune404").checked,
                usePathAsIs: document.getElementById("optUsePathAsIs").checked,
                rotateUserAgents: document.getElementById("optRotateUserAgents").checked,
                autoPause: document.getElementById("optAutoPause").checked,
                probeVariations: document.getElementById("optProbeVariations").value.trim() || null,
                insecure: document.getElementById("optInsecure").checked
            };

            // Build extension params if checked
            if (enableExtensions && enableExtensions.checked) {
                payload.extensionsMode = extSourceInput.checked ? "input" : "file";
                payload.extensionsInput = extensionsInput.value.trim();
                payload.extensionsFilePath = extensionsFilePath.value.trim();
            }

            if (!payload.targetUrl) {
                alert("Target URL path is required.");
                return;
            }
            if (!payload.wordlistPath) {
                alert("Wordlist file path is required.");
                return;
            }

            try {
                // Clear dynamic screens and metrics
                knownPaths.clear();
                document.getElementById("resultsTableBody").innerHTML = "";
                document.getElementById("visualQueueList").innerHTML = "";
                document.getElementById("screenshotGallery").innerHTML = "";
                if (window.liveGraph) window.liveGraph.clear();

                // Reset numerical displays to zero
                if (statRequests) statRequests.textContent = "0";
                if (aiWordsText) aiWordsText.textContent = "0";
                if (statQueue) statQueue.textContent = "0 / 0";
                if (statDirectory) statDirectory.textContent = "/";
                if (progressBarFill) progressBarFill.style.width = "0%";
                if (progressPercent) progressPercent.textContent = "0%";

                if (count2xx) count2xx.textContent = "0";
                if (count3xx) count3xx.textContent = "0";
                if (count4xx) count4xx.textContent = "0";
                if (count5xx) count5xx.textContent = "0";

                // Trigger start sound
                if (window.synth) window.synth.playStart();

                const response = await fetch("/api/scan/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (data.error) {
                    alert(data.error);
                    return;
                }

                currentScanId = data.scan_id;

                // Update UI State
                document.title = `Scanning: ${payload.targetUrl}`;
                const pageSubtitle = document.getElementById("pageSubtitle");
                if (pageSubtitle) pageSubtitle.textContent = `Scanning: ${payload.targetUrl}`;

                // Toggle action button states
                btnStart.disabled = true;
                btnPause.disabled = false;
                btnResume.disabled = true;
                btnStop.disabled = false;
                // btnNext.disabled = false;

                statusMessage.textContent = "Scan running...";
                setEngineStatus("yellow", "Scanning...");

                // Start status poll interval loop
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(pollState, 1000);
            } catch (e) {
                console.error("Scan initialization error:", e);
                alert("Failed to start scan server engine.");
            }
        });
    }

    // Pause Control Trigger
    if (btnPause) {
        btnPause.addEventListener("click", async () => {
            const resp = await fetch("/api/scan/pause", { method: "POST" });
            const data = await resp.json();
            if (data.status === "paused") {
                btnPause.disabled = true;
                btnResume.disabled = false;
                statusMessage.textContent = "Scan paused";
                setEngineStatus("yellow", "Scan Paused");
                if (window.synth) window.synth.playError();
            }
        });
    }

    // Resume Control Trigger
    if (btnResume) {
        btnResume.addEventListener("click", async () => {
            const resp = await fetch("/api/scan/resume", { method: "POST" });
            const data = await resp.json();
            if (data.status === "running") {
                btnPause.disabled = false;
                btnResume.disabled = true;
                statusMessage.textContent = "Scan running...";
                setEngineStatus("yellow", "Scanning...");
                if (window.synth) window.synth.playStart();
            }
        });
    }

    // Stop Control Trigger
    if (btnStop) {
        btnStop.addEventListener("click", async () => {
            const resp = await fetch("/api/scan/stop", { method: "POST" });
            const data = await resp.json();
            if (data.status === "stopped") {


                btnStart.disabled = false;
                btnPause.disabled = true;
                btnResume.disabled = true;
                btnStop.disabled = true;
                // btnNext.disabled = true;
                statusMessage.textContent = "Scan stopped by user";
                setEngineStatus("red", "Engine Stopped");
                if (window.synth) window.synth.playError();

                // Stop poller interval
                if (pollInterval) clearInterval(pollInterval);
                loadHistory();
            }
        });
    }

    // Skip Directory Control Trigger
    // if (btnNext) {
    //     btnNext.addEventListener("click", async () => {
    //         const resp = await fetch("/api/scan/next-directory", { method: "POST" });
    //         const data = await resp.json();
    //         if (data.status === "success") {
    //             statusMessage.textContent = `Skipped dir ${data.skipped_directory} (${data.count} items)`;
    //         }
    //     });
    // }

    // Update Status Polling Function
    async function pollState() {
        try {
            const res = await fetch("/api/scan/status");
            const state = await res.json();

            if (state.status === "idle") {
                if (pollInterval) clearInterval(pollInterval);
                setEngineStatus("green", "Engine Idle");
                return;
            }

            // Sync sidebar status and controls
            if (state.status === "running") {
                setEngineStatus("yellow", "Scanning...");
                if (btnStart) btnStart.disabled = true;
                if (btnPause) btnPause.disabled = false;
                if (btnResume) btnResume.disabled = true;
                if (btnStop) btnStop.disabled = false;
            } else if (state.status === "paused") {
                setEngineStatus("yellow", "Scan Paused");
                if (btnStart) btnStart.disabled = true;
                if (btnPause) btnPause.disabled = true;
                if (btnResume) btnResume.disabled = false;
                if (btnStop) btnStop.disabled = false;
                if (statusMessage) {
                    if (state.paused_reason === "waf_block") {
                        statusMessage.innerHTML = `<span style="color: #ff4d5e; font-weight: bold;">[WAF Block Detected]</span> Scan paused automatically due to consecutive 403/429 errors.`;
                        setEngineStatus("red", "WAF Blocked");
                    } else {
                        statusMessage.textContent = "Scan paused";
                    }
                }
            }

            // Sync metrics display
            statRequests.textContent = state.total_requests;
            statQueue.textContent = state.queue_size;
            statDirectory.textContent = state.current_directory || "/";
            aiStatusText.textContent = state.ai_status;
            if (aiWordsText) aiWordsText.textContent = state.ai_words_generated || 0;
            window.currentAiWords = state.ai_words_list || [];



            count2xx.textContent = state.counts[2] || 0;
            count3xx.textContent = state.counts[3] || 0;
            count4xx.textContent = state.counts[4] || 0;
            count5xx.textContent = state.counts[5] || 0;

            // Simple fake progress estimation based on total request + queue sizing
            const totalEst = state.total_requests + state.queue_size;
            const percentage = totalEst > 0 ? Math.min(100, Math.round((state.total_requests / totalEst) * 100)) : 0;
            progressBarFill.style.width = `${percentage}%`;
            progressPercent.textContent = `${percentage}%`;

            // Poll list results
            await fetchResults();

            if (state.status === "completed" || state.status === "stopped" || state.status === "error") {
                clearInterval(pollInterval);



                btnStart.disabled = false;
                btnPause.disabled = true;
                btnResume.disabled = true;
                btnStop.disabled = true;
                // btnNext.disabled = true;
                statusMessage.textContent = `Scan ${state.status.toUpperCase()}`;
                if (state.status === "completed") {
                    setEngineStatus("green", "Engine Idle");
                } else {
                    setEngineStatus("red", `Engine ${state.status.toUpperCase()}`);
                }

                if (window.synth) {
                    if (state.status === "completed") window.synth.playComplete();
                    else window.synth.playError();
                }

                // Refresh final logs history view
                loadHistory();
            }
        } catch (e) {
            console.error("Poller status error:", e);
        }
    }

    // Fetch and Draw Scan Result Feeds
    async function fetchResults() {
        try {
            const resp = await fetch("/api/scan/results");
            const list = await resp.json();
            const tbody = document.getElementById("resultsTableBody");

            let html = "";
            let newFindDetected = false;

            list.forEach(item => {
                const family = Math.floor(item.status_code / 100);
                const badgeClass = `badge-${family}xx`;

                // Graph mapping check
                if (!knownPaths.has(item.path)) {
                    knownPaths.add(item.path);
                    newFindDetected = true;

                    if (window.liveGraph) {
                        window.liveGraph.addPath(item.path, item.status_code);
                    }

                    // Add elements to visual capture queue automatically only for HTTP 2xx/3xx
                    if (item.status_code >= 200 && item.status_code < 400) {
                        if (item.screenshot_path) {
                            addVisualQueueRow(item.path, item.status_code, item.screenshot_path);
                        } else {
                            addVisualQueueRow(item.path, item.status_code);
                        }
                    }
                }

                const isEligibleForCapture = item.status_code >= 200 && item.status_code < 400;
                const captureBtn = isEligibleForCapture
                    ? `<button class="btn btn-secondary sub-input" onclick="captureSinglePath('${item.path}')">Capture</button>`
                    : `<span style="color: var(--text-muted); font-style: italic;">N/A</span>`;

                // Build full URL for the visit button
                let visitUrl = targetUrlInput.value.trim();
                if (visitUrl && !visitUrl.endsWith('/')) visitUrl += '/';
                let cleanVisitPath = item.path;
                if (cleanVisitPath.startsWith('/')) cleanVisitPath = cleanVisitPath.substring(1);
                const fullVisitUrl = visitUrl + cleanVisitPath;

                html += `
                    <tr>
                        <td><span class="status-badge ${badgeClass}">${item.status_code}</span></td>
                        <td>GET</td>
                        <td><strong>${item.path}</strong></td>
                        <td>${formatBytes(item.response_size)}</td>
                        <td>${formatTimestamp(item.timestamp)}</td>
                        <td style="display:flex;gap:6px;align-items:center;">
                            <a href="${fullVisitUrl}" target="_blank" class="btn btn-primary sub-input" style="font-size:0.78rem;padding:4px 8px;text-decoration:none;">Visit</a>
                            ${captureBtn}
                        </td>
                    </tr>
                `;
            });

            if (newFindDetected && window.liveGraph) {
                window.liveGraph.applyFilter(window.liveGraph.activeFilter);
            }

            if (list.length > 0 && tbody) {
                tbody.innerHTML = html;
            }

            if (newFindDetected && window.synth) {
                window.synth.playFinding();
            }
        } catch (e) {
            console.error("Results reading error:", e);
        }
    }

    // Dynamic recalculation of visual queue status counters (prevents duplicate count bugs)
    function updateVisualCounters() {
        const queueList = document.getElementById("visualQueueList");
        if (!queueList) return;

        const items = queueList.querySelectorAll(".endpoint-item");
        const total = items.length;

        let success = 0;
        let pending = 0;
        let failed = 0;

        items.forEach(item => {
            const statusSpan = item.querySelector(".endpoint-status");
            if (statusSpan) {
                if (statusSpan.classList.contains("success")) {
                    success++;
                } else if (statusSpan.classList.contains("failed")) {
                    failed++;
                } else {
                    pending++;
                }
            }
        });

        const activeCount = document.getElementById("visEndpointsCount");
        const queueCount = document.getElementById("visQueueCount");
        const successCount = document.getElementById("visSuccessCount");
        const failedCount = document.getElementById("visFailedCount");

        if (activeCount) activeCount.textContent = total;
        if (queueCount) queueCount.textContent = pending;
        if (successCount) successCount.textContent = success;
        if (failedCount) failedCount.textContent = failed;
    }

    // Visual Capture Grid queues helper
    function addVisualQueueRow(path, statusCode, screenshotPath = null) {
        const queueList = document.getElementById("visualQueueList");
        if (!queueList) return;

        // Remove empty placeholders
        const emptyPl = queueList.querySelector(".empty-row-text");
        if (emptyPl) emptyPl.remove();

        const rowId = `vrow_${path.replace(/\//g, '_').replace(/\./g, '_')}`;

        let existing = document.getElementById(rowId);
        if (existing) {
            if (screenshotPath) {
                const statusSpan = document.getElementById(`status_${rowId}`);
                if (statusSpan && statusSpan.textContent !== "Captured") {
                    statusSpan.className = "endpoint-status success";
                    statusSpan.textContent = "Captured";
                    updateVisualCounters();
                }
            }
            return;
        }

        const div = document.createElement("div");
        div.id = rowId;
        div.className = "endpoint-item";

        if (screenshotPath) {
            div.innerHTML = `
                <div class="endpoint-meta">
                    <span class="endpoint-path">${path}</span>
                    <span class="endpoint-host">${targetUrlInput.value}</span>
                </div>
                <span class="endpoint-status success" id="status_${rowId}">Captured</span>
            `;
            queueList.appendChild(div);

            // Also append directly to gallery
            appendGalleryCard(path, screenshotPath, false);
            updateVisualCounters();
        } else {
            div.innerHTML = `
                <div class="endpoint-meta">
                    <span class="endpoint-path">${path}</span>
                    <span class="endpoint-host">${targetUrlInput.value}</span>
                </div>
                <span class="endpoint-status pending" id="status_${rowId}">Pending</span>
            `;
            queueList.appendChild(div);
            updateVisualCounters();

            // Auto assess screenshots triggers if checked
            const autoScreenshot = document.getElementById("autoScreenshot");
            if (autoScreenshot && autoScreenshot.checked) {
                triggerVisualAssessment(path, rowId);
            }
        }
    }

    // Launch Evidence Snapshot Assessment API
    async function triggerVisualAssessment(path, rowId) {
        const statusSpan = document.getElementById(`status_${rowId}`);
        if (statusSpan) {
            statusSpan.className = "endpoint-status pending";
            statusSpan.textContent = "Capturing...";
            updateVisualCounters();
        }

        try {
            const resp = await fetch("/api/visual-capture", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    url: targetUrlInput.value.trim() + path,
                    path: path,
                    scanId: currentScanId
                })
            });
            const data = await resp.json();

            if (data.error) {
                if (statusSpan) {
                    statusSpan.className = "endpoint-status failed";
                    statusSpan.textContent = "Failed";
                }
                updateVisualCounters();
                appendGalleryCard(path, null, true);
            } else {
                if (statusSpan) {
                    statusSpan.className = "endpoint-status success";
                    statusSpan.textContent = "Captured";
                }
                updateVisualCounters();

                // Poll check target file until generated successfully to display preview
                pollScreenshotReady(path);
            }
        } catch (e) {
            console.error("Screenshot launch error:", e);
            if (statusSpan) {
                statusSpan.className = "endpoint-status failed";
                statusSpan.textContent = "Failed";
            }
            updateVisualCounters();
        }
    }

    // Poll screenshot image file creation in background using the backend API
    function pollScreenshotReady(path) {
        let attempts = 0;
        const maxAttempts = 15;
        const check = setInterval(async () => {
            attempts++;
            try {
                const response = await fetch(`/api/screenshot/status?scanId=${currentScanId}&path=${encodeURIComponent(path)}`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.status === "ready" && data.screenshot_path) {
                        clearInterval(check);
                        appendGalleryCard(path, data.screenshot_path, false);
                    }
                }
            } catch (err) {
                console.error("Poller screenshot error:", err);
            }

            if (attempts >= maxAttempts) {
                clearInterval(check);
                appendGalleryCard(path, null, true);
            }
        }, 1000);
    }

    // Track gallery paths to prevent duplicate gallery cards
    const galleryPaths = new Set();

    // Render screenshot gallery image card elements
    function appendGalleryCard(path, imageUrl, isFailed) {
        const gallery = document.getElementById("screenshotGallery");
        if (!gallery) return;

        // Prevent duplicate gallery cards for the same path
        if (galleryPaths.has(path)) return;
        galleryPaths.add(path);

        const empty = gallery.querySelector(".empty-row-text");
        if (empty) empty.remove();

        // Build full URL for visit button
        let baseUrl = targetUrlInput.value.trim();
        if (baseUrl && !baseUrl.endsWith('/')) baseUrl += '/';
        let cleanPath = path;
        if (cleanPath.startsWith('/')) cleanPath = cleanPath.substring(1);
        const fullPageUrl = baseUrl + cleanPath;

        const card = document.createElement("div");
        card.className = "evidence-card";

        let previewHtml = `<div class="evidence-preview"><div class="fallback">Assessment Failed</div></div>`;
        if (!isFailed && imageUrl) {
            previewHtml = `
                <div class="evidence-preview" style="cursor:pointer;" data-full-img="${imageUrl}" data-page-url="${fullPageUrl}">
                    <img src="${imageUrl}" alt="Capture preview" onerror="this.style.display='none'">
                </div>
            `;
        }

        card.innerHTML = `
            ${previewHtml}
            <div class="evidence-info">
                <span class="evidence-path">${path}</span>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="evidence-time">${new Date().toLocaleTimeString()}</span>
                    <a href="${fullPageUrl}" target="_blank" class="btn btn-primary" style="font-size:0.7rem;padding:3px 8px;text-decoration:none;">Visit Page</a>
                </div>
            </div>
        `;

        // Lightbox click on image preview
        const preview = card.querySelector('.evidence-preview[data-full-img]');
        if (preview) {
            preview.addEventListener('click', () => {
                openLightbox(preview.getAttribute('data-full-img'), preview.getAttribute('data-page-url'), path);
            });
        }

        gallery.appendChild(card);
    }

    // Lightbox modal for enlarged screenshots
    function openLightbox(imgSrc, pageUrl, path) {
        let overlay = document.getElementById('galleryLightbox');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'galleryLightbox';
            overlay.className = 'lightbox-overlay';
            document.body.appendChild(overlay);

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    overlay.classList.remove('open');
                }
            });
        }

        overlay.innerHTML = `
            <div class="lightbox-content">
                <span class="lightbox-close">&times;</span>
                <img src="${imgSrc}" alt="${path}">
                <div class="lightbox-footer">
                    <span class="lightbox-path">${path}</span>
                    <a href="${pageUrl}" target="_blank" class="btn btn-primary" style="font-size:0.85rem;padding:6px 16px;text-decoration:none;">Visit Page</a>
                </div>
            </div>
        `;

        overlay.querySelector('.lightbox-close').addEventListener('click', () => {
            overlay.classList.remove('open');
        });

        // Force reflow then open for animation
        void overlay.offsetWidth;
        overlay.classList.add('open');
    }

    // Setup single path capture action
    window.captureSinglePath = (path) => {
        // Find if this path exists in the visual queue, if not add it
        const rowId = `vrow_${path.replace(/\//g, '_').replace(/\./g, '_')}`;
        addVisualQueueRow(path, 200); // default status code since we are capturing it
        triggerVisualAssessment(path, rowId);

        // Switch to the gallery tab to show results
        const visTabBtn = document.querySelector('.nav-btn[data-tab="visual"]');
        if (visTabBtn) visTabBtn.click();
    };

    // Setup visual capture button
    const btnCaptureSelected = document.getElementById("btnCaptureSelected");
    if (btnCaptureSelected) {
        btnCaptureSelected.addEventListener("click", () => {
            // Screen capture all discovered items in queue
            const items = document.querySelectorAll(".endpoint-item");
            items.forEach(el => {
                const pathEl = el.querySelector(".endpoint-path");
                const statusEl = el.querySelector(".endpoint-status");
                if (pathEl && statusEl && statusEl.textContent === "Pending") {
                    triggerVisualAssessment(pathEl.textContent, el.id);
                }
            });
        });
    }

    // Live Graph tree direction layout controls
    const btnTreeLR = document.getElementById("btnTreeLR");
    const btnTreeUD = document.getElementById("btnTreeUD");

    if (btnTreeLR && btnTreeUD) {
        btnTreeLR.addEventListener("click", () => {
            btnTreeLR.classList.add("active");
            btnTreeUD.classList.remove("active");
            if (window.liveGraph) window.liveGraph.setDirection('LR');
        });
        btnTreeUD.addEventListener("click", () => {
            btnTreeUD.classList.add("active");
            btnTreeLR.classList.remove("active");
            if (window.liveGraph) window.liveGraph.setDirection('UD');
        });
    }

    // Live Graph status filter controls
    const filterButtons = {
        'all': document.getElementById("btnFilterAll"),
        '2xx': document.getElementById("btnFilter2xx"),
        '3xx': document.getElementById("btnFilter3xx"),
        '4xx': document.getElementById("btnFilter4xx"),
        '5xx': document.getElementById("btnFilter5xx")
    };

    Object.entries(filterButtons).forEach(([key, btn]) => {
        if (btn) {
            btn.addEventListener("click", () => {
                Object.values(filterButtons).forEach(b => {
                    if (b) b.classList.remove("active");
                });
                btn.classList.add("active");
                if (window.liveGraph) {
                    window.liveGraph.applyFilter(key);
                }
            });
        }
    });

    // ============================================
    // Local File Dialog Browser Handler
    // ============================================
    const fileBrowserModal = document.getElementById("fileBrowserModal");
    const closeFileBrowser = document.getElementById("closeFileBrowser");
    const btnBrowserBack = document.getElementById("btnBrowserBack");
    const browserCurrentPath = document.getElementById("browserCurrentPath");
    const fileList = document.getElementById("fileList");
    const browserSelectedPath = document.getElementById("browserSelectedPath");
    const btnBrowserSelect = document.getElementById("btnBrowserSelect");

    const suggestionsDropdown = document.getElementById("pathSuggestionsDropdown");
    let activeSuggestionIndex = -1;
    let suggestionsList = [];

    // Validation function (checks if it's a file, not a directory, and exists)
    let validationTimeout = null;
    function validateSelectedPath(path) {
        if (validationTimeout) clearTimeout(validationTimeout);
        if (!path) {
            btnBrowserSelect.disabled = true;
            return;
        }
        const allowNew = (activeInputTargetId === "optOutputFile");
        validationTimeout = setTimeout(async () => {
            try {
                const resp = await fetch(`/api/validate-file?path=${encodeURIComponent(path)}&allow_new=${allowNew}`);
                const data = await resp.json();
                btnBrowserSelect.disabled = !data.valid;
            } catch (e) {
                btnBrowserSelect.disabled = true;
            }
        }, 300);
    }

    // Autocomplete / suggestions logic when user types
    let autocompleteTimeout = null;
    if (browserSelectedPath) {
        browserSelectedPath.addEventListener("input", () => {
            const val = browserSelectedPath.value;
            validateSelectedPath(val.trim());

            if (autocompleteTimeout) clearTimeout(autocompleteTimeout);
            
            if (!val.trim()) {
                closeSuggestions();
                return;
            }

            autocompleteTimeout = setTimeout(async () => {
                let dir = "";
                let prefix = "";
                const lastSlash = val.lastIndexOf("/");
                if (lastSlash !== -1) {
                    dir = val.substring(0, lastSlash) || "/";
                    prefix = val.substring(lastSlash + 1);
                } else {
                    dir = ""; // current directory
                    prefix = val;
                }

                try {
                    const resp = await fetch(`/api/browse?path=${encodeURIComponent(dir)}`);
                    const data = await resp.json();
                    
                    if (data.error || !data.items) {
                        closeSuggestions();
                        return;
                    }

                    // Filter files AND directories matching prefix (case-insensitive), skip '..'
                    suggestionsList = data.items.filter(item => 
                        item.name !== ".." &&
                        item.name.toLowerCase().startsWith(prefix.toLowerCase())
                    );

                    if (suggestionsList.length > 0) {
                        renderSuggestions();
                    } else {
                        closeSuggestions();
                    }
                } catch (err) {
                    console.error("Autocomplete fetch error:", err);
                    closeSuggestions();
                }
            }, 150);
        });

        // Keyboard navigation for autocomplete list
        browserSelectedPath.addEventListener("keydown", (e) => {
            if (!suggestionsDropdown || !suggestionsDropdown.classList.contains("open")) return;

            const items = suggestionsDropdown.querySelectorAll(".suggestion-item");
            if (items.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
                updateActiveSuggestion(items);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
                updateActiveSuggestion(items);
            } else if (e.key === "Enter") {
                e.preventDefault();
                if (activeSuggestionIndex >= 0 && activeSuggestionIndex < items.length) {
                    items[activeSuggestionIndex].click();
                }
            } else if (e.key === "Escape") {
                closeSuggestions();
            }
        });
    }

    function renderSuggestions() {
        if (!suggestionsDropdown) return;
        suggestionsDropdown.innerHTML = "";
        activeSuggestionIndex = -1;

        suggestionsList.forEach((item, index) => {
            const div = document.createElement("div");
            div.className = "suggestion-item";
            const icon = item.is_dir ? "📁" : "📄";
            div.innerHTML = `<span class="icon">${icon}</span> <span class="name">${item.name}</span>`;
            
            div.addEventListener("click", () => {
                if (item.is_dir) {
                    // Navigate into the directory: set path with trailing slash and re-trigger input
                    browserSelectedPath.value = item.path + "/";
                    closeSuggestions();
                    browserSelectedPath.focus();
                    browserSelectedPath.dispatchEvent(new Event("input"));
                } else {
                    browserSelectedPath.value = item.path;
                    closeSuggestions();
                    btnBrowserSelect.disabled = false;
                    browserSelectedPath.focus();
                }
            });

            suggestionsDropdown.appendChild(div);
        });

        suggestionsDropdown.classList.add("open");
    }

    function updateActiveSuggestion(items) {
        items.forEach(item => item.classList.remove("active"));
        if (activeSuggestionIndex >= 0 && activeSuggestionIndex < items.length) {
            items[activeSuggestionIndex].classList.add("active");
            // Scroll into view if needed
            items[activeSuggestionIndex].scrollIntoView({ block: "nearest" });
        }
    }

    function closeSuggestions() {
        if (suggestionsDropdown) {
            suggestionsDropdown.classList.remove("open");
            suggestionsDropdown.innerHTML = "";
        }
        activeSuggestionIndex = -1;
        suggestionsList = [];
    }

    // Close suggestions when clicking outside
    document.addEventListener("click", (e) => {
        if (suggestionsDropdown && !suggestionsDropdown.contains(e.target) && e.target !== browserSelectedPath) {
            closeSuggestions();
        }
    });

    let currentBrowsingPath = "";
    let activeInputTargetId = null;

    // Attach click handlers to all Browse buttons
    document.addEventListener("click", (e) => {
        if (e.target && e.target.classList.contains("btn-browse") && !e.target.disabled) {
            e.preventDefault();
            activeInputTargetId = e.target.getAttribute("data-target");
            const targetInput = document.getElementById(activeInputTargetId);
            const initialPath = targetInput ? targetInput.value.trim() : "";
            openLocalFileBrowser(initialPath);
        }
    });

    if (closeFileBrowser) {
        closeFileBrowser.addEventListener("click", () => {
            fileBrowserModal.classList.remove("open");
        });
    }

    // Close on click outside modal content
    window.addEventListener("click", (e) => {
        if (e.target === fileBrowserModal) {
            fileBrowserModal.classList.remove("open");
        }
    });

    async function openLocalFileBrowser(path) {
        fileBrowserModal.classList.add("open");
        browserSelectedPath.value = "";
        btnBrowserSelect.disabled = true;

        let targetDir = "";
        if (path) {
            // If it's a file path, get parent directory
            if (path.includes("/")) {
                targetDir = path.substring(0, path.lastIndexOf("/"));
            } else {
                targetDir = path;
            }
        }
        await fetchDirectory(targetDir);
    }

    async function fetchDirectory(path) {
        try {
            browserCurrentPath.textContent = "Loading...";
            fileList.innerHTML = "<li class='file-item'>Loading directory contents...</li>";

            const url = `/api/browse?path=${encodeURIComponent(path)}`;
            const resp = await fetch(url);
            const data = await resp.json();

            if (data.error) {
                fileList.innerHTML = `<li class='file-item' style='color:#ff4d5e;'>Error: ${data.error}</li>`;
                return;
            }

            currentBrowsingPath = data.current_path;
            browserCurrentPath.textContent = currentBrowsingPath;
            fileList.innerHTML = "";

            if (data.items.length === 0) {
                fileList.innerHTML = "<li class='file-item' style='color:#576580; font-style:italic;'>Directory is empty</li>";
                return;
            }

            data.items.forEach(item => {
                // If it is '..', we might skip since we have the UP button, but it's fine to display
                if (item.name === "..") return;

                const li = document.createElement("li");
                li.className = "file-item";
                li.setAttribute("data-path", item.path);
                li.setAttribute("data-dir", item.is_dir ? "true" : "false");

                const icon = item.is_dir ? "📁" : "📄";
                li.innerHTML = `<span class="icon">${icon}</span> <span class="name">${item.name}</span>`;

                // Single click selects item
                li.addEventListener("click", (e) => {
                    e.stopPropagation();
                    document.querySelectorAll(".file-item").forEach(el => el.classList.remove("selected"));
                    li.classList.add("selected");

                    browserSelectedPath.value = item.path;
                    // Disable select button if it's a directory (only allow selecting files)
                    btnBrowserSelect.disabled = item.is_dir;
                });

                // Double click folders to navigate inside
                if (item.is_dir) {
                    li.addEventListener("dblclick", (e) => {
                        e.stopPropagation();
                        fetchDirectory(item.path);
                    });
                }

                fileList.appendChild(li);
            });
        } catch (e) {
            console.error("Directory browse error:", e);
            fileList.innerHTML = `<li class='file-item' style='color:#ff4d5e;'>Error loading directory</li>`;
        }
    }

    if (btnBrowserBack) {
        btnBrowserBack.addEventListener("click", () => {
            if (currentBrowsingPath) {
                // Go to parent directory
                const parts = currentBrowsingPath.split("/");
                parts.pop();
                const parentPath = parts.join("/") || "/";
                fetchDirectory(parentPath);
            }
        });
    }

    if (btnBrowserSelect) {
        btnBrowserSelect.addEventListener("click", () => {
            if (activeInputTargetId && browserSelectedPath.value) {
                const targetInput = document.getElementById(activeInputTargetId);
                if (targetInput) {
                    targetInput.value = browserSelectedPath.value;
                    // Trigger change event if listeners depend on it
                    targetInput.dispatchEvent(new Event("change"));
                }
            }
            fileBrowserModal.classList.remove("open");
        });
    }

    // Historical Logs Tab Fetcher Loader
    window.scanHistory = {};
    async function loadHistory() {
        try {
            const resp = await fetch("/api/scan/history");
            const historyList = await resp.json();
            const tbody = document.getElementById("historyTableBody");

            if (!tbody) return;
            if (historyList.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No historical scans recorded.</td></tr>`;
                return;
            }

            let html = "";
            historyList.forEach(scan => {
                window.scanHistory[scan.id] = scan;
                html += `
                    <tr>
                        <td><strong>#${scan.id}</strong></td>
                        <td><a href="${scan.target_url}" target="_blank" class="range-val">${scan.target_url}</a></td>
                        <td><small>${scan.wordlist_path}</small></td>
                        <td>
                            <div class="system-status">
                                <span class="indicator ${scan.status === 'completed' ? 'green' : 'yellow'}"></span>
                                <span>${scan.status.toUpperCase()}</span>
                            </div>
                        </td>
                        <td>
                            <strong>${(scan.count_200 || 0) + (scan.count_300 || 0)}</strong> findings
                        </td>
                        <td>
                            <button class="btn btn-secondary sub-input" onclick="viewScanDbLogs(${scan.id})">View DB Logs</button>
                        </td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        } catch (e) {
            console.error("Historical scan reading error:", e);
        }
    }

    // Utility formatting helpers
    function formatBytes(bytes) {
        if (!bytes) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    function formatTimestamp(isoStr) {
        if (!isoStr) return "";
        const date = new Date(isoStr);
        return date.toLocaleTimeString();
    }

    // Global action helpers
    window.captureSinglePath = (path) => {
        const rowId = `vrow_${path.replace(/\//g, '_').replace(/\./g, '_')}`;
        addVisualQueueRow(path, 200);
        triggerVisualAssessment(path, rowId);

        // Switch to Visual Tab
        const btn = document.querySelector('[data-tab="visual"]');
        if (btn) btn.click();
    };

    // Fetch and submit AI settings form values
    const aiConfigForm = document.getElementById("aiConfigForm");
    const aiConfigEnabled = document.getElementById("aiConfigEnabled");
    const aiConfigBaseUrl = document.getElementById("aiConfigBaseUrl");
    const aiConfigModel = document.getElementById("aiConfigModel");
    const aiConfigApiKey = document.getElementById("aiConfigApiKey");
    const aiConfigTemperature = document.getElementById("aiConfigTemperature");
    const aiConfigStatus = document.getElementById("aiConfigStatus");

    async function loadAiConfig() {
        if (!aiConfigForm) return;
        try {
            const resp = await fetch("/api/config/ai");
            const config = await resp.json();
            if (config.error) {
                console.error("Failed to load AI configuration settings:", config.error);
                return;
            }
            aiConfigEnabled.checked = config.enabled;
            aiConfigBaseUrl.value = config.base_url;
            aiConfigModel.value = config.model;
            aiConfigApiKey.value = config.api_key;
            aiConfigTemperature.value = config.temperature;
        } catch (err) {
            console.error("AI Config loading network error:", err);
        }
    }

    if (aiConfigForm) {
        aiConfigForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (aiConfigStatus) {
                aiConfigStatus.textContent = "Saving...";
                aiConfigStatus.style.color = "var(--text-muted)";
            }
            try {
                const payload = {
                    enabled: aiConfigEnabled.checked,
                    base_url: aiConfigBaseUrl.value.trim(),
                    model: aiConfigModel.value.trim(),
                    api_key: aiConfigApiKey.value.trim(),
                    temperature: parseFloat(aiConfigTemperature.value)
                };
                const resp = await fetch("/api/config/ai", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (data.status === "success") {
                    if (aiConfigStatus) {
                        aiConfigStatus.textContent = "AI Configuration saved successfully.";
                        aiConfigStatus.style.color = "#00ffcc";
                    }
                    if (window.synth) window.synth.playStart();
                } else {
                    if (aiConfigStatus) {
                        aiConfigStatus.textContent = `Error: ${data.error || 'Unknown error'}`;
                        aiConfigStatus.style.color = "#ff0055";
                    }
                    if (window.synth) window.synth.playError();
                }
            } catch (err) {
                console.error("AI Settings saving network error:", err);
                if (aiConfigStatus) {
                    aiConfigStatus.textContent = "Network error. Failed to save config.";
                    aiConfigStatus.style.color = "#ff0055";
                }
                if (window.synth) window.synth.playError();
            }
        });
    }

    // ============================================
    // Scan Run Archives (DB Logs) Modal Controllers
    // ============================================
    const dbLogsModal = document.getElementById("dbLogsModal");
    const closeDbLogs = document.getElementById("closeDbLogs");
    const btnCloseDbLogsFooter = document.getElementById("btnCloseDbLogsFooter");
    const btnExportDbLogsCSV = document.getElementById("btnExportDbLogsCSV");

    let activeLogScan = null;
    let activeLogResults = [];

    if (closeDbLogs) {
        closeDbLogs.addEventListener("click", () => {
            dbLogsModal.classList.remove("open");
        });
    }

    if (btnCloseDbLogsFooter) {
        btnCloseDbLogsFooter.addEventListener("click", () => {
            dbLogsModal.classList.remove("open");
        });
    }

    window.viewScanDbLogs = async (scanId) => {
        try {
            const scan = window.scanHistory[scanId];
            if (!scan) {
                alert("Scan details not found in cache.");
                return;
            }
            activeLogScan = scan;

            document.getElementById("dbLogsTarget").textContent = scan.target_url;
            document.getElementById("dbLogsWordlist").textContent = scan.wordlist_path;
            document.getElementById("dbLogsStart").textContent = formatTimestamp(scan.start_time);
            document.getElementById("dbLogsEnd").textContent = scan.end_time ? formatTimestamp(scan.end_time) : "N/A";
            document.getElementById("dbLogsRequests").textContent = scan.total_requests;
            document.getElementById("dbLogsStatus").textContent = scan.status.toUpperCase();
            document.getElementById("dbLogsTitle").textContent = `Scan Run #${scan.id} Summary`;

            // Populate response family stats
            document.getElementById("dbLogsCount2xx").textContent = scan.count_200 || 0;
            document.getElementById("dbLogsCount3xx").textContent = scan.count_300 || 0;
            document.getElementById("dbLogsCount4xx").textContent = scan.count_400 || 0;
            document.getElementById("dbLogsCount5xx").textContent = scan.count_500 || 0;

            const tbody = document.getElementById("dbLogsTableBody");
            tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Loading logs results...</td></tr>`;

            dbLogsModal.classList.add("open");

            const resp = await fetch(`/api/scan/${scan.id}/results`);
            const results = await resp.json();
            activeLogResults = results;

            if (results.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" class="empty-row">No discovered paths recorded for this scan.</td></tr>`;
                return;
            }

            let html = "";
            results.forEach(item => {
                const family = Math.floor(item.status_code / 100);
                const badgeClass = `badge-${family}xx`;

                let actionHtml = `<span style="color: var(--text-muted); font-style: italic;">None</span>`;
                if (item.screenshot_path) {
                    actionHtml = `<a class="btn btn-secondary btn-sm" style="font-size:0.8rem; padding: 4px 8px;" href="${item.screenshot_path}" target="_blank">👁️ View Screenshot</a>`;
                }

                html += `
                    <tr>
                        <td><span class="status-badge ${badgeClass}">${item.status_code}</span></td>
                        <td>GET</td>
                        <td><strong>${item.path}</strong></td>
                        <td>${formatBytes(item.response_size)}</td>
                        <td>${actionHtml}</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        } catch (err) {
            console.error("View DB Logs fetch error:", err);
            alert("Failed to load DB results logs.");
        }
    };

    if (btnExportDbLogsCSV) {
        btnExportDbLogsCSV.addEventListener("click", () => {
            if (!activeLogScan || activeLogResults.length === 0) {
                alert("No results data to export.");
                return;
            }
            let csvContent = "Status Code,Method,Path,Full URL,Size (KB),Timestamp,Screenshot URL\r\n";

            activeLogResults.forEach(item => {
                // 1. Full URL path of the page
                let baseUrl = activeLogScan.target_url || "";
                if (baseUrl && !baseUrl.endsWith('/')) {
                    baseUrl += '/';
                }
                let cleanPath = item.path || "";
                if (cleanPath.startsWith('/')) {
                    cleanPath = cleanPath.substring(1);
                }
                const fullUrl = baseUrl + cleanPath;

                // 2. Size in KB
                const sizeKb = (item.response_size / 1024).toFixed(2);

                // 3. Formatted timestamp (YYYY-MM-DD HH:MM:SS)
                let formattedTime = "";
                if (item.timestamp) {
                    const date = new Date(item.timestamp);
                    const YYYY = date.getFullYear();
                    const MM = String(date.getMonth() + 1).padStart(2, '0');
                    const DD = String(date.getDate()).padStart(2, '0');
                    const hh = String(date.getHours()).padStart(2, '0');
                    const mm = String(date.getMinutes()).padStart(2, '0');
                    const ss = String(date.getSeconds()).padStart(2, '0');
                    formattedTime = `${YYYY}-${MM}-${DD} ${hh}:${mm}:${ss}`;
                }

                // 4. Full image path
                let fullScreenshotPath = "";
                if (item.screenshot_path) {
                    if (item.screenshot_path.startsWith('http://') || item.screenshot_path.startsWith('https://')) {
                        fullScreenshotPath = item.screenshot_path;
                    } else {
                        let baseOrigin = window.location.origin;
                        let sPath = item.screenshot_path;
                        if (!sPath.startsWith('/')) {
                            sPath = '/' + sPath;
                        }
                        fullScreenshotPath = baseOrigin + sPath;
                    }
                }

                const row = [
                    item.status_code,
                    "GET",
                    `"${item.path.replace(/"/g, '""')}"`,
                    `"${fullUrl.replace(/"/g, '""')}"`,
                    sizeKb,
                    `"${formattedTime}"`,
                    `"${fullScreenshotPath.replace(/"/g, '""')}"`
                ];
                csvContent += row.join(",") + "\r\n";
            });

            const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.setAttribute("href", url);
            link.setAttribute("download", `deepbuster_scan_${activeLogScan.id}_results.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        });
    }

    // ============================================
    // AI Generated Words Modal Controllers
    // ============================================
    window.currentAiWords = [];

    if (btnViewAiWords) {
        btnViewAiWords.addEventListener("click", () => {
            if (aiWordsListContainer) {
                if (window.currentAiWords && window.currentAiWords.length > 0) {
                    aiWordsListContainer.innerHTML = window.currentAiWords.map(word => {
                        return `<span style="background: rgba(157, 78, 221, 0.15); border: 1px solid rgba(157, 78, 221, 0.4); color: #e2c0ff; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-family: monospace;">${word}</span>`;
                    }).join("");
                } else {
                    aiWordsListContainer.innerHTML = `<span class="no-words-msg" style="color: var(--text-muted); font-style: italic;">No words generated yet.</span>`;
                }
            }
            if (aiWordsModal) aiWordsModal.classList.add("open");
        });
    }

    if (closeAiWords) {
        closeAiWords.addEventListener("click", () => {
            if (aiWordsModal) aiWordsModal.classList.remove("open");
        });
    }

    if (btnCloseAiWordsFooter) {
        btnCloseAiWordsFooter.addEventListener("click", () => {
            if (aiWordsModal) aiWordsModal.classList.remove("open");
        });
    }

    window.addEventListener("click", (e) => {
        if (e.target === aiWordsModal) {
            aiWordsModal.classList.remove("open");
        }
    });

    // Load static arrays history immediately on load
    loadAiConfig();
    loadHistory();
});
