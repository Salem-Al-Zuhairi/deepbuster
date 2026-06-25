import sys

libs = ['selenium', 'pyppeteer', 'requests_html', 'playwright', 'PIL', 'matplotlib', 'urllib3']
for lib in libs:
    try:
        __import__(lib)
        print(f"{lib}: INSTALLED")
    except ImportError:
        print(f"{lib}: NOT INSTALLED")
