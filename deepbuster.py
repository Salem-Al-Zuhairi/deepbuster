#!/usr/bin/env python3

import argparse
import sys
import io
import uuid
import ssl
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
import asyncio
from typing import Iterable

class Deepbuster:
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
        self.ignored_codes = set(kwargs.get('ignored_codes', []))
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
        self.interactive_recursive = kwargs.get('interactive_recursive', False)
        self.scanned_directories = set(['/'])
        self.input_lock = asyncio.Lock()
        self.wordlist = []
        self.probe_extensions = kwargs.get('probe_extensions', [])
        self.probe_variations = kwargs.get('probe_variations', [])
        self.cookie = kwargs.get('cookie', None) or kwargs.get('cookies', None)
        headers = kwargs.get('headers', None)
        self.headers = {}
        if isinstance(headers, list):
            for header in headers:
                if ':' in header:
                    k, v = header.split(':', 1)
                    self.headers[k.strip()] = v.strip()
        elif isinstance(headers, dict):
            self.headers = headers
        credentials = kwargs.get('credentials', None)
        self.auth_user_name, self.auth_password = credentials.split(':', 1) \
            if isinstance(credentials, str) else (None, None)
        self.queue = asyncio.Queue()
        self.num_workers = kwargs.get('num_workers', 10)
        self.results = []

    async def check_wildcard(self) -> bool:
        # Generate two completely unique, dynamic, and random nonexistent paths
        p1 = f"/deepbuster_{uuid.uuid4().hex}"
        p2 = f"/deepbuster_{uuid.uuid4().hex}_{uuid.uuid4().hex}"
        
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
                               ssl_options=self.ssl_ctx)
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
                                   ssl_options=self.ssl_ctx)
                r2 = await http_client.fetch(req2)
                if r2.code == 200:
                    if self.fine_tune_404:
                        self.custom_404_lengths.add(len(r2.body))
                        self.custom_404_base_sizes.add(len(r2.body) - len(p2))
        except Exception:
            pass
        return has_wildcard

    async def run(self, paths: Iterable[str]) -> None:
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
        # wait for queue to be processed
        await self.queue.join()
        for worker in workers:
            worker.cancel()

    async def try_url(self) -> None:
        if self.delay > 0:
            await asyncio.sleep(self.delay / 1000.0)
        path = await self.queue.get()
        if not self.use_path_as_is:
            if not path.startswith('/'):
                path = '/' + path
            if not self.dont_force_slash and not path.endswith('/'):
                # Only append slash if there's no extension in the last path segment
                last_segment = path.split('/')[-1]
                if '.' not in last_segment:
                    path = path + '/'
        url = f'{self.base_url}{path}'
        if callable(self.pre_fetch_callback):
            await self.pre_fetch_callback(path)
        try:
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
                              ssl_options=self.ssl_ctx)
            response = await http_client.fetch(req)
            if response.code in self.ignored_codes:
                return
            # print([i for i in response.headers.get_all()])
            print(len(response.body))

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
                            await self.error_callback(f'{path} -> Ignored (Soft 404 matching nonexistent size and signature)')
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
        finally:
            self.queue.task_done()

    async def worker(self) -> None:
        while True:
            try:
                await self.try_url()
            except asyncio.CancelledError:
                return

    async def handle_recursive_directory(self, path: str) -> None:
        if path in self.scanned_directories:
            return
        
        should_recurse = False
        if self.recursive:
            if self.interactive_recursive:
                # Synchronize prompts between parallel workers
                async with self.input_lock:
                    # Execute input() in a thread to keep the asyncio event loop running
                    choice = await asyncio.to_thread(
                        input, f"\n==> Directory found: {path}\nDo you want to scan it recursively? (y/n): "
                    )
                    if choice.strip().lower() == 'y':
                        should_recurse = True
            else:
                should_recurse = True

        if should_recurse:
            self.scanned_directories.add(path)
            print(f"\n\u001b[34;1m[+] Adding recursive scan for directory: {path}\u001b[0m")
            for word in self.wordlist:
                clean_word = word[1:] if word.startswith('/') else word
                await self.queue.put(f"{path}{clean_word}")



    @property
    def result(self) -> Iterable[str]:
        return self.results

    def alive(self) -> Iterable[str]:
        return [r for r in self.results if r['status_code'] == 200]


async def main(base_url: str, verbose: int, word_files: Iterable[io.StringIO], **kwargs) -> None:

    # Beautiful Ascii art banner in Feroxbuster style
    print("\u001b[35;1m" + r"""
 ____  _____ _____ ____  ____  _     ____ _____ _____ ____ 
|  _ \|  ___| ____|  _ \| __ )| |   / ___|_   _| ____|  _ \ 
| | | | |_  |  _| | |_) |  _ \| |   \___ \ | | |  _| | |_) |
| |_| |  _| | |___|  __/| |_) | |___ ___) || | | |___|  _ < 
|____/|_|   |_____|_|   |____/|_____|____/ |_| |_____|_| \_\ """ + "\u001b[0m" + """
    \u001b[36mby Salem-Al-Zuhairi\u001b[0m               \u001b[33;1mver: 2.5.0\u001b[0m
============================================================
""")

    print(f"\u001b[36m🎯 Target URL      :\u001b[0m {base_url}")
    print(f"\u001b[36m🚀 Threads         :\u001b[0m {kwargs.get('num_workers', 10)}")
    print(f"\u001b[36m📂 Extensions      :\u001b[0m {kwargs.get('probe_extensions', []) or 'None'}")
    print(f"\u001b[36m🔎 Ignore Case     :\u001b[0m {kwargs.get('ignore_case', False)}")
    print(f"\u001b[36m⏳ Delay           :\u001b[0m {kwargs.get('delay', 0)} ms")
    print(f"\u001b[36m🛡️  Client Cert     :\u001b[0m {kwargs.get('cert', 'None')}")
    print(f"\u001b[36m🚫 Ignored Codes   :\u001b[0m {kwargs.get('ignored_codes', []) or 'None'}")
    print(f"\u001b[36m🔄 Recursion       :\u001b[0m {kwargs.get('recursive', True)} (Interactive: {kwargs.get('interactive_recursive', False)})")
    print("============================================================\n")

    # Define dynamic interactive lock for CLI printing
    print_lock = asyncio.Lock()

    async def pre_fetch_hook(url: str) -> None:
        async with print_lock:
            # Overwrite current line (Feroxbuster style)
            print(f'\r\u001b[36m[⧗]\u001b[0m Testing: {url}\u001b[0K', end='', flush=True)

    async def found_hook(url: str, status_code: int, size: int) -> None:
        async with print_lock:
            # Highlighting status code in different colors
            if status_code == 200:
                status_color = "\u001b[32;1m" # Green
            elif status_code in [301, 302]:
                status_color = "\u001b[33;1m" # Yellow
            else:
                status_color = "\u001b[36;1m" # Cyan
            
            # Print beautiful aligned result
            print(f'\r{status_color}{status_code:<5}\u001b[0m  GET   {size:>8}b   {url}\u001b[0K')

    async def error_hook(url: str, status_code: int, size: int) -> None:
        async with print_lock:
            # Red color for error / hidden pages
            print(f'\r\u001b[31;1m{status_code:<5}\u001b[0m  GET   {size:>8}b   {url}\u001b[0K')

    quiet = kwargs.get('quiet', False)
    kwargs['pre_fetch_callback'] = pre_fetch_hook \
        if not quiet else None
    kwargs['found_callback'] = found_hook \
        if not quiet else None
    kwargs['error_callback'] = error_hook \
        if not quiet else None

    deepbuster = Deepbuster(base_url, **kwargs)
    for word_file in word_files:
        await deepbuster.run(word_file.readlines())

    if kwargs.get('output_file'):
        output = open(kwargs.get('output_file'), 'w+')
    else:
        output = sys.stdout

    if kwargs.get('csv'):
        ESC_QUOTES = str.maketrans({'"': r'\"'})
        FIELDS = ['status_code', 'path', 'effective_url', 'headers']
        output.write(f'''{';'.join(FIELDS)}\n''')
        for result in deepbuster.results:
            output.write(f'''{result['status_code']};"{result['path'].translate(ESC_QUOTES)}";"{result['effective_url'].translate(ESC_QUOTES)}";''')
            headers = [f'"{h.translate(ESC_QUOTES)}:{v.translate(ESC_QUOTES)}"' for (h, v) in result['headers']]
            output.write(','.join(headers))
            output.write('\n')
    else:
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
    parser = argparse.ArgumentParser(prog='deepbuster', description='Directory Buster')
    # -S : Silent Mode. Don't show tested words. (For dumb terminals) 
    # لم تتم اضافته لانه قديم ولا داعي له هو شبيه ب -q لكنه مخصص للتيرمنال القديم الذي لا يدعم الالوان
    parser.add_argument('base_url', help='Base URL, e.g. https://example.com')
    parser.add_argument('-n', '--num-workers', help='parallelize scanning with n workers running concurrently', type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument('-v', '--verbose', action='count', default=0)
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
    parser.add_argument('-R', '--interactive-recursive', action='store_true', help="Interactive recursive search (ask before entering every directory)", default=False)
    parser.add_argument('-d', '--delay', help='Add a milliseconds delay in each request', type=int, default=0)
    parser.add_argument('-E', '--cert', help='Client certificate file (or cert,key split by comma)')
    parser.add_argument('-N', '--ignore-code', help='Ignore responses with these HTTP status codes (comma-separated or multiple flags)', action='append', default=[])
    parser.add_argument('-b', '--use-path-as-is', action='store_true', help='Use path as is (no leading/trailing slashes normalization)', default=False)
    parser.add_argument('-o', '--output', help='Write output to file')
    parser.add_argument('-G', '--gui', action='store_true', help="Launch web based GUI", default=False)
    parser.add_argument('-A', '--ai', action='store_true', help="AI-powered deep scanning", default=True)
    args = parser.parse_args()
    word_files = [sys.stdin]
    if len(args.word_file) > 0:
        word_files = [open(filename, 'r') for filename in args.word_file]
    
    ignored_codes = []
    if args.ignore_code:
        for item in args.ignore_code:
            for code in item.split(','):
                try:
                    ignored_codes.append(int(code.strip()))
                except ValueError:
                    pass

    try:
        asyncio.run(main(
            args.base_url,
            args.verbose,
            word_files,
            quiet=args.quiet,
            user_agent=args.user_agent,
            cookie=args.cookie,
            headers=args.header,
            credentials=args.credentials,
            follow_redirects=args.follow_redirects,
            probe_extensions=args.probe_extensions.split(',') if isinstance(args.probe_extensions, str) else [],
            probe_variations=args.probe_variations.split(',') if isinstance(args.probe_variations, str) else [],
            num_workers=args.num_workers,
            csv=args.csv,
            dont_force_slash=args.dont_force_slash,
            dont_stop_on_warning=args.dont_stop_on_warning,
            fine_tune_404=args.fine_tune_404,
            ignore_case=args.ignore_case,
            recursive=not args.no_recursive,
            interactive_recursive=args.interactive_recursive,
            delay=args.delay,
            cert=args.cert,
            ignored_codes=ignored_codes,
            use_path_as_is=args.use_path_as_is,
            output_file=args.output))
    except KeyboardInterrupt:
        print("\n\n\u001b[31;1m[!] Caught Ctrl+C ... Saving results and shutting down deepbuster cleanly.\u001b[0m")
        sys.exit(0)
