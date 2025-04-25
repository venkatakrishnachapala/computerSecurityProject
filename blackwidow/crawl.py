import os
import argparse
import warnings
import traceback
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service

from Classes import Crawler

# ─── Setup Argument Parser ────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Crawler')
parser.add_argument('--wivet', help="Run a WIVET challenge. Use 0 to run all.")
parser.add_argument('--debug', action='store_true', help="Don't use path deconstruction.")
parser.add_argument('--url', help="Custom URL to crawl.")
parser.add_argument('--urls_file', help='File with list of URLs. One per line.')
parser.add_argument('--tokens_file', help='File with list of tokens. One per line.')
parser.add_argument('--payload_csv', help='Path to CSV file containing test payloads.')
parser.add_argument('--cookies', help='Cookie string copied from browser.')
parser.add_argument('--shallow', help='Quick shallow scan for links.')
parser.add_argument('--headless', action='store_true', help="Run browser in headless mode.")
args = parser.parse_args()

# ─── Prepare Directories ───────────────────────────────────────────────
root_dirname = os.path.dirname(__file__)
dynamic_path = os.path.join(root_dirname, 'form_files', 'dynamic')
Path(dynamic_path).mkdir(parents=True, exist_ok=True)
for f in os.listdir(dynamic_path):
    os.remove(os.path.join(dynamic_path, f))

# ─── Chrome WebDriver Setup ────────────────────────────────────────────
WebDriver.add_script = lambda self, script: self.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument", {"source": script})

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--disable-xss-auditor")
chrome_options.add_argument("--remote-debugging-port=9222")
if args.headless:
    chrome_options.add_argument("--headless=new")

warnings.filterwarnings("ignore", category=DeprecationWarning)

chromedriver_path = "C:\\Users\\HP\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe"
service = Service(executable_path=chromedriver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

driver.set_window_position(200, 10)

# ─── Inject Custom JavaScript ──────────────────────────────────────
js_folder = os.path.join(root_dirname, "js")
js_files = [
    "lib.js",
    "property_obs.js",
    "md5.js",
    "addeventlistener_wrapper.js",
    "timing_wrapper.js",
    "window_wrapper.js",
    "forms.js",
    "xss_xhr.js",
    "remove_alerts.js"
]

for js_file in js_files:
    path = os.path.join(js_folder, js_file)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            driver.add_script(f.read())

# ─── Read Payload CSV ────────────────────────────────────────
payload_tokens = []
if args.payload_csv:
    try:
        import pandas as pd
        df = pd.read_csv(args.payload_csv)
        if "payload" not in df.columns:
            raise ValueError(f"'payload' column not found in {args.payload_csv}")
        payload_tokens = df["payload"].dropna().astype(str).tolist()
        print("Loaded", len(payload_tokens), "payloads from", args.payload_csv)
    except Exception:
        print("Error reading payload CSV:")
        traceback.print_exc()
        payload_tokens = []

# ─── Crawler Logic ────────────────────────────────────────
try:
    if args.wivet:
        challenge = int(args.wivet)
        if challenge > 0:
            url = f"http://localhost/wivet/pages/{challenge}.php"
        else:
            url = "http://localhost/wivet/menu.php"
        Crawler(driver, url).start()

    elif args.url:
        Crawler(driver, args.url).start(args.debug)

    elif args.urls_file:
        with open(args.urls_file, encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        tokens = []
        if args.tokens_file:
            with open(args.tokens_file, encoding='utf-8') as tf:
                tokens = [line.strip() for line in tf if line.strip()]
        else:
            tokens = payload_tokens  # fallback to payload CSV tokens

        Crawler(driver, urls[0], urls, args.cookies, tokens).start(args.debug)

    elif args.shallow:
        c = Crawler(driver, args.shallow, None, args.cookies)
        c.shallow = True
        c.start(args.debug)

    else:
        print("Please specify one of --wivet, --url, --urls_file, or --shallow")
except Exception:
    print("Unexpected error during crawling:")
    traceback.print_exc()
