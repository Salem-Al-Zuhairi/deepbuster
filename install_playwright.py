import subprocess
import sys

def run_cmd(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)
    print(f"Exit code: {res.returncode}")
    return res.returncode

# Try to install playwright via pip
run_cmd("pip install --upgrade playwright --break-system-packages")
# Try to install chromium browser binaries
run_cmd("playwright install chromium")
