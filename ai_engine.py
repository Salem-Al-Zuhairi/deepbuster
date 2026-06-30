import os
import json
import logging
import asyncio
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

class DeepbusterAIEngine:
    def __init__(self, config_path="config.json", log_path="deepbuster_ai.log", wordlist_path="ai_generated_wordlist.txt"):
        self.config_path = config_path
        self.log_path = log_path
        self.wordlist_path = wordlist_path
        
        # Configure dedicated logger for AI operations
        self.logger = logging.getLogger("deepbuster_ai")
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(self.log_path, mode="w", encoding="utf-8")
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.enabled = False
        self.unchecked_candidates_set = set()
        self.api_endpoint = ""
        self.api_key = ""
        self.model_name = ""
        self.temperature = 0.3
        self.max_tokens = 4096
        self.max_content_length = 8000
        self.trigger_status_codes = [200, 201, 301, 302, 403]
        self.min_body_size = 0
        self.prefixes = [""]
        self.suffixes = [""]
        self.patterns = ["{keyword}"]
        
        # In-memory analyzed paths set to avoid duplicate token consumption
        self.analyzed_paths = set()
        
        # Comprehensive Rate Limiting & Spacing variables
        self.rpm = 30
        self.tpm = 0
        self.rpd = 0
        self.tpd = 0
        self.max_concurrent = 0
        self.concurrency_window = 0.0
        
        # Sliding Window / Token consumption trackers
        self.requests_timestamps_minute = []  # list of floats (timestamps)
        self.tokens_timestamps_minute = []    # list of tuples: (timestamp, token_count)
        self.requests_timestamps_day = []     # list of floats
        self.tokens_timestamps_day = []        # list of tuples: (timestamp, token_count)
        self.active_concurrency_window = []   # list of floats (timestamps of active requests)
        
        self.api_delay = 2.0
        self.max_retries = 3
        self.retry_backoff = 5.0
        self.last_request_time = 0.0
        self.rate_limit_lock = asyncio.Lock()
        
        # Upgraded Context-Aware & Directory Listing Sensitive System Prompt
        self.system_prompt = (
            "You are a professional cybersecurity reconnaissance assistant.\n"
            "Your goal is to analyze the provided HTTP response headers and body, detect the type of page/resource, and generate high-probability directory/file names for hidden paths.\n\n"
            "STRICT CLASSIFICATION & BEHAVIOR RULES:\n"
            "1. DIRECTORY LISTINGS:\n"
            "   - If the page is a directory listing (e.g. title starts with 'Directory listing for' or contains lists of files/links):\n"
            "     - Extract ONLY the actual words/names from the listed directory/file links.\n"
            "     - Decrypt any percent-encoded characters (e.g., %D8%A7 -> Arabic/Unicode characters) to their raw, clean form.\n"
            "     - DO NOT guess generic files (like .env, .git, robots.txt, admin, config) inside assets, assets/js. Only generate generic guesses if you see structural/developer indicators (like 'v1', 'api', 'admin').\n"
            "2. API ENDPOINTS (JSON/XML):\n"
            "   - If the page is a JSON/XML response, guess relevant API routing paths, API versions (e.g. 'v2', 'v3'), documentation endpoints (e.g. 'swagger', 'docs'), or authentication routes.\n"
            "3. AUTHENTICATION / LOGIN PAGES:\n"
            "   - If you detect login forms or authorization headers, guess auth-related paths (e.g. 'signup', 'forgot-password', 'register', 'admin', 'portal').\n"
            "4. STANDARD HTML / LANDING PAGES:\n"
            "   - Inspect links, scripts, and comments to extract keywords, assets, and technology directories.\n\n"
            "OUTPUT FORMAT:\n"
            "- Respond ONLY with a valid JSON array of short lowercase directory/file words (e.g. [\"b\", \"orange\", \"v2\"]).\n"
            "- Do not wrap paths in full URLs.\n"
            "- No markdown blocks, no explanations, no text before or after the JSON array."
        )
        
        # Keep customized wordlist_path if not default
        self.custom_wordlist_path_provided = (wordlist_path != "ai_generated_wordlist.txt")
        
        self._ensure_config()
        self._load_config()
        
    def _ensure_config(self):
        """Creates a template config.json if not present."""
        if not os.path.exists(self.config_path):
            default_config = {
                "llm": {
                    "enabled": False,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                    "api_key": "YOUR_API_KEY_HERE",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "custom_system_prompt": self.system_prompt
                },
                "rate_limits": {
                    "rpm": 30,
                    "tpm": 0,
                    "rpd": 0,
                    "tpd": 0,
                    "max_concurrent": 5,
                    "concurrency_window": 10.0,
                    "delay": 2.0,
                    "max_retries": 3,
                    "retry_backoff": 5.0
                },
                "analysis": {
                    "max_content_length": 8000,
                    "trigger_status_codes": [200, 201, 301, 302, 403],
                    "min_body_size": 0
                },
                "wordlist": {
                    "output_file": self.wordlist_path,
                    "prefixes": ["", "api/", "v1/", "v2/", "admin/", "internal/", "_", "."],
                    "suffixes": ["", "/", ".php", ".html", ".json", ".xml", ".js", ".bak", ".old", ".txt", ".log", ".conf"],
                    "patterns": [
                        "{keyword}",
                        "{keyword}/login",
                        "{keyword}/admin",
                        "{keyword}/config",
                        "{keyword}/api",
                        "{keyword}/dashboard",
                        "{keyword}/backup",
                        "{keyword}_backup",
                        "{keyword}_old",
                        "{keyword}_test",
                        "{keyword}_dev",
                        "old_{keyword}",
                        "test_{keyword}",
                        "dev_{keyword}",
                        "backup_{keyword}"
                    ]
                }
            }
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4)
                self.logger.info(f"Created template configuration at {self.config_path}")
            except Exception as e:
                self.logger.error(f"Failed to create template configuration: {e}")

    def _load_config(self):
        """Loads parameters from config.json."""
        if not os.path.exists(self.config_path):
            self.logger.warning("Configuration file missing. AI engine disabled.")
            return
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            llm_config = data.get("llm", {})
            if not llm_config and "ai_agent" in data:
                llm_config = data.get("ai_agent", {})
                self.api_endpoint = llm_config.get("api_endpoint", "")
                self.api_key = llm_config.get("api_key", "")
                self.model_name = llm_config.get("model_name", "")
                self.temperature = llm_config.get("temperature", 0.2)
                self.max_tokens = llm_config.get("max_tokens", 1000)
                self.enabled = llm_config.get("enabled", False)
                self.system_prompt = llm_config.get("custom_system_prompt", self.system_prompt)
            else:
                self.api_endpoint = llm_config.get("base_url", "")
                self.api_key = llm_config.get("api_key", "")
                self.model_name = llm_config.get("model", "")
                self.temperature = llm_config.get("temperature", 0.3)
                self.max_tokens = llm_config.get("max_tokens", 4096)
                self.enabled = llm_config.get("enabled", False)
                self.system_prompt = llm_config.get("custom_system_prompt", self.system_prompt)
                
            if self.enabled:
                if not self.api_key or "YOUR_API_KEY_HERE" in self.api_key:
                    self.logger.warning("AI enabled in config, but API key is a placeholder. Disabling AI.")
                    self.enabled = False
                    
            rate_limits = data.get("rate_limits", {})
            self.rpm = rate_limits.get("rpm", 30)
            self.tpm = rate_limits.get("tpm", 0)
            self.rpd = rate_limits.get("rpd", 0)
            self.tpd = rate_limits.get("tpd", 0)
            self.max_concurrent = rate_limits.get("max_concurrent", 0)
            self.concurrency_window = rate_limits.get("concurrency_window", 0.0)
            self.api_delay = rate_limits.get("delay", 2.0)
            self.max_retries = rate_limits.get("max_retries", 3)
            self.retry_backoff = rate_limits.get("retry_backoff", 5.0)
            
            wordlist_config = data.get("wordlist", {})
            if not self.custom_wordlist_path_provided:
                self.wordlist_path = wordlist_config.get("output_file", self.wordlist_path)
            self.prefixes = wordlist_config.get("prefixes", [""])
            self.suffixes = wordlist_config.get("suffixes", [""])
            self.patterns = wordlist_config.get("patterns", ["{keyword}"])
            
            analysis_config = data.get("analysis", {})
            self.max_content_length = analysis_config.get("max_content_length", 8000)
            self.trigger_status_codes = analysis_config.get("trigger_status_codes", [200, 201, 301, 302, 403])
            self.min_body_size = analysis_config.get("min_body_size", 0)
            
            if self.enabled:
                self.logger.info("AI Engine successfully initialized and enabled.")
            else:
                self.logger.info("AI Engine is loaded but disabled or missing API key.")
                
        except Exception as e:
            self.logger.error(f"Failed to parse config.json: {e}")
            self.enabled = False

    def load_state_unchecked_words(self):
        """Reads ai_generated_wordlist.txt and extracts words starting with [$]."""
        unchecked_words = []
        self.unchecked_candidates_set.clear()
        if not os.path.exists(self.wordlist_path):
            return unchecked_words
            
        try:
            with open(self.wordlist_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[$]"):
                        word = line[3:].strip()
                        if word:
                            unchecked_words.append(word)
                            self.unchecked_candidates_set.add(word)
            self.logger.info(f"Loaded {len(unchecked_words)} unchecked AI paths from existing wordlist.")
        except Exception as e:
            self.logger.error(f"Error loading state from wordlist: {e}")
            
        return unchecked_words

    def mark_word_processed(self, path):
        """Removes the [$] prefix from a processed word in the file."""
        # path is like 'admin/v1/login.php' or 'v1/login.php'
        match = None
        if path in self.unchecked_candidates_set:
            match = path
        else:
            # Suffix match: e.g. if path is 'admin/v1/login.php' and candidate is 'v1/login.php'
            for candidate in self.unchecked_candidates_set:
                if path.endswith(candidate) and (len(path) == len(candidate) or path[-len(candidate)-1] == '/'):
                    match = candidate
                    break
        
        if not match:
            return
            
        self.unchecked_candidates_set.discard(match)
        
        if not os.path.exists(self.wordlist_path):
            return
            
        try:
            lines = []
            with open(self.wordlist_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            updated = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == f"[$] {match}" or stripped == f"[$]{match}":
                    lines[i] = f"{match}\n"
                    updated = True
                    break
                    
            if updated:
                with open(self.wordlist_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception as e:
            self.logger.error(f"Failed to update word state in wordlist: {e}")

    def _save_new_words(self, words):
        """Saves newly generated words to the file with [$] prefix if not already present."""
        existing_words = set()
        if os.path.exists(self.wordlist_path):
            try:
                with open(self.wordlist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("[$]"):
                            existing_words.add(line[3:].strip())
                        else:
                            existing_words.add(line)
            except Exception as e:
                self.logger.error(f"Error checking existing words in file: {e}")
                
        # Expanded set of words based on config patterns, prefixes, and suffixes
        expanded_words = set()
        for word in words:
            word = word.strip().strip("/")
            if not word:
                continue
            for pattern in getattr(self, 'patterns', ["{keyword}"]):
                formatted_pattern = pattern.replace("{keyword}", word)
                for prefix in getattr(self, 'prefixes', [""]):
                    for suffix in getattr(self, 'suffixes', [""]):
                        candidate = f"{prefix}{formatted_pattern}{suffix}"
                        candidate = candidate.strip().strip("/")
                        if candidate:
                            expanded_words.add(candidate)
                            
        try:
            with open(self.wordlist_path, "a", encoding="utf-8") as f:
                appended_count = 0
                for candidate in expanded_words:
                    if candidate not in existing_words:
                        f.write(f"[$] {candidate}\n")
                        self.unchecked_candidates_set.add(candidate)
                        appended_count += 1
            self.logger.info(f"Appended {appended_count} expanded new words to {self.wordlist_path}")
        except Exception as e:
            self.logger.error(f"Failed to save new words to wordlist file: {e}")
            
        return list(expanded_words)

    def _clean_rate_limit_records(self):
        import time
        now = time.time()
        
        # Clean minute records (60.0s)
        self.requests_timestamps_minute = [t for t in self.requests_timestamps_minute if now - t < 60.0]
        self.tokens_timestamps_minute = [item for item in self.tokens_timestamps_minute if now - item[0] < 60.0]
        
        # Clean day records (86400.0s)
        self.requests_timestamps_day = [t for t in self.requests_timestamps_day if now - t < 86400.0]
        self.tokens_timestamps_day = [item for item in self.tokens_timestamps_day if now - item[0] < 86400.0]
        
        # Clean sliding concurrency window
        if self.concurrency_window > 0:
            self.active_concurrency_window = [t for t in self.active_concurrency_window if now - t < self.concurrency_window]

    async def _enforce_limits(self):
        import time
        now = time.time()
        self._clean_rate_limit_records()
        
        rpm_wait = 0.0
        rpd_wait = 0.0
        tpm_wait = 0.0
        tpd_wait = 0.0
        concurrency_wait = 0.0
        
        # 1. Check RPM
        if self.rpm > 0 and len(self.requests_timestamps_minute) >= self.rpm:
            rpm_wait = (self.requests_timestamps_minute[0] + 60.0) - now
            
        # 2. Check RPD
        if self.rpd > 0 and len(self.requests_timestamps_day) >= self.rpd:
            rpd_wait = (self.requests_timestamps_day[0] + 86400.0) - now
            
        # 3. Check TPM
        if self.tpm > 0:
            current_tpm_sum = sum(item[1] for item in self.tokens_timestamps_minute)
            if current_tpm_sum >= self.tpm:
                temp_sum = current_tpm_sum
                for t_stamp, t_count in sorted(self.tokens_timestamps_minute, key=lambda x: x[0]):
                    temp_sum -= t_count
                    if temp_sum < self.tpm:
                        tpm_wait = (t_stamp + 60.0) - now
                        break
                        
        # 4. Check TPD
        if self.tpd > 0:
            current_tpd_sum = sum(item[1] for item in self.tokens_timestamps_day)
            if current_tpd_sum >= self.tpd:
                temp_sum = current_tpd_sum
                for t_stamp, t_count in sorted(self.tokens_timestamps_day, key=lambda x: x[0]):
                    temp_sum -= t_count
                    if temp_sum < self.tpd:
                        tpd_wait = (t_stamp + 86400.0) - now
                        break
                        
        # 5. Check Concurrency Window
        if self.max_concurrent > 0 and self.concurrency_window > 0:
            if len(self.active_concurrency_window) >= self.max_concurrent:
                concurrency_wait = (self.active_concurrency_window[0] + self.concurrency_window) - now
                
        wait_time = max(0.0, rpm_wait, rpd_wait, tpm_wait, tpd_wait, concurrency_wait)
        if wait_time > 0.0:
            if wait_time > 10.0:
                self.logger.warning(f"Rate Limiter: wait time of {wait_time:.2f}s exceeds 10s threshold. Raising timeout exception to skip.")
                raise ValueError("Rate limit wait time too long")
            self.logger.info(f"Rate Limiter: custom limits reached. Pausing API scan for {wait_time:.2f} seconds...")
            await asyncio.sleep(wait_time)

    async def analyze(self, path, response_headers, response_body):
        """Sends the HTTP headers and response body to the OpenAI-compatible endpoint."""
        if not self.enabled:
            return []
            
        # 1. Cache/Deduplication check
        if path in self.analyzed_paths:
            self.logger.info(f"Skipping already analyzed path: {path}")
            return []
        self.analyzed_paths.add(path)
        
        self.logger.info(f"Starting AI analysis of path: {path}")
        
        # Check size limits
        body_len = len(response_body) if response_body else 0
        if body_len < self.min_body_size:
            self.logger.info(f"Skipping AI analysis for path {path}: body size {body_len} is less than min_body_size {self.min_body_size}")
            return []

        # Clean response body for token economy and truncate to max_content_length
        body_text = ""
        if response_body:
            if isinstance(response_body, bytes):
                try:
                    body_text = response_body.decode("utf-8", errors="ignore")
                except Exception:
                    body_text = str(response_body)
            else:
                body_text = str(response_body)
                
            # Truncate if exceeds max_content_length
            if len(body_text) > self.max_content_length:
                self.logger.info(f"Truncating response body from {len(body_text)} to max_content_length {self.max_content_length}")
                body_text = body_text[:self.max_content_length] + "\n[TRUNCATED BY AI ENGINE LIMITS]"
                
        headers_str = json.dumps(dict(response_headers)) if response_headers else "None"
        
        user_message = (
            f"Analyzed Path: {path}\n\n"
            f"HTTP Response Headers:\n{headers_str}\n\n"
            f"HTTP Response Body:\n{body_text}\n"
        )
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        endpoint_url = self.api_endpoint
        if not endpoint_url.endswith("/chat/completions") and not endpoint_url.endswith("/completions"):
            endpoint_url = f"{endpoint_url.rstrip('/')}/chat/completions"
            
        retries = 0
        response = None
        http_client = AsyncHTTPClient()
        
        req = HTTPRequest(
            endpoint_url,
            method="POST",
            headers=headers,
            body=json.dumps(payload),
            request_timeout=60.0  # Increased request timeout to support large full-body requests cleanly
        )
        self.logger.info(f"request headers: {req.headers}\n\nrequest body: {req.body}")
        self.logger.info(f"Sending async API request for path: {path}")
        
        while retries <= self.max_retries:
            try:
                # 2. Rate Limit, Delay Spacing & Custom Limit Lock Enforcer
                async with self.rate_limit_lock:
                    # Enforce custom limits (RPM, TPM, RPD, TPD, Concurrency Sliding Window)
                    await self._enforce_limits()
                    
                    # Apply delay spacing
                    import time
                    now = time.time()
                    elapsed = now - self.last_request_time
                    needed_wait = self.api_delay - elapsed
                    if needed_wait > 0:
                        self.logger.info(f"Rate limiter: waiting {needed_wait:.2f} seconds before next API request...")
                        await asyncio.sleep(needed_wait)
                    
                    # Record start time for request concurrency sliding windows
                    now = time.time()
                    self.requests_timestamps_minute.append(now)
                    self.requests_timestamps_day.append(now)
                    self.active_concurrency_window.append(now)
                    self.last_request_time = now
                
                self.logger.info(f"Sending async API request for path: {path} (Attempt {retries + 1}/{self.max_retries + 1})")
                response = await http_client.fetch(req)
                break  # Successful fetch! Break the retry loop.
            except ValueError as ve:
                if str(ve) == "Rate limit wait time too long":
                    self.logger.warning(f"Aborting AI analysis of path {path} due to high rate limit delay.")
                    return []
                # Otherwise treat as generic exception
                error_msg = str(ve)
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Failed to analyze path {path} after {self.max_retries} retries. Last error: {ve}")
                    return []
            except Exception as e:
                error_msg = str(e)
                is_429 = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "Quota exceeded" in error_msg
                
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Failed to analyze path {path} after {self.max_retries} retries. Last error: {e}")
                    return []
                
                # Check for rate-limiting or quota exhaustion
                if is_429:
                    import sys
                    sys.stdout.write("\n\u001b[33;1m[!] AI API Rate Limit / Quota Exhausted. Pausing AI scans for 60 seconds to cooldown...\u001b[0m\n")
                    sys.stdout.flush()
                    self.logger.warning(f"Quota exceeded / HTTP 429 for path {path}. error message: {error_msg}\nCooldown sleep for 60.00 seconds...")
                    await asyncio.sleep(60.0)
                else:
                    # Exponential Backoff computation with minor random jitter for general connection errors
                    import random
                    backoff_wait = (self.retry_backoff * (2 ** (retries - 1))) + random.uniform(0.5, 1.5)
                    self.logger.warning(f"Network error ({e}) for path {path}. Retrying in {backoff_wait:.2f} seconds...")
                    await asyncio.sleep(backoff_wait)
                
        try:
            res_data = json.loads(response.body.decode("utf-8", errors="ignore"))
            self.logger.info(f"response Headers: {response.headers}\n\nresponse body: {response.body}\n\nresponse enhance body: {res_data}")
            
            # Check for API-returned errors inside successful HTTP responses (like some proxies emit)
            if "error" in res_data:
                err_info = res_data["error"]
                err_msg = err_info.get("message", "")
                err_code = err_info.get("code", "")
                if "exhausted" in err_msg.lower() or "quota" in err_msg.lower() or "429" in str(err_code):
                    import sys
                    sys.stdout.write("\n\u001b[33;1m[!] AI API Quota Exhausted (API Error). Pausing AI scans for 60 seconds to cooldown...\u001b[0m\n")
                    sys.stdout.flush()
                    self.logger.warning(f"Quota Exhausted error returned by API: {err_msg}. Sleeping for 60 seconds...")
                    await asyncio.sleep(60.0)
                    # Recursively retry the analyze call once after cooldown
                    return await self.analyze(path, response_headers, response_body)
            
            content = res_data["choices"][0]["message"]["content"].strip()
            
            # Record Token Consumption usage
            usage = res_data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            if total_tokens == 0:
                # estimate if missing from API metadata
                total_tokens = len(payload["messages"][0]["content"]) // 4 + len(payload["messages"][1]["content"]) // 4 + len(content) // 4
            
            import time
            now = time.time()
            self.tokens_timestamps_minute.append((now, total_tokens))
            self.tokens_timestamps_day.append((now, total_tokens))
            
            # Basic cleanup in case the LLM wrapped JSON in markdown codeblocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            words = json.loads(content)
            if isinstance(words, list):
                # Sanitize extracted words
                clean_words = [str(w).strip().strip("/") for w in words if w]
                self.logger.info(f"AI returned {len(clean_words)} candidate words for path {path}: {clean_words}")
                expanded = self._save_new_words(clean_words)
                return expanded
            else:
                self.logger.warning(f"AI response content did not parse as a list: {content}")
                
        except Exception as e:
            self.logger.error(f"Error parsing AI response for {path}: {e}")
            
        return []
