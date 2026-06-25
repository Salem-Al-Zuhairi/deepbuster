#!/usr/bin/env python3

import argparse
import sys
import io
import uuid
import ssl
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
import asyncio
from typing import Iterable, Any, Callable, Awaitable
import urllib.parse
from ai_engine import DeepbusterAIEngine
import os
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
                FIELDS = ['status_code', 'path', 'effective_url', 'headers']
                output.write(f'''{';'.join(FIELDS)}\n''')
                for result in results:
                    headers_str = ""
                    if result.get('headers'):
                        if isinstance(result['headers'], dict):
                            headers_str = ','.join([f'"{h.translate(ESC_QUOTES)}:{v.translate(ESC_QUOTES)}"' for (h, v) in result['headers'].items()])
                        else:
                            headers_str = ','.join([f'"{h.translate(ESC_QUOTES)}:{v.translate(ESC_QUOTES)}"' for (h, v) in result['headers']])
                    output.write(f'''{result['status_code']};"{result['path'].translate(ESC_QUOTES)}";"{result.get('effective_url', '').translate(ESC_QUOTES)}";{headers_str}\n''')
            else:
                output.write("========================= RESULTS ==========================\n")
                alive = [r for r in results if r['status_code'] == 200]
                if len(alive) == 0:
                    output.write("NOTHING FOUND 🧐\n")
                else:
                    output.write(f"Found {len(alive)} accessible URL(s):\n")
                    for d in alive:
                        output.write(f"  [+] {base_url}{d['path']}\n")
                output.write("============================================================\n")
    except Exception as e:
        print(f"[!] Failed to write output file: {e}")

class Deepbuster:
    found_callback: Callable[..., Awaitable[Any]] | None
    error_callback: Callable[..., Awaitable[Any]] | None
    pre_fetch_callback: Callable[..., Awaitable[Any]] | None

    def __init__(self, base_url: str, **kwargs) -> None:
        self.base_url = base_url
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

    async def check_wildcard(self) -> bool:
        # Generate two completely unique, dynamic, and random nonexistent paths
        p1 = f"/{uuid.uuid4().hex}"
        p2 = f"/{uuid.uuid4().hex}_{uuid.uuid4().hex}"
        
        has_wildcard = False
        try:
            http_client = AsyncHTTPClient()
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
                http_client = AsyncHTTPClient()
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
            
            http_client = AsyncHTTPClient()
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
                              proxy_host=self.proxy_host,
                              proxy_port=self.proxy_port,
                              proxy_username=self.proxy_username,
                              proxy_password=self.proxy_password,
                              connect_timeout=10.0,
                              request_timeout=10.0)
            response = await http_client.fetch(req)
            if response.code in self.ignored_codes:
                return
            # print([i for i in response.headers.get_all()])

            if response.code == 200 and self.fine_tune_404:
                body_len = len(response.body)
                normalized_len = body_len - len(path)
                
                # Check if the exact length or normalized length matches known nonexistent sizes
                if body_len in self.custom_404_lengths or normalized_len in self.custom_404_base_sizes:
                    # To prevent false positives (a real page having the same size coincidentally),
                    # we verify if common 404-related terms are present in the response body
                    body_lower = response.body.lower()
                    keywords = [b'not found', b'error', b'404', b'does not exist', b'cannot find', b'invalid']
                    has_404_keyword = any(kw in body_lower for kw in keywords)
                    
                    if has_404_keyword:
                        if callable(self.error_callback):
                            await self.error_callback(f'{path} -> Ignored (Soft 404 matching nonexistent size and signature)', 404, len(response.body))
                        self.results.append({
                            'path': path,
                            'effective_url': response.effective_url,
                            'status_code': 404,
                            'headers': [header for header in response.headers.get_all()],
                        })
                        return

            self.results.append({
                'path': path,
                'effective_url': response.effective_url,
                'status_code': response.code,
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
                for ext in self.probe_variations:
                    await self.queue.put(f'{path}{ext}')
            # يتم تنفيذ هذا الشرط  في كل الاحوال طالما انه تم الوصول الى الخادم مثل http 200 301 302
            # وفي حال لم يتم الرد يتم تنفيذ الشرط الموجود في exception مثل error 404 500
            if callable(self.found_callback):
                await self.found_callback(path, response.code, len(response.body))
        except HTTPClientError as e:
            if e.code in self.ignored_codes:
                return
            # print(f'{e.response} for {path}')
            body_len = len(e.response.body) if e.response else 0
            if callable(self.error_callback):
                await self.error_callback(path, e.code, body_len)
            self.results.append({
                'path': path,
                'effective_url': '',
                'status_code': e.code,
                'headers': [],
            })
        except Exception as e:
            await self.safe_print(f"\u001b[31;1m[!] Request exception for {path}: {e}\u001b[0m")
            if callable(self.error_callback):
                await self.error_callback(path, 0, 0)
            self.results.append({
                'path': path,
                'effective_url': '',
                'status_code': 0,
                'headers': [],
            })
        finally:
            if got_path:
                self.queue.task_done()

    async def worker(self) -> None:
        while True:
            try:
                await self.try_url()
            except asyncio.CancelledError:
                return
            except Exception as e:
                await self.safe_print(f"\u001b[31;1m[!] Worker outer loop error: {e}\u001b[0m")

    async def handle_recursive_directory(self, path: str) -> None:
        if path in self.scanned_directories:
            return
        
        self.scanned_directories.add(path)
        
        should_recurse = self.recursive
        
        # If user skips recursion or recursive is disabled, we keep the path in scanned_directories to avoid re-prompting/re-processing
        if should_recurse:
            await self.safe_print(f"\u001b[34;1m[+] Adding recursive scan for directory: {path}\u001b[0m")
            for word in self.wordlist:
                clean_word = word[1:] if word.startswith('/') else word
                await self.queue.put(f"{path}{clean_word}")

    async def safe_print(self, msg: str) -> None:
        async with self.print_lock:
            sys.stdout.write(f"\r\u001b[0K{msg}\n")
            sys.stdout.flush()

    @property
    def result(self) -> Iterable[str]:
        return self.results

    def alive(self) -> Iterable[str]:
        return [r for r in self.results if r['status_code'] == 200]

    def get_current_scanning_directory(self) -> str:
        if not self.queue.empty():
            # In asyncio.Queue, _queue is a deque
            first_item = self.queue._queue[0]
            last_slash_idx = first_item.rfind('/')
            if last_slash_idx > 0:
                return first_item[:last_slash_idx + 1]
        return '/'

    async def skip_current_directory(self):
        dir_to_skip = self.get_current_scanning_directory()
        new_items = []
        skipped_count = 0
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                self.queue.task_done()
                if item.startswith(dir_to_skip):
                    skipped_count += 1
                else:
                    new_items.append(item)
            except asyncio.QueueEmpty:
                break
        
        for item in new_items:
            await self.queue.put(item)
            
        return dir_to_skip, skipped_count

    def get_progress_snapshot(self):
        return {
            "total_requests": getattr(self, 'total_requests', 0),
            "queue_size": self.queue.qsize(),
            "scanned_dirs": list(self.scanned_directories),
            "ai_status": getattr(self, 'current_ai_status', 'Inactive'),
            "ai_tasks_count": len(getattr(self, 'ai_tasks', [])),
            "results_count": len(self.results),
            "is_paused": not self.pause_event.is_set(),
            "status": getattr(self, 'current_state', 'running')
        }


async def main(base_url: str, word_files: Iterable[io.StringIO], **kwargs) -> None:

    # Add protocol scheme if not present
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "http://" + base_url

    # Load all wordlist lines into memory to calculate stats
    wordlists_data = []
    total_words = 0
    wordlist_paths = []
    for word_file in word_files:
        lines = word_file.readlines()
        wordlists_data.append(lines)
        total_words += len(lines)
        wordlist_paths.append(getattr(word_file, 'name', '<stdin>'))

    # Beautiful Ascii art banner in Feroxbuster style
    print("\u001b[35;1m" + r"""
 ____  _____ _____ ____  ____  _     ____ _____ _____ ____ 
|  _ \|  ___| ____|  _ \| __ )| |   / ___|_   _| ____|  _ \ 
| | | | |_  |  _| | |_) |  _ \| |   \___ \ | | |  _| | |_) |
| |_| |  _| | |___|  __/| |_) | |___ ___) || | | |___|  _ < 
|____/|_|   |_____|_|   |____/|_____|____/ |_| |_____|_| \_\ """ + "\u001b[0m" + """
    \u001b[36mby OverPowerTeam\u001b[0m               \u001b[33;1mver: beta\u001b[0m
============================================================
""")

    print(f"\u001b[36m🎯 Target URL      :\u001b[0m {base_url}")
    print(f"\u001b[36m📂 Wordlists       :\u001b[0m {', '.join(wordlist_paths)} ({total_words} words)")
    print(f"\u001b[36m🚀 Threads         :\u001b[0m {kwargs.get('num_workers', 10)}")
    print(f"\u001b[36m⏳ Delay           :\u001b[0m {kwargs.get('delay', 50)} ms")
    
    user_agent = kwargs.get('user_agent', 'Mozilla/5.0')
    print(f"\u001b[36m👤 User-Agent      :\u001b[0m {user_agent}")
    
    cookies = kwargs.get('cookie') or kwargs.get('cookies')
    if cookies:
        print(f"\u001b[36m🍪 Cookies         :\u001b[0m {cookies}")
        
    headers = kwargs.get('headers')
    if headers:
        print(f"\u001b[36m🏷️  Headers         :\u001b[0m {headers}")
        
    probe_exts = kwargs.get('probe_extensions', [])
    if probe_exts:
        print(f"\u001b[36m📂 Extensions      :\u001b[0m {', '.join(probe_exts)}")
        
    ignore_case = kwargs.get('ignore_case', False)
    if ignore_case:
        print(f"\u001b[36m🔎 Ignore Case     :\u001b[0m {ignore_case}")
        
    cert = kwargs.get('cert', None)
    if cert:
        print(f"\u001b[36m🛡️  Client Cert     :\u001b[0m {cert}")
        
    ignored_codes = kwargs.get('ignored_codes', [])
    if ignored_codes:
        print(f"\u001b[36m🚫 Ignored Codes   :\u001b[0m {list(ignored_codes)}")
        
    recursive = kwargs.get('recursive', True)
    rec_status = "Enabled" if recursive else "Disabled"
    print(f"\u001b[36m🔄 Recursion       :\u001b[0m {rec_status}")
    
    ai_status = "Enabled" if kwargs.get('ai_enabled', False) else "Disabled"
    print(f"\u001b[36m💡 AI Deep Scan    :\u001b[0m {ai_status}")
    
    output_file = kwargs.get('output_file')
    if output_file:
        print(f"\u001b[36m📝 Output File     :\u001b[0m {output_file}")
        
    start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\u001b[36m🕒 Start Time      :\u001b[0m {start_time_str}")
    # Instantiate the scanning engine first to let hooks access status
    deepbuster = Deepbuster(base_url, **kwargs)

    if deepbuster.ai_enabled:
        print("\u001b[35;1m💡 Tip: To monitor the AI Agent's real-time reasoning and thought logs, run:\u001b[0m")
        print("   \u001b[36mtail -f deepbuster_ai.log\u001b[0m \u001b[35;1min a separate terminal window.\u001b[0m")
        print("============================================================\n")
    else:
        print("============================================================\n")

    # Define a request counter for the spinner animation
    requests_count = 0
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Simple size formatter helper
    def format_cli_size(bytes_size: int) -> str:
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.2f} KB"
        return f"{bytes_size / (1024 * 1024):.2f} MB"

    async def pre_fetch_hook(path: str) -> None:
        nonlocal requests_count
        async with deepbuster.print_lock:
            requests_count += 1
            ai_status = ""
            if deepbuster.ai_enabled:
                ai_status = f" | \u001b[35;1m[AI: {deepbuster.current_ai_status} ({len(deepbuster.ai_tasks)} tasks)]\u001b[0m"
            
            spinner = spinner_chars[requests_count % len(spinner_chars)]
            sys.stdout.write(f"\r\u001b[36m[{spinner}]\u001b[0m Testing: {path}{ai_status} | Requests: {requests_count}\u001b[0K")
            sys.stdout.flush()

    async def found_hook(path: str, status_code: int, size: int) -> None:
        if status_code >= 200 and status_code < 300:
            status_color = "\u001b[32;1m" # Green
        elif status_code >= 300 and status_code < 400:
            status_color = "\u001b[33;1m" # Yellow
        elif status_code in [401, 403]:
            status_color = "\u001b[35;1m" # Magenta
        else:
            status_color = "\u001b[31;1m" # Red
        
        size_str = format_cli_size(size)
        msg = f"\u001b[32m[+]\u001b[0m {status_color}{status_code:<5}\u001b[0m GET   {size_str:>9}   {path}"
        await deepbuster.safe_print(msg)

    async def error_hook(path: str, status_code: int, size: int) -> None:
        if status_code in [401, 403]:
            status_color = "\u001b[35;1m" # Magenta
        else:
            status_color = "\u001b[31;1m" # Red
            
        size_str = format_cli_size(size)
        msg = f"\u001b[31m[-]\u001b[0m {status_color}{status_code:<5}\u001b[0m GET   {size_str:>9}   {path}"
        await deepbuster.safe_print(msg)

    quiet = kwargs.get('quiet', False)
    deepbuster.pre_fetch_callback = pre_fetch_hook if not quiet else None
    deepbuster.found_callback = found_hook if not quiet else None
    deepbuster.error_callback = error_hook if not quiet else None

    for lines in wordlists_data:
        await deepbuster.run(lines)

    output_file = kwargs.get('output_file')
    if output_file:
        save_output(output_file, deepbuster.results, is_csv=kwargs.get('csv', False), base_url=base_url)
    else:
        # CLI print to stdout
        alive = deepbuster.alive()
        print("\n========================= RESULTS ==========================")
        if len(alive) == 0:
            print('\n\u001b[31;1mNOTHING FOUND 🧐\u001b[0m')
        else:
            print(f'''\u001b[32;1mFound {len(alive)} accessible URL{'s' if len(alive) != 1 else ''}:\u001b[0m''')
            for d in alive:
                print(f'''  \u001b[32m[+]\u001b[0m {base_url}{d['path']}''')
        print("============================================================\n")


if __name__ == '__main__':
    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
    DEFAULT_NUM_WORKERS = 20
    parser = argparse.ArgumentParser(prog='deepbuster', description='')
    # -S : Silent Mode. Don't show tested words. (For dumb terminals) 
    # لم تتم اضافته لانه قديم ولا داعي له هو شبيه ب -q لكنه مخصص للتيرمنال القديم الذي لا يدعم الالوان
    parser.add_argument('base_url', help='Base URL, e.g. https://example.com', nargs='?')
    parser.add_argument('-n', '--num-workers', help='parallelize scanning with n workers running concurrently', type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument('-q', '--quiet', action='store_true', default=False)
    parser.add_argument('-w', '--word-file', help='Word file', action='append', default=[])
    parser.add_argument('-W', '--dont-stop-on-warning', action='store_true', help="Don't stop on WARNING messages", default=False)
    parser.add_argument('-a', '--user-agent', help='User agent', default=DEFAULT_USER_AGENT)
    parser.add_argument('-c', '--cookie', help='Cookie string')
    parser.add_argument('-H', '--header', help='Add header string', action='append', default=[])
    parser.add_argument('-u', '--credentials', help='username:password')
    parser.add_argument('-X', '--probe-extensions', help='do not only check the path itself, but also try every path by adding these extensions', default=None)
    parser.add_argument('-M', '--probe-variations', help='if a path is found, check these variations by appending them to the path', default=None)
    parser.add_argument('-L', '--follow-redirects', action='store_true', help='Follow 301/302 redirects', default=False)
    parser.add_argument('-f', '--fine-tune-404', action='store_true', help='Fine-tuning of NOT_FOUND (404) detection to filter soft 404s', default=False)
    parser.add_argument('-s', '--csv', action='store_true', help='Generate CSV output', default=False)
    parser.add_argument('-t', '--dont-force-slash', action='store_true', help="Don't force an ending '/' on URLs", default=False)
    parser.add_argument('-i', '--ignore-case', action='store_true', help="Case-insensitive scanning (normalize wordlist paths to lowercase)", default=False)
    parser.add_argument('-r', '--no-recursive', action='store_true', help="Don't search recursively", default=False)
    parser.add_argument('-d', '--delay', help='Add a milliseconds delay in each request', type=int, default=50)
    parser.add_argument('-E', '--cert', help='Client certificate file (or cert,key split by comma)')
    parser.add_argument('-N', '--ignore-code', help='Ignore responses with these HTTP status codes (comma-separated or multiple flags)', action='append', default=[])
    parser.add_argument('-b', '--use-path-as-is', action='store_true', help='Use path as is (no leading/trailing slashes normalization)', default=False)
    parser.add_argument('-o', '--output', help='Write output to file')
    parser.add_argument('-G', '--gui', action='store_true', help="Launch web based GUI", default=False)
    parser.add_argument('-A', '--ai', action='store_true', help="AI-powered deep scanning", default=False)
    args = parser.parse_args()
    
    if args.gui:
        import gui_server
        gui_server.start_gui_server()
        sys.exit(0)

    if not args.base_url:
        parser.error("the following arguments are required: base_url")

    word_files = [sys.stdin]
    if len(args.word_file) > 0:
        word_files = [open(filename, 'r') for filename in args.word_file]
    
    ignored_codes = parse_ignore_codes(args.ignore_code)

    try:
        asyncio.run(main(
            args.base_url,
            word_files,
            quiet=args.quiet,
            user_agent=args.user_agent,
            cookie=args.cookie,
            headers=args.header,
            credentials=args.credentials,
            follow_redirects=args.follow_redirects,
            probe_extensions=parse_extensions(args.probe_extensions),
            probe_variations=parse_variations(args.probe_variations),
            num_workers=args.num_workers,
            csv=args.csv,
            dont_force_slash=args.dont_force_slash,
            dont_stop_on_warning=args.dont_stop_on_warning,
            fine_tune_404=args.fine_tune_404,
            ignore_case=args.ignore_case,
            recursive=not args.no_recursive,
            delay=args.delay,
            cert=args.cert,
            ignored_codes=ignored_codes,
            use_path_as_is=args.use_path_as_is,
            ai_enabled=args.ai,
            output_file=args.output))
    except KeyboardInterrupt:
        print("\n\n\u001b[31;1m[!] Caught Ctrl+C ... Saving results and shutting down deepbuster cleanly.\u001b[0m")
        sys.exit(0)
