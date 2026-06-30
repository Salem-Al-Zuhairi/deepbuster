import os
import sys
import socket
import threading
import asyncio
import io
import time
from datetime import datetime
import json
from flask import Flask, jsonify, request, send_from_directory, render_template
import database
from deepbuster import (
    Deepbuster,
    parse_headers,
    parse_proxy,
    parse_ignore_codes,
    parse_extensions,
    parse_variations,
    save_output,
    take_screenshot,
    check_target_active,
    download_remote_wordlist,
    ensure_playwright_installed
)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Global scanner worker state
class ActiveScan:
    def __init__(self):
        self.lock = threading.Lock()
        self.scanner = None
        self.loop = None
        self.thread = None
        self.scan_id = None
        self.target_url = None
        self.status = "idle"  # idle, running, paused, completed, stopped, error
        self.start_time = None
        self.end_time = None
        
        # Results cache
        self.results = []
        self.counts = {2: 0, 3: 0, 4: 0, 5: 0}
        self.total_requests = 0
        self.ai_words_generated = 0
        self.ai_words_list = []

    def reset(self, scan_id, target_url):
        with self.lock:
            self.scanner = None
            self.loop = None
            self.thread = None
            self.scan_id = scan_id
            self.target_url = target_url
            self.status = "running"
            self.start_time = datetime.now()
            self.end_time = None
            self.results = []
            self.counts = {2: 0, 3: 0, 4: 0, 5: 0}
            self.total_requests = 0
            self.ai_words_generated = 0
            self.ai_words_list = []

active_scan = ActiveScan()

# Scanner execution runner in worker thread
def run_scanner_loop(target_url, wordlist, kwargs, scan_id):
    active_scan.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(active_scan.loop)
    
    # Instantiate the Deepbuster scanner
    active_scan.scanner = Deepbuster(target_url, **kwargs)
    
    # Custom callbacks to update memory state and DB
    async def pre_fetch_hook(path: str) -> None:
        # Keep track of total request count
        active_scan.total_requests = active_scan.scanner.total_requests
        if not active_scan.scanner.pause_event.is_set() and active_scan.status == "running":
            active_scan.status = "paused"
            database.update_scan_status(scan_id, "paused")
    
    async def found_hook(path: str, status_code: int, size: int) -> None:
        active_scan.total_requests = active_scan.scanner.total_requests
        family = status_code // 100
        if family in active_scan.counts:
            active_scan.counts[family] += 1
        else:
            active_scan.counts[family] = active_scan.counts.get(family, 0) + 1
            
        result_item = {
            "path": path,
            "status_code": status_code,
            "response_size": size,
            "timestamp": datetime.now().isoformat()
        }
        
        # Avoid duplicate results in memory cache
        with active_scan.lock:
            if not any(item["path"] == path for item in active_scan.results):
                active_scan.results.append(result_item)
        
        # Async-to-thread DB writes to avoid blocking network I/O
        await asyncio.to_thread(database.add_scan_result, scan_id, path, status_code, size)
        await asyncio.to_thread(
            database.update_scan_stats,
            scan_id,
            active_scan.total_requests,
            active_scan.counts.get(2, 0),
            active_scan.counts.get(3, 0),
            active_scan.counts.get(4, 0),
            active_scan.counts.get(5, 0)
        )

    async def error_hook(path: str, status_code: int, size: int) -> None:
        active_scan.total_requests = active_scan.scanner.total_requests
        family = status_code // 100
        if family in active_scan.counts:
            active_scan.counts[family] += 1
            
        result_item = {
            "path": path,
            "status_code": status_code,
            "response_size": size,
            "timestamp": datetime.now().isoformat()
        }
        # Only log/store errors if 404 is not ignored or user specified
        if status_code not in active_scan.scanner.ignored_codes:
            with active_scan.lock:
                if not any(item["path"] == path for item in active_scan.results):
                    active_scan.results.append(result_item)
            await asyncio.to_thread(database.add_scan_result, scan_id, path, status_code, size)
            
        await asyncio.to_thread(
            database.update_scan_stats,
            scan_id,
            active_scan.total_requests,
            active_scan.counts.get(2, 0),
            active_scan.counts.get(3, 0),
            active_scan.counts.get(4, 0),
            active_scan.counts.get(5, 0)
        )

    # Attach callbacks
    active_scan.scanner.pre_fetch_callback = pre_fetch_hook
    active_scan.scanner.found_callback = found_hook
    active_scan.scanner.error_callback = error_hook
    
    try:
        active_scan.loop.run_until_complete(active_scan.scanner.run(wordlist))
        active_scan.status = "completed"
        database.update_scan_status(scan_id, "completed", datetime.now().isoformat())
    except asyncio.CancelledError:
        active_scan.status = "stopped"
        database.update_scan_status(scan_id, "stopped", datetime.now().isoformat())
    except Exception as e:
        active_scan.status = "error"
        database.update_scan_status(scan_id, f"error: {str(e)}", datetime.now().isoformat())
    finally:
        # Write output file if requested (even if stopped or error, to save partial progress!)
        output_file = kwargs.get('output_file')
        if output_file and active_scan.scanner:
            is_csv = output_file.lower().endswith('.csv')
            save_output(output_file, active_scan.scanner.results, is_csv=is_csv, base_url=target_url)
        active_scan.loop.close()

# Flask API Handlers
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/scan/start", methods=["POST"])
def start_scan():
    data = request.json or {}
    target_url = data.get("targetUrl")
    wordlist_path = data.get("wordlistPath")
    threads = int(data.get("threads", 20))
    delay = int(data.get("delay", 50))
    
    if not target_url:
        return jsonify({"error": "Target URL is required"}), 400
    if not wordlist_path:
        return jsonify({"error": "Wordlist path is required"}), 400

    # If it is a URL, fetch it and cache it locally
    is_remote_wordlist = wordlist_path.startswith("http://") or wordlist_path.startswith("https://")
    if is_remote_wordlist:
        cached_path, err = download_remote_wordlist(wordlist_path)
        if err:
            return jsonify({"error": err}), 400
        wordlist_path = cached_path
    else:
        if not os.path.exists(wordlist_path):
            return jsonify({"error": f"Wordlist file not found: {wordlist_path}"}), 400

    # Ensure only one scan is running
    if active_scan.status == "running" or active_scan.status == "paused":
        return jsonify({"error": "A scan is already active"}), 400

    # Read words
    try:
        with open(wordlist_path, 'r', encoding='utf-8', errors='ignore') as f:
            wordlist = f.readlines()
    except Exception as e:
        return jsonify({"error": f"Failed to read wordlist: {str(e)}"}), 500

    # Parse headers text block
    headers_dict = parse_headers(data.get("headers", ""))

    # Parse proxy
    proxy_host, proxy_port = parse_proxy(data.get("proxy", ""))

    # Validate target host is active and responsive before starting
    is_active, active_err = check_target_active(target_url, proxy=(proxy_host, proxy_port))
    if not is_active:
        return jsonify({"error": active_err}), 400

    # Set up ignore code list
    ignored_codes = parse_ignore_codes(data.get("ignoreCodes", ""))

    # Build credentials
    credentials = None
    http_user = data.get("httpUser", "")
    http_pass = data.get("httpPass", "")
    if http_user and http_pass:
        credentials = f"{http_user}:{http_pass}"

    # Build probe extensions
    probe_extensions = []
    extensions_mode = data.get("extensionsMode", "")
    if extensions_mode == "input":
        ext_str = data.get("extensionsInput", "")
        probe_extensions = parse_extensions(ext_str)
    elif extensions_mode == "file":
        ext_file_path = data.get("extensionsFilePath", "")
        if ext_file_path and os.path.exists(ext_file_path):
            try:
                with open(ext_file_path, "r") as ef:
                    probe_extensions = parse_extensions([line.strip() for line in ef if line.strip()])
            except Exception as e:
                print(f"[!] Extensions file reading error: {e}")

    # Build variations
    probe_variations = parse_variations(data.get("probeVariations") or data.get("variations", ""))

    # Extract additional settings
    follow_redirects = data.get("followRedirects", False)
    fine_tune_404 = data.get("fineTune404", False)
    use_path_as_is = data.get("usePathAsIs", False)
    output_file = data.get("outputFile")

    # Construct scan settings kwargs
    kwargs = {
        "num_workers": threads,
        "delay": delay,
        "user_agent": data.get("userAgent"),
        "cookie": data.get("cookies"),
        "headers": headers_dict,
        "proxy_host": proxy_host,
        "proxy_port": proxy_port,
        "proxy_username": data.get("proxyUser"),
        "proxy_password": data.get("proxyPass"),
        "credentials": credentials,
        "recursive": not data.get("noRecursive", False),
        "dont_force_slash": data.get("dontForceSlash", False),
        "ignore_case": data.get("ignoreCase", False),
        "dont_stop_on_warning": data.get("dontStopOnWarning", False),
        "cert": data.get("certPath"),
        "ignored_codes": ignored_codes,
        "probe_extensions": probe_extensions,
        "probe_variations": probe_variations,
        "ai_enabled": data.get("aiEnabled", False),
        "follow_redirects": follow_redirects,
        "fine_tune_404": fine_tune_404,
        "use_path_as_is": use_path_as_is,
        "rotate_user_agents": data.get("rotateUserAgents", False),
        "auto_pause": data.get("autoPause", True),
        "validate_cert": not data.get("insecure", False),
        "is_gui": True,
        "quiet": False,
        "output_file": output_file
    }

    # Add protocol scheme if not present
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "http://" + target_url

    # Check target connectivity/reachability
    from deepbuster import check_target_reachable
    reachable, err_msg = check_target_reachable(target_url)
    if not reachable:
        return jsonify({"error": f"Network/DNS Error: {err_msg}"}), 400

    # Write scan entry to SQLite
    scan_id = database.create_scan(target_url, wordlist_path, threads)
    
    # Reset active scan state
    active_scan.reset(scan_id, target_url)
    
    # Spawn thread to run asyncio event loop
    active_scan.thread = threading.Thread(
        target=run_scanner_loop,
        args=(target_url, wordlist, kwargs, scan_id)
    )
    active_scan.thread.daemon = True
    active_scan.thread.start()

    return jsonify({"status": "running", "scan_id": scan_id})

@app.route("/api/scan/pause", methods=["POST"])
def pause_scan():
    if active_scan.scanner and active_scan.loop:
        if active_scan.loop.is_closed():
            return jsonify({"error": "Scan has already completed or stopped"}), 400
        active_scan.loop.call_soon_threadsafe(active_scan.scanner.pause_event.clear)
        active_scan.status = "paused"
        database.update_scan_status(active_scan.scan_id, "paused")
        return jsonify({"status": "paused"})
    return jsonify({"error": "No active scan found"}), 400

@app.route("/api/scan/resume", methods=["POST"])
def resume_scan():
    if active_scan.scanner and active_scan.loop:
        if active_scan.loop.is_closed():
            return jsonify({"error": "Scan has already completed or stopped"}), 400
        active_scan.loop.call_soon_threadsafe(active_scan.scanner.pause_event.set)
        active_scan.scanner.paused_reason = None
        active_scan.scanner.consecutive_waf_blocks = 0
        active_scan.scanner.current_state = "running"
        active_scan.status = "running"
        database.update_scan_status(active_scan.scan_id, "running")
        return jsonify({"status": "running"})
    return jsonify({"error": "No active scan found"}), 400

@app.route("/api/scan/stop", methods=["POST"])
def stop_scan():
    if active_scan.scanner and active_scan.loop:
        if active_scan.loop.is_closed():
            active_scan.status = "stopped"
            return jsonify({"status": "stopped"})
        def stop_coro():
            active_scan.scanner.current_state = "stopped"
            # Drain queue items
            while not active_scan.scanner.queue.empty():
                try:
                    active_scan.scanner.queue.get_nowait()
                    active_scan.scanner.queue.task_done()
                except:
                    break
            # Resume pause event if paused so workers wake up and exit
            active_scan.scanner.pause_event.set()
            
            # Cancel all loop tasks
            for task in asyncio.all_tasks(active_scan.loop):
                task.cancel()
                
        active_scan.loop.call_soon_threadsafe(stop_coro)
        active_scan.status = "stopped"
        database.update_scan_status(active_scan.scan_id, "stopped", datetime.now().isoformat())
        
        # Cleanly stop the background scanner run loop thread
        if active_scan.thread and active_scan.thread.is_alive():
            try:
                active_scan.thread.join(timeout=3)
            except:
                pass
        return jsonify({"status": "stopped"})
    return jsonify({"error": "No active scan found"}), 400

@app.route("/api/scan/next-directory", methods=["POST"])
def next_directory():
    if active_scan.scanner and active_scan.loop:
        if active_scan.loop.is_closed():
            return jsonify({"error": "Scan has already completed or stopped"}), 400
        # Run next directory filter coroutine thread-safely in background event loop
        fut = asyncio.run_coroutine_threadsafe(
            active_scan.scanner.skip_current_directory(),
            active_scan.loop
        )
        try:
            skipped_dir, count = fut.result(timeout=5)
            return jsonify({
                "status": "success",
                "skipped_directory": skipped_dir,
                "count": count
            })
        except Exception as e:
            return jsonify({"error": f"Failed to skip directory: {str(e)}"}), 500
    return jsonify({"error": "No active scan found"}), 400

@app.route("/api/browse", methods=["GET"])
def browse_directory():
    current_path = request.args.get("path", "")
    if not current_path:
        current_path = os.getcwd()
    
    current_path = os.path.abspath(current_path)
    
    try:
        if not os.path.exists(current_path):
            return jsonify({"error": "Path does not exist"}), 400
        if not os.path.isdir(current_path):
            return jsonify({"error": "Path is not a directory"}), 400
            
        items = []
        
        # Add parent folder option
        parent_dir = os.path.dirname(current_path)
        if parent_dir != current_path:
            items.append({
                "name": "..",
                "path": parent_dir,
                "is_dir": True
            })
            
        # List items (directories first, then files)
        for entry in sorted(os.scandir(current_path), key=lambda e: (not e.is_dir(), e.name.lower())):
            # Skip hidden files
            if entry.name.startswith('.') and not entry.is_dir():
                continue
            items.append({
                "name": entry.name,
                "path": entry.path,
                "is_dir": entry.is_dir()
            })
            
        return jsonify({
            "current_path": current_path,
            "items": items
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/validate-file", methods=["GET"])
def validate_file():
    path = request.args.get("path", "")
    allow_new = request.args.get("allow_new", "false").lower() == "true"
    if not path:
        return jsonify({"valid": False, "reason": "Empty path"}), 200
    
    path = os.path.abspath(path)
    exists = os.path.exists(path)
    is_file = os.path.isfile(path)
    
    valid = (exists and is_file)
    if not exists and allow_new:
        parent_dir = os.path.dirname(path)
        if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
            valid = True
            
    return jsonify({
        "valid": valid,
        "exists": exists,
        "is_file": is_file
    })

@app.route("/api/scan/status", methods=["GET"])
def get_scan_status():
    if not active_scan.scan_id:
        return jsonify({"status": "idle"})
        
    snapshot = {}
    if active_scan.scanner:
        snapshot = active_scan.scanner.get_progress_snapshot()
        active_scan.ai_words_generated = snapshot.get("ai_words_generated", 0)
        active_scan.ai_words_list = snapshot.get("ai_words_list", [])
        if snapshot.get("is_paused", False) and active_scan.status == "running":
            active_scan.status = "paused"
            database.update_scan_status(active_scan.scan_id, "paused")

    return jsonify({
        "scan_id": active_scan.scan_id,
        "status": active_scan.status,
        "target_url": active_scan.target_url,
        "total_requests": active_scan.total_requests,
        "ai_words_generated": active_scan.ai_words_generated,
        "ai_words_list": active_scan.ai_words_list,
        "counts": active_scan.counts,
        "queue_size": snapshot.get("queue_size", 0),
        "ai_status": snapshot.get("ai_status", "Inactive"),
        "ai_tasks_count": snapshot.get("ai_tasks_count", 0),
        "results_count": len(active_scan.results),
        "paused_reason": snapshot.get("paused_reason", None),
        "current_directory": active_scan.scanner.get_current_scanning_directory() if active_scan.scanner else "/"
    })

@app.route("/api/scan/results", methods=["GET"])
def get_results():
    return jsonify(active_scan.results)

@app.route("/api/config/ai", methods=["GET", "POST"])
def manage_ai_config():
    config_path = "config.json"
    if request.method == "POST":
        data = request.json or {}
        try:
            # Read existing config.json to preserve non-AI structures
            current_config = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    current_config = json.load(f)
            
            # Update values
            if "llm" not in current_config:
                current_config["llm"] = {}
            
            llm = current_config["llm"]
            llm["enabled"] = bool(data.get("enabled", True))
            llm["base_url"] = data.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
            llm["api_key"] = data.get("api_key", "")
            llm["model"] = data.get("model", "gemini-2.5-flash")
            llm["temperature"] = float(data.get("temperature", 0.3))
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(current_config, f, indent=4)
            
            return jsonify({"status": "success", "config": current_config})
        except Exception as e:
            return jsonify({"error": f"Failed to save config: {str(e)}"}), 500
            
    else:
        # GET request
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                llm = config_data.get("llm", {})
                return jsonify({
                    "enabled": llm.get("enabled", True),
                    "base_url": llm.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/"),
                    "api_key": llm.get("api_key", ""),
                    "model": llm.get("model", "gemini-2.5-flash"),
                    "temperature": llm.get("temperature", 0.3)
                })
            else:
                return jsonify({
                    "enabled": False,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "api_key": "",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.3
                })
        except Exception as e:
            return jsonify({"error": f"Failed to load config: {str(e)}"}), 500

@app.route("/api/scan/history", methods=["GET"])
def get_history():
    history = database.get_scans_history()
    return jsonify(history)

@app.route("/api/scan/<int:scan_id>/results", methods=["GET"])
def get_scan_db_results(scan_id):
    results = database.get_scan_results(scan_id)
    return jsonify(results)

@app.route("/api/visual-capture", methods=["POST"])
def visual_capture():
    data = request.json or {}
    url = data.get("url")
    path = data.get("path")
    scan_id = data.get("scanId")
    
    if not url or not path:
        return jsonify({"error": "URL and path are required"}), 400
        
    # Create static/screenshots directory
    screenshot_dir = os.path.join(app.static_folder, "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # Base output filename prefix without extension
    file_prefix = f"evidence_{int(time.time())}_{path.replace('/', '_').replace('.', '_')}"
    output_path_base = os.path.join(screenshot_dir, file_prefix)
    
    # Run screenshot capture in a separate thread to avoid blocking Flask
    def async_capture():
        fmt = take_screenshot(url, output_path_base)
        if fmt:
            final_filename = f"{file_prefix}.{fmt}"
            static_url = f"/static/screenshots/{final_filename}"
            print(f"[+] Screenshot captured successfully for {url} ({fmt}) -> {final_filename}")
            
            # Save visual capture path to active scan results memory cache if it's currently loaded
            if active_scan.scan_id == scan_id:
                for item in active_scan.results:
                    if item.get("path") == path:
                        item["screenshot_path"] = static_url
                        break
                        
            # Save/Update in DB so it is persistent across reload and View DB Logs
            if scan_id is not None:
                try:
                    database.update_screenshot_path(scan_id, path, static_url)
                except Exception as db_err:
                    print(f"[!] Database update of screenshot failed: {db_err}")
            
    threading.Thread(target=async_capture).start()
    
    return jsonify({
        "status": "queued",
        "fileName": file_prefix,
    })

@app.route("/api/screenshot/status", methods=["GET"])
def screenshot_status():
    scan_id = request.args.get("scanId")
    path = request.args.get("path")
    if not scan_id or not path:
        return jsonify({"error": "scanId and path are required"}), 400
        
    try:
        scan_id = int(scan_id)
    except ValueError:
        return jsonify({"error": "scanId must be integer"}), 400
        
    # Query database for screenshot path
    results = database.get_scan_results(scan_id)
    for res in results:
        if res.get("path") == path:
            screenshot_path = res.get("screenshot_path")
            if screenshot_path:
                return jsonify({"status": "ready", "screenshot_path": screenshot_path})
            else:
                return jsonify({"status": "pending"})
                
    return jsonify({"status": "not_found"})

def find_free_port(start_port):
    port = start_port
    while port < 65535:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except OSError:
            port += 1
    return start_port



def start_gui_server(port=4440):
    ensure_playwright_installed()
    default_port = port
    active_port = find_free_port(default_port)
    
    print("\n============================================================")
    print(f"\u001b[32;1m🚀 Launching Deepbuster Web GUI on: http://127.0.0.1:{active_port}\u001b[0m")
    print("============================================================\n")
    
    # Run Flask production WSGI server (or development server with threaded=True)
    app.run(host="127.0.0.1", port=active_port, debug=False, threaded=True)
