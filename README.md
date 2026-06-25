# Deepbuster 🚀
**An Advanced, AI-Powered, Asynchronous Directory Buster with a Modern Web GUI.**

Deepbuster is a state-of-the-art web directory and file discovery tool written in Python. Harnessing the power of massive parallelization via Tornado's asynchronous I/O, it scans web servers at blistering speeds. It features an interactive, high-fidelity Web GUI, visual screenshot evidence capture via Playwright, context-aware AI directory analysis via Gemini, and robust WAF evasion mechanisms.

---

## ✨ Key Features

* 🚀 **High-Speed Asynchronous Scanning**: Powered by Tornado asynchronous HTTP client for maximum performance and sub-millisecond network I/O.
* 🖥️ **Stunning Web GUI**: Built with a sleek dark-mode sci-fi aesthetic, real-time status dashboards, audio alerts, and interactive control buttons (Start, Pause, Resume, Stop).
* 🧠 **AI-Assisted Recon (Gemini API)**: Integrates with Gemini models to dynamically analyze HTTP headers and response bodies, discovering context-specific directory/file names on the fly.
* 📸 **Visual Evidence Capture**: Automated headless browser screenshotting via Playwright/Chromium for successful (e.g. 2xx) page discoveries.
* 🕸️ **Interactive Network Graph**: Live visualization mapping of discovered paths, directories, and node relationships.
* 🛡️ **Evasion & WAF Bypass**:
  * **Auto-Pause on WAF Block**: Temporarily pauses scanning if consecutive `403 Forbidden` or `429 Too Many Requests` are encountered.
  * **User-Agent Rotation**: Dynamically rotates randomized headers for evasion.
* 🔍 **Fine-Tune 404 / Soft 404 Detection**: Automatically checks for wildcard DNS redirects and ignores soft 404 custom error pages using structural size checks and signature keywords.
* 💾 **Historical Archiving**: Local SQLite integration stores scan histories, status metrics, and allows exporting results directly to CSV.

---

## 🛠️ Installation & Setup

Ensure you have **Python 3.8+** installed.

### 1. Clone the Repository
```bash
git clone https://github.com/Salem-Al-Zuhairi/deepbuster.git
cd deepbuster
```

### 2. Install Dependencies
It is highly recommended to use a virtual environment (`venv`) to keep package installations isolated:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required Python libraries
pip install -r requirements.txt
```
*(Alternatively, install globally using `pip install -r requirements.txt --break-system-packages`)*

### 3. Playwright Setup (Screenshots)
Playwright and its Chromium browser dependencies are **automatically verified and installed** when you launch the Web GUI for the first time. 

If you are running exclusively in CLI mode and want to set up Playwright manually, run:
```bash
pip install playwright --break-system-packages
playwright install chromium
playwright install-deps chromium
```

---

## ⚙️ Configuration (AI Integration)

When you first launch the scanner, a default `config.json` template will be generated in the root directory. To enable the AI-assisted wordlist expansion:

1. Open `config.json` in a text editor.
2. In the `llm` block, update your configuration:
   - Change `"enabled": false` to `"enabled": true`
   - Paste your Gemini API key in `"api_key": "YOUR_GEMINI_API_KEY"`
3. Save the file.

---

## 🚀 Running Deepbuster

### 1. Launching the Web GUI (Recommended)
```bash
python3 deepbuster.py --gui
```
Open your browser and navigate to: **`http://127.0.0.1:4440/`**

From the dashboard you can:
* Enter target hosts, load custom wordlists, and enable/disable the AI agent.
* Watch scan stats, active queue size, and response code distributions.
* Filter and view discovered paths in the Live Graph.
* Export completed scan results directly to CSV.

### 2. Running in CLI Mode
For standard terminal output:
```bash
# Simple scan using a custom wordlist
python3 deepbuster.py http://example.com -w mylist.txt

# Scan with AI-assisted discovery enabled
python3 deepbuster.py http://example.com -w mylist.txt --ai

# Follow redirects and output results to a CSV file
python3 deepbuster.py http://example.com -w mylist.txt -f --csv -o output.csv
```

#### CLI Options:
* `-w`, `--wordlist` : Path to wordlist text files (can specify multiple times).
* `-n`, `--threads`  : Number of concurrent workers (default: 20).
* `-f`, `--follow`   : Instructs the HTTP client to follow redirects.
* `--ai`             : Enables local AI-engine reasoning pipeline.
* `-o`, `--output`   : Writes results to a specified file.
* `--csv`            : Formats file output as a CSV.
* `-h`, `--help`     : Shows the help menu with all options.

---

## 🔒 License & Disclaimer
This tool is created for educational and authorized penetration testing purposes only. Running automated scanners against networks or servers without explicit authorization is illegal. The author holds no liability for any misuse or damages caused by this software.