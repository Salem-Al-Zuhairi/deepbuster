#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
import platform

MIN_PYTHON_VERSION = (3, 10)

if sys.version_info < MIN_PYTHON_VERSION:
    current_version_str = ".".join(map(str, sys.version_info[:3]))
    min_version_str = ".".join(map(str, MIN_PYTHON_VERSION))
    print(f"\n\u001b[31;1m[!] Error: Deepbuster requires Python {min_version_str} or higher to run.\u001b[0m")
    print(f"\u001b[33;1m[*] Your current version is {current_version_str}.\u001b[0m\n")
    
    try:
        choice = input("Would you like Deepbuster to automatically install/upgrade Python for your system? (y/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        choice = "n"
        
    if choice in ['y', 'yes']:
        system_platform = platform.system().lower()
        print(f"[*] Detecting system platform: {system_platform}")
        
        try:
            if "linux" in system_platform:
                if os.path.exists("/usr/bin/apt"):
                    print("[*] Running 'sudo apt update && sudo apt install -y python3'...")
                    os.system("sudo apt update && sudo apt install -y python3")
                elif os.path.exists("/usr/bin/pacman"):
                    print("[*] Running 'sudo pacman -Syu python'...")
                    os.system("sudo pacman -Syu python")
                elif os.path.exists("/usr/bin/dnf"):
                    print("[*] Running 'sudo dnf upgrade python3'...")
                    os.system("sudo dnf upgrade python3")
                elif os.path.exists("/usr/bin/yum"):
                    print("[*] Running 'sudo yum update python3'...")
                    os.system("sudo yum update python3")
                else:
                    print("[!] No recognized package manager found. Please install Python manually.")
                    sys.exit(1)
            elif "darwin" in system_platform:
                if os.path.exists("/usr/local/bin/brew") or os.path.exists("/opt/homebrew/bin/brew"):
                    print("[*] Running 'brew install python'...")
                    os.system("brew install python")
                else:
                    print("[!] Homebrew not found. Please install Homebrew or Python manually.")
                    sys.exit(1)
            elif "windows" in system_platform:
                print("[*] Downloading Python Windows installer...")
                import urllib.request
                import tempfile
                installer_url = "https://www.python.org/ftp/python/3.11.4/python-3.11.4-amd64.exe"
                temp_dir = tempfile.gettempdir()
                installer_path = os.path.join(temp_dir, "python_installer.exe")
                print(f"[*] Downloading {installer_url} to {installer_path}...")
                urllib.request.urlretrieve(installer_url, installer_path)
                print("[*] Launching installer. Please follow the prompt to complete installation.")
                os.system(installer_path)
            else:
                print(f"[!] Unsupported operating system: {system_platform}. Please install Python manually.")
                sys.exit(1)
                
            print("\n\u001b[32;1m[+] Python installation/upgrade process completed.\u001b[0m")
            print("[*] Please restart your terminal/session and run the script again.")
            sys.exit(0)
        except Exception as e:
            print(f"\n\u001b[31;1m[!] Error during installation: {e}\u001b[0m")
            sys.exit(1)
    else:
        print("[*] Exiting. Please install Python manually.")
        sys.exit(1)

import argparse
import io
import uuid
import ssl
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
import asyncio
from typing import Iterable, Any, Callable, Awaitable
import urllib.parse
from ai_engine import DeepbusterAIEngine
from datetime import datetime

def parse_headers(headers_input):
    headers_dict = {}
    if not headers_input:
        return headers_dict
    
    if isinstance(headers_input, list):
        for header in headers_input:
            if ':' in header:
                k, v = header.split(':', 1)
                headers_dict[k.strip()] = v.strip()
    elif isinstance(headers_input, dict):
        for k, v in headers_input.items():
            headers_dict[str(k).strip()] = str(v).strip()
    elif isinstance(headers_input, str):
        for line in headers_input.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                headers_dict[k.strip()] = v.strip()
    return headers_dict

def parse_proxy(proxy_input):
    if not proxy_input:
        return None, None
    if isinstance(proxy_input, str):
        proxy_input = proxy_input.strip()
        if not proxy_input:
            return None, None
        if ":" in proxy_input:
            host, port = proxy_input.split(":", 1)
            try:
                return host.strip(), int(port.strip())
            except ValueError:
                return host.strip(), 1080
        return proxy_input, 1080
    return None, None

def parse_ignore_codes(ignore_input):
    ignored_codes = [404]
    if not ignore_input:
        return ignored_codes
    
    if isinstance(ignore_input, list):
        ignored_codes = []
        for item in ignore_input:
            if isinstance(item, int):
                ignored_codes.append(item)
            elif isinstance(item, str):
                for code in item.split(','):
                    cleaned = code.strip()
                    if cleaned:
                        try:
                            ignored_codes.append(int(cleaned))
                        except ValueError:
                            pass
    elif isinstance(ignore_input, str):
        ignored_codes = []
        for code in ignore_input.split(','):
            cleaned = code.strip()
            if cleaned:
                try:
                    ignored_codes.append(int(cleaned))
                except ValueError:
                    pass
    elif isinstance(ignore_input, (int, float)):
        ignored_codes = [int(ignore_input)]
    return ignored_codes

def parse_extensions(ext_input):
    probe_extensions = []
    if not ext_input:
        return probe_extensions
    
    if isinstance(ext_input, list):
        for item in ext_input:
            item_str = str(item).strip()
            if item_str:
                if not item_str.startswith('.'):
                    item_str = '.' + item_str
                probe_extensions.append(item_str)
    elif isinstance(ext_input, str):
        for ext in ext_input.split(','):
            cleaned = ext.strip()
            if cleaned:
                if not cleaned.startswith('.'):
                    cleaned = '.' + cleaned
                probe_extensions.append(cleaned)
    return probe_extensions

def parse_variations(var_input):
    probe_variations = []
    if not var_input:
        return probe_variations
    
    if isinstance(var_input, list):
        for item in var_input:
            item_str = str(item).strip()
            if item_str:
                probe_variations.append(item_str)
    elif isinstance(var_input, str):
        for var in var_input.split(','):
            cleaned = var.strip()
            if cleaned:
                probe_variations.append(cleaned)
    return probe_variations

def save_output(output_file, results, is_csv=False, base_url=""):
    try:
        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        print(f"[!] Failed to create output directory: {e}")

    try:
        with open(output_file, 'w+', encoding='utf-8', errors='ignore') as output:
            if is_csv:
                ESC_QUOTES = str.maketrans({'"': r'\"'})
                FIELDS = ['status_code', 'path', 'response_size', 'effective_url', 'headers']
                output.write(f'''{';'.join(FIELDS)}\n''')
                for result in results:
                    headers_str = ""
                    if result.get('headers'):
                        if isinstance(result['headers'], dict):
                            headers_str = ','.join([f'"{h.translate(ESC_QUOTES)}:{v.translate(ESC_QUOTES)}"' for (h, v) in result['headers'].items()])
                        else:
                            headers_str = ','.join([f'"{h.translate(ESC_QUOTES)}:{v.translate(ESC_QUOTES)}"' for (h, v) in result['headers']])
                    output.write(f'''{result['status_code']};"{result['path'].translate(ESC_QUOTES)}";{result.get('response_size', 0)};"{result.get('effective_url', '').translate(ESC_QUOTES)}";{headers_str}\n''')
            else:
                output.write("========================= RESULTS ==========================\n")
                alive = [r for r in results if r['status_code'] == 200]
                if len(alive) == 0:
                    output.write("NOTHING FOUND 🧐\n")
                else:
                    output.write(f"Found {len(alive)} accessible URL(s):\n")
                    for d in alive:
                        size_val = d.get('response_size', 0)
                        if size_val < 1024:
                            size_str = f"{size_val} B"
                        elif size_val < 1024 * 1024:
                            size_str = f"{size_val / 1024:.2f} KB"
                        else:
                            size_str = f"{size_val / (1024 * 1024):.2f} MB"
                        output.write(f"  [+] {base_url}{d['path']} (Size: {size_str})\n")
                output.write("============================================================\n")
    except Exception as e:
        print(f"[!] Failed to write output file: {e}")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.1; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0"
]

class Deepbuster:
    found_callback: Callable[..., Awaitable[Any]] | None
    error_callback: Callable[..., Awaitable[Any]] | None
    pre_fetch_callback: Callable[..., Awaitable[Any]] | None

    def __init__(self, base_url: str, **kwargs) -> None:
        self.base_url = base_url
        self.rotate_user_agents = kwargs.get('rotate_user_agents', False)
        self.auto_pause = kwargs.get('auto_pause', True)
        self.validate_cert = kwargs.get('validate_cert', True)
        self.is_gui = kwargs.get('is_gui', False)
        self.consecutive_waf_blocks = 0
        self.waf_block_threshold = 20
        self.paused_reason = None
        self.found_callback = kwargs.get('found_callback', None)
        self.error_callback = kwargs.get('error_callback', None)
        self.pre_fetch_callback = kwargs.get('pre_fetch_callback', None)
        self.user_agent = kwargs.get('user_agent', None)
        self.follow_redirects = kwargs.get('follow_redirects', False)
        self.dont_force_slash = kwargs.get('dont_force_slash', False)
        self.dont_stop_on_warning = kwargs.get('dont_stop_on_warning', False)
        self.ignore_case = kwargs.get('ignore_case', False)
        self.delay = kwargs.get('delay', 0)
        self.ignored_codes = set(parse_ignore_codes(kwargs.get('ignored_codes', [])))
        self.use_path_as_is = kwargs.get('use_path_as_is', False)
        self.fine_tune_404 = kwargs.get('fine_tune_404', False)
        self.custom_404_lengths = set()
        self.custom_404_base_sizes = set()
        self.ssl_ctx = None
        cert_arg = kwargs.get('cert', None)
        if cert_arg:
            self.ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            if ',' in cert_arg:
                cert_file, key_file = cert_arg.split(',', 1)
                self.ssl_ctx.load_cert_chain(certfile=cert_file.strip(), keyfile=key_file.strip())
            else:
                self.ssl_ctx.load_cert_chain(certfile=cert_arg.strip())
        self.recursive = kwargs.get('recursive', True)
        self.scanned_directories = set(['/'])
        self.print_lock = asyncio.Lock()
        self.wordlist = []
        self.ai_enabled = kwargs.get('ai_enabled', False)
        self.ai_engine = None
        self.ai_tasks = set()
        self.ai_unchecked_words = []
        self.current_ai_status = "Inactive"
        self.ai_words_generated = 0
        self.ai_generated_words_list = []
        
        if self.ai_enabled:
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(self.base_url)
                netloc = parsed_url.netloc or parsed_url.path
                domain_clean = netloc.replace(":", "_").replace("/", "_").strip()
                if not domain_clean:
                    domain_clean = "target"
            except Exception:
                domain_clean = "target"
            
            custom_wordlist = f"{domain_clean}_ai_wordlist.txt"
            self.ai_engine = DeepbusterAIEngine(wordlist_path=custom_wordlist)
            
            if not self.ai_engine.enabled:
                print("\n\u001b[33;1m[!] Warning: AI Engine is disabled or config.json is not populated.\u001b[0m")
                print("\u001b[33;1m[!] Please fill in your API key in config.json and set \"enabled\": true.\u001b[0m")
                self.ai_enabled = False
            else:
                self.ai_unchecked_words = self.ai_engine.load_state_unchecked_words()
                self.current_ai_status = "Initialized"
        self.probe_extensions = parse_extensions(kwargs.get('probe_extensions', []))
        self.probe_variations = parse_variations(kwargs.get('probe_variations', []))
        self.cookie = kwargs.get('cookie', None) or kwargs.get('cookies', None)
        self.headers = parse_headers(kwargs.get('headers', None))
        credentials = kwargs.get('credentials', None)
        self.auth_user_name, self.auth_password = credentials.split(':', 1) \
            if isinstance(credentials, str) else (None, None)
        self.queue = asyncio.Queue()
        self.num_workers = kwargs.get('num_workers', 10)
        self.results = []
        
        # Concurrency, control, and state management
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.total_requests = 0
        self.current_state = "running"
        self.visited_paths = set()
        
        # Proxy configuration
        self.proxy_host = kwargs.get('proxy_host', None)
        self.proxy_port = kwargs.get('proxy_port', None)
        if self.proxy_host and not self.proxy_port and ':' in self.proxy_host:
            self.proxy_host, self.proxy_port = parse_proxy(self.proxy_host)
        if self.proxy_port is not None:
            try:
                self.proxy_port = int(self.proxy_port)
            except ValueError:
                self.proxy_port = None
        self.proxy_username = kwargs.get('proxy_username', None)
        self.proxy_password = kwargs.get('proxy_password', None)

    def track_response_code(self, code: int) -> None:
        if not self.auto_pause:
            return
        if code in [403, 429]:
            self.consecutive_waf_blocks += 1
            if self.consecutive_waf_blocks >= self.waf_block_threshold:
                if self.current_state != "paused":
                    self.current_state = "paused"
                    self.paused_reason = "waf_block"
                    self.pause_event.clear()
                    
                    is_gui = getattr(self, 'is_gui', False)
                    if not is_gui:
                        asyncio.create_task(self.safe_print(
                            f"\n\u001b[31;1m[!] WAF Block Detected! (Received {self.consecutive_waf_blocks} consecutive {code} responses). Scanning paused automatically.\u001b[0m\n"
                        ))
                        asyncio.create_task(self.wait_for_resume())
                    else:
                        asyncio.create_task(self.safe_print(
                            f"\n\u001b[31;1m[!] WAF Block Detected! (Received {self.consecutive_waf_blocks} consecutive {code} responses). Scanning paused automatically.\u001b[0m\n"
                            f"\u001b[33m[i] You can resume the scan from the Web GUI.\u001b[0m\n"
                        ))
        else:
            self.consecutive_waf_blocks = 0

    async def wait_for_resume(self):
        await self.safe_print("\u001b[33m[i] Press [Enter] to resume the scan...\u001b[0m")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sys.stdin.readline)
        self.consecutive_waf_blocks = 0
        self.paused_reason = None
        self.current_state = "running"
        self.pause_event.set()
        await self.safe_print("\u001b[32;1m[+] Resuming scan...\u001b[0m")

    async def check_wildcard(self) -> bool:
        # Generate two completely unique, dynamic, and random nonexistent paths
        p1 = f"/{uuid.uuid4().hex}"
        p2 = f"/{uuid.uuid4().hex}_{uuid.uuid4().hex}"
        
        has_wildcard = False
        try:
            http_client = self.http_client
            headers = dict(self.headers) if self.headers else {}
            if self.cookie:
                headers['Cookie'] = self.cookie

            # Fetch the first random path
            req1 = HTTPRequest(f"{self.base_url}{p1}",
                               user_agent=self.user_agent,
                               headers=headers,
                               auth_username=self.auth_user_name,
                               auth_password=self.auth_password,
                               follow_redirects=self.follow_redirects,
                               ssl_options=self.ssl_ctx,
                               validate_cert=self.validate_cert,
                               proxy_host=self.proxy_host,
                               proxy_port=self.proxy_port,
                               proxy_username=self.proxy_username,
                               proxy_password=self.proxy_password)
            r1 = await http_client.fetch(req1)
            
            if r1.code == 200:
                has_wildcard = True
                if self.fine_tune_404:
                    self.custom_404_lengths.add(len(r1.body))
                    # Save the normalized base size (subtracting path length) in case the path is reflected in the HTML
                    self.custom_404_base_sizes.add(len(r1.body) - len(p1))
 
                # Fetch the second random path to detect dynamic/reflected soft 404s
                req2 = HTTPRequest(f"{self.base_url}{p2}",
                                   user_agent=self.user_agent,
                                   headers=headers,
                                   auth_username=self.auth_user_name,
                                   auth_password=self.auth_password,
                                   follow_redirects=self.follow_redirects,
                                   ssl_options=self.ssl_ctx,
                                   validate_cert=self.validate_cert,
                                   proxy_host=self.proxy_host,
                                   proxy_port=self.proxy_port,
                                   proxy_username=self.proxy_username,
                                   proxy_password=self.proxy_password)
                r2 = await http_client.fetch(req2)
                if r2.code == 200:
                    if self.fine_tune_404:
                        self.custom_404_lengths.add(len(r2.body))
                        self.custom_404_base_sizes.add(len(r2.body) - len(p2))
        except Exception:
            pass
        return has_wildcard
 
    async def trigger_ai_analysis(self, path, response_headers=None, response_body=None):
        if not self.ai_enabled or not self.ai_engine:
            return
            
        # If headers/body are missing, we issue a quick async request to get them (e.g. for bootstrapping)
        if not response_headers and not response_body:
            try:
                self.current_ai_status = f"Bootstrapping {path}"
                http_client = self.http_client
                url = f"{self.base_url}{path}"
                headers = dict(self.headers) if self.headers else {}
                if self.cookie:
                    headers['Cookie'] = self.cookie
                req = HTTPRequest(url,
                                  user_agent=self.user_agent,
                                  headers=headers,
                                  auth_username=self.auth_user_name,
                                  auth_password=self.auth_password,
                                  follow_redirects=self.follow_redirects,
                                  ssl_options=self.ssl_ctx,
                                  validate_cert=self.validate_cert,
                                  proxy_host=self.proxy_host,
                                  proxy_port=self.proxy_port,
                                  proxy_username=self.proxy_username,
                                  proxy_password=self.proxy_password)
                response = await http_client.fetch(req)
                response_headers = response.headers
                response_body = response.body
            except Exception as e:
                if self.ai_engine:
                    self.ai_engine.logger.error(f"Failed to bootstrap fetch for {path}: {e}")
                return
                
        self.current_ai_status = f"Analyzing {path}"
        words = await self.ai_engine.analyze(path, response_headers, response_body)
        if words:
            self.current_ai_status = f"Injecting {len(words)} AI words"
            for word in words:
                word_clean = word.strip().strip("/")
                if word_clean and word_clean not in self.ai_generated_words_list:
                    self.ai_generated_words_list.append(word_clean)
            self.ai_words_generated = len(self.ai_generated_words_list)
            # Cross-pollination: test generated words in all scanned directories!
            for directory in list(self.scanned_directories):
                # Ensure directory ends with '/' for clean merging
                base_dir = directory if directory.endswith('/') else f"{directory}/"
                for word in words:
                    # Clean up prefix slash
                    clean_word = word[1:] if word.startswith('/') else word
                    await self.queue.put(f"{base_dir}{clean_word}")
                    
        self.current_ai_status = "Idle"

    async def run(self, paths: Iterable[str]) -> None:
        self.current_state = "running"
        self.http_client = AsyncHTTPClient(max_clients=max(200, self.num_workers))
        has_wildcard = await self.check_wildcard()
        if has_wildcard:
            print("\n\u001b[33;1mWARNING: Active response on random HTTP requests! (Wildcard detected)\u001b[0m")
            if not self.dont_stop_on_warning and not self.fine_tune_404:
                print("\u001b[31;1m[-] Stopping scan because -W and -f are NOT set.\u001b[0m")
                return
            elif self.fine_tune_404:
                print("\u001b[32;1m[+] Continuing scan anyway because -f (Fine-tune 404) is enabled to filter soft 404s.\u001b[0m")
            else:
                print("\u001b[32;1m[+] Continuing scan anyway because -W is set.\u001b[0m")

        # Bootstrap Homepage immediately if AI is enabled
        if self.ai_enabled:
            task = asyncio.create_task(self.trigger_ai_analysis("/", None, None))
            self.ai_tasks.add(task)
            task.add_done_callback(self.ai_tasks.discard)
            
            # Load state of unchecked words from previous runs
            if self.ai_unchecked_words:
                for word in self.ai_unchecked_words:
                    await self.queue.put(word)

        # sanitize input stream
        if self.ignore_case:
            paths = set([path.strip().lower() for path in paths])
        else:
            paths = set([path.strip() for path in paths])
        self.wordlist = list(paths)
        for url in paths:
            await self.queue.put(url)
            for ext in self.probe_extensions:
                await self.queue.put(f'{url}{ext}')
        # spawn workers
        workers = [asyncio.create_task(self.worker()) # workers is the number of concurrent threads
                   for _ in range(self.num_workers)]
        # wait for initial queue to be processed
        await self.queue.join()
        
        # Drain all background AI tasks that might inject more paths
        while len(self.ai_tasks) > 0:
            self.current_ai_status = f"Waiting for {len(self.ai_tasks)} AI task(s)"
            # Wait for currently running AI tasks to finish with a maximum timeout of 15 seconds
            try:
                await asyncio.wait_for(
                    asyncio.gather(*list(self.ai_tasks), return_exceptions=True),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                print("\n[!] AI tasks wait timed out after 15 seconds. Proceeding to finish scan.")
                break
            # Re-join queue in case those AI tasks added new paths
            await self.queue.join()
            
            self.current_ai_status = "Done"
        self.current_state = "completed"

        for worker in workers:
            worker.cancel()

    async def try_url(self) -> None:
        await self.pause_event.wait()
        if self.current_state == "stopped":
            return
        if self.delay > 0:
            await asyncio.sleep(self.delay / 1000.0)
        if self.current_state == "stopped":
            return
        path = await self.queue.get()
        if self.current_state == "stopped":
            self.queue.task_done()
            return
            
        got_path = True
        try:
            if not self.use_path_as_is:
                if not path.startswith('/'):
                    path = '/' + path
                if not self.dont_force_slash and not path.endswith('/'):
                    # Only append slash if there's no extension in the last path segment
                    last_segment = path.split('/')[-1]
                    if '.' not in last_segment:
                        path = path + '/'
            
            # Deduplicate using self.visited_paths
            if path in self.visited_paths:
                return
            self.visited_paths.add(path)

            # Construct URL by quoting the path correctly (keeping slashes)
            quoted_path = urllib.parse.quote(path, safe='/')
            url = f'{self.base_url}{quoted_path}'
            if callable(self.pre_fetch_callback):
                await self.pre_fetch_callback(path)
            
            http_client = self.http_client
            headers = dict(self.headers) if self.headers else {}
            if 'Connection' not in headers:
                headers['Connection'] = 'close'
            if self.cookie:
                headers['Cookie'] = self.cookie

            user_agent = self.user_agent
            if self.rotate_user_agents:
                import random
                user_agent = random.choice(USER_AGENTS)

            req = HTTPRequest(url,
                              user_agent=user_agent,
                              headers=headers,
                              auth_username=self.auth_user_name,
                              auth_password=self.auth_password,
                              follow_redirects=self.follow_redirects,
                              ssl_options=self.ssl_ctx,
                              validate_cert=self.validate_cert,
                              proxy_host=self.proxy_host,
                              proxy_port=self.proxy_port,
                              proxy_username=self.proxy_username,
                              proxy_password=self.proxy_password,
                              connect_timeout=10.0,
                              request_timeout=10.0)
            
            # Retry loop for 599 timeouts or network dropouts
            max_retries = 2
            attempt = 0
            response = None
            while attempt <= max_retries:
                try:
                    if attempt > 0:
                        await asyncio.sleep(0.1 * attempt)
                    self.total_requests += 1
                    response = await http_client.fetch(req)
                    break
                except HTTPClientError as e:
                    if e.code == 599 and attempt < max_retries:
                        attempt += 1
                        self.total_requests -= 1
                        continue
                    raise e
                except Exception as e:
                    if attempt < max_retries:
                        attempt += 1
                        self.total_requests -= 1
                        continue
                    raise e
            self.track_response_code(response.code)
            if response.code in self.ignored_codes:
                return
            # print([i for i in response.headers.get_all()])

            # Extract body size with Content-Length fallback
            body_len = len(response.body) if response.body else 0
            if body_len == 0 and response.headers:
                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        body_len = int(content_length)
                    except ValueError:
                        pass

            if response.code == 200 and self.fine_tune_404:
                normalized_len = body_len - len(path)
                
                # Check if the exact length or normalized length matches known nonexistent sizes
                if body_len in self.custom_404_lengths or normalized_len in self.custom_404_base_sizes:
                    # To prevent false positives (a real page having the same size coincidentally),
                    # we verify if common 404-related terms are present in the response body
                    body_lower = response.body.lower() if response.body else b''
                    keywords = [b'not found', b'error', b'404', b'does not exist', b'cannot find', b'invalid']
                    has_404_keyword = any(kw in body_lower for kw in keywords)
                    
                    if has_404_keyword:
                        if callable(self.error_callback):
                            await self.error_callback(f'{path} -> Ignored (Soft 404 matching nonexistent size and signature)', 404, body_len)
                        self.results.append({
                            'path': path,
                            'effective_url': response.effective_url,
                            'status_code': 404,
                            'response_size': body_len,
                            'headers': [header for header in response.headers.get_all()],
                        })
                        return

            self.results.append({
                'path': path,
                'effective_url': response.effective_url,
                'status_code': response.code,
                'response_size': body_len,
                'headers': [header for header in response.headers.get_all()],
            })

            if self.ai_enabled and response.code in [200, 301, 302]:
                task = asyncio.create_task(self.trigger_ai_analysis(path, response.headers, response.body))
                self.ai_tasks.add(task)
                task.add_done_callback(self.ai_tasks.discard)

            if response.code in [200, 301, 302]:
                if path.endswith('/'):
                    await self.handle_recursive_directory(path)

            if response.code == 200:
                for ext 