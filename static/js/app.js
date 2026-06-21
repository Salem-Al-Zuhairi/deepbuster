/**
 * Deepbuster GUI Controller Application Script
 * Orchestrates navigation tabs, dynamic scans control APIs, live results rendering,
 * visual capture screenshot elements, file browser dialogue modals, and history listings.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Navigation Tabs Routing
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

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
            let path = "";
            
            // Adjust label text
            if (wordlistPathLabel) {
                if (category === "url") {
                    wordlistPathLabel.textContent = "Wordlist URL";
                } else {
                    wordlistPathLabel.textContent = "Full File Path";
                }
            }

            if (category === "common") {
                path = "/usr/share/wordlists/dirb/common.txt";
            } else if (category === "directories") {
                path = "/usr/share/wordlists/dirb/big.txt";
            } else if (category === "files") {
                path = "/usr/share/wordlists/dirb/small.txt";
            } else if (category === "ai") {
                try {
                    const urlVal = targetUrlInput ? targetUrlInput.value.trim() : "";
                    const hostname = urlVal ? new URL(urlVal).hostname : "0.0.0.0";
                    path = `/home/kali/deepbuster/${hostname}_ai_wordlist.txt`;
                } catch(e) {
                    path = "/home/kali/deepbuster/ai_generated_wordlist.txt";
                }
            } else if (category === "url") {
                path = "http://127.0.0.1:8001/wordlists/common.txt";
            } else if (category === "custom") {
                path = "/home/kali/deepbuster/mylist.txt";
            }
            if (path) {
                wordlistPathInput.value = path;
            }
        });
    }

    // Control buttons
    const btnStart = document.getElementById("btnStart");
    const btnPause = document.getElementById("btnPause");
    const btnResume = document.getElementById("btnResume");
    const btnStop = document.getElementById("btnStop");
    const btnNext = document.getElementById("btnNext");

    // Stat displays
    const statRequests = document.getElementById("statRequests");
    const statQueue = document.getElementById("statQueue");
    const statDirectory = document.getElementById("statDirectory");
    const progressBarFill = document.getElementById("progressBarFill");
    const progressPercent = document.getElementById("progressPercent");
    const aiStatusText = document.getElementById("aiStatusText");
    const statusMessage = document.getElementById("statusMessage");

    const count2xx = document.getElementById("count2xx");
    const count3xx = document.getElementById("count3xx");
    const count4xx = document.getElementById("count4xx");
    const count5xx = document.getElementById("count5xx");

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
                interactiveRecursive: document.getElementById("optInteractiveRecursive").checked,
                dontForceSlash: document.getElementById("optDontForceSlash").checked,
                showNotFound: document.getElementById("optShowNotFound").checked,
                dontStopOnWarning: document.getElementById("optDontStopOnWarning").checked,
                ignoreCase: !document.getElementById("optCaseSensitive").checked,
                ignoreCodes: document.getElementById("optIgnoreCodes").value.trim(),
                certPath: document.getElementById("optCertPath").value.trim() || null,
                aiEnabled: document.getElementById("aiEnabled").checked,
                outputFile: document.getElementById("optOutputFile").value.trim() || null,
                followRedirects: document.getElementById("optFollowRedirects").checked,
                fineTune404: document.getElementById("optFineTune404").checked,
                usePathAsIs: document.getElementById("optUsePathAsIs").checked,
                quiet: document.getElementById("optQuiet").checked,
                verbosity: parseInt(document.getElementById("optVerbosity").value),
                probeVariations: document.getElementById("optProbeVariations").value.trim() || null
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
                
                // Toggle action button states
                btnStart.disabled = true;
                btnPause.disabled = false;
                btnResume.disabled = true;
                btnStop.disabled = false;
                btnNext.disabled = false;
                
                statusMessage.textContent = "Scan running...";
                
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
                btnNext.disabled = true;
                statusMessage.textContent = "Scan stopped by user";
                if (window.synth) window.synth.playError();
                
                // Stop poller interval
                if (pollInterval) clearInterval(pollInterval);
                loadHistory();
            }
        });
    }

    // Skip Directory Control Trigger
    if (btnNext) {
        btnNext.addEventListener("click", async () => {
            const resp = await fetch("/api/scan/next-directory", { method: "POST" });
            const data = await resp.json();
            if (data.status === "success") {
                statusMessage.textContent = `Skipped dir ${data.skipped_directory} (${data.count} items)`;
            }
        });
    }

    // Update Status Polling Function
    async function pollState() {
        try {
            const res = await fetch("/api/scan/status");
            const state = await res.json();

            if (state.status === "idle") {
                if (pollInterval) clearInterval(pollInterval);
                return;
            }

            // Sync metrics display
            statRequests.textContent = state.total_requests;
            statQueue.textContent = state.queue_size;
            statDirectory.textContent = state.current_directory || "/";
            aiStatusText.textContent = state.ai_status;

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
                btnNext.disabled = true;
                statusMessage.textContent = `Scan ${state.status.toUpperCase()}`;
                
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
                const actionButton = isEligibleForCapture 
                    ? `<button class="btn btn-secondary sub-input" onclick="captureSinglePath('${item.path}')">Capture</button>`
                    : `<span style="color: var(--text-muted); font-style: italic;">N/A</span>`;

                html += `
                    <tr>
                        <td><span class="status-badge ${badgeClass}">${item.status_code}</span></td>
                        <td>GET</td>
                        <td><strong>${item.path}</strong></td>
                        <td>${formatBytes(item.response_size)}</td>
                        <td>${formatTimestamp(item.timestamp)}</td>
                        <td>${actionButton}</td>
                    </tr>
                `;
            });

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
            
            // Update success counter
            const activeCount = document.getElementById("visEndpointsCount");
            const visSuccessCount = document.getElementById("visSuccessCount");
            if (activeCount) activeCount.textContent = knownPaths.size;
            if (visSuccessCount) visSuccessCount.textContent = parseInt(visSuccessCount.textContent || 0) + 1;
        } else {
            div.innerHTML = `
                <div class="endpoint-meta">
                    <span class="endpoint-path">${path}</span>
                    <span class="endpoint-host">${targetUrlInput.value}</span>
                </div>
                <span class="endpoint-status pending" id="status_${rowId}">Pending</span>
            `;
            queueList.appendChild(div);

            // Update queue/active counters
            const activeCount = document.getElementById("visEndpointsCount");
            const queueCount = document.getElementById("visQueueCount");
            if (activeCount) activeCount.textContent = knownPaths.size;
            if (queueCount) queueCount.textContent = parseInt(queueCount.textContent || 0) + 1;

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
        }

        const visQueueCount = document.getElementById("visQueueCount");
        const visSuccessCount = document.getElementById("visSuccessCount");
        const visFailedCount = document.getElementById("visFailedCount");

        if (visQueueCount) visQueueCount.textContent = Math.max(0, parseInt(visQueueCount.textContent || 0) - 1);

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
                if (visFailedCount) visFailedCount.textContent = parseInt(visFailedCount.textContent || 0) + 1;
                appendGalleryCard(path, null, true);
            } else {
                if (statusSpan) {
                    statusSpan.className = "endpoint-status success";
                    statusSpan.textContent = "Captured";
                }
                if (visSuccessCount) visSuccessCount.textContent = parseInt(visSuccessCount.textContent || 0) + 1;
                
                // Poll check target file until generated successfully to display preview
                pollScreenshotReady(path);
            }
        } catch (e) {
            console.error("Screenshot launch error:", e);
            if (visFailedCount) visFailedCount.textContent = parseInt(visFailedCount.textContent || 0) + 1;
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

    // Render screenshot gallery image card elements
    function appendGalleryCard(path, imageUrl, isFailed) {
        const gallery = document.getElementById("screenshotGallery");
        if (!gallery) return;
        const empty = gallery.querySelector(".empty-row-text");
        if (empty) empty.remove();

        const card = document.createElement("div");
        card.className = "evidence-card";
        
        let previewHtml = `<div class="evidence-preview"><div class="fallback">Assessment Failed</div></div>`;
        if (!isFailed && imageUrl) {
            previewHtml = `
                <div class="evidence-preview">
                    <img src="${imageUrl}" alt="Capture preview" onerror="this.style.display='none'">
                </div>
            `;
        }

        card.innerHTML = `
            ${previewHtml}
            <div class="evidence-info">
                <span class="evidence-path">${path}</span>
                <span class="evidence-time">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        gallery.appendChild(card);
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
                    // Only enable select button if it's a file (or either, user choice, but usually files for wordlist/certs)
                    btnBrowserSelect.disabled = false;
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
                tbody.innerHTML = `<tr><td colspan="7" class="empty-row">No historical scans recorded.</td></tr>`;
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
                        <td>${scan.threads}</td>
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
            let csvContent = "data:text/csv;charset=utf-8,";
            csvContent += "Status Code,Method,Path,Size,Timestamp,Screenshot Path\r\n";
            
            activeLogResults.forEach(item => {
                const row = [
                    item.status_code,
                    "GET",
                    `"${item.path.replace(/"/g, '""')}"`,
                    item.response_size,
                    `"${item.timestamp}"`,
                    `"${item.screenshot_path || ''}"`
                ];
                csvContent += row.join(",") + "\r\n";
            });
            
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `scan_${activeLogScan.id}_results.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // Load static arrays history immediately on load
    loadAiConfig();
    loadHistory();
});
