"""Create PyPI API Token via Playwright - with TOTP fallback."""
import os, sys, time, re
from playwright.sync_api import sync_playwright
import pyotp

PYPI_USER = os.environ.get("PYPI_USER", "")
PYPI_PASS = os.environ.get("PYPI_PASS", "")
TOTP_SECRETS = [
    os.environ.get("PYPI_TOTP_SECRET", "ZZ4TENABL5LFFK6X"),
    "ZZ4OL5CUEPF2W4QCRGJNA5DIKLRMLKTX",
]
TOKEN_NAME = os.environ.get("TOKEN_NAME", "cniw-github-actions")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

for TOTP_SECRET in TOTP_SECRETS:
    totp = pyotp.TOTP(TOTP_SECRET)
    try:
        log(f"Trying TOTP secret: {TOTP_SECRET[:12]}...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            )
            page = ctx.new_page()
            
            # Login
            log("Logging in...")
            page.goto("https://pypi.org/account/login/", timeout=60000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="username"]', PYPI_USER)
            page.fill('input[name="password"]', PYPI_PASS)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            log(f"After login: {page.url}")
            
            # TOTP
            page_title = page.title().lower()
            page_url = page.url.lower()
            if "two-factor" in page_url or "two-factor" in page_title or "totp" in page_url or "authenticator" in page_url:
                log("Submitting TOTP...")
                code = totp.now()
                log(f"TOTP code: {code}")
                # Try both possible field names
                totp_input = page.query_selector('input[name="code"]')
                if not totp_input:
                    totp_input = page.query_selector('input[name="totp_value"]')
                if not totp_input:
                    totp_input = page.query_selector('input[type="text"]')
                if totp_input:
                    totp_input.fill(code)
                    page.click('button[type="submit"]')
                    page.wait_for_load_state("networkidle")
                    log(f"After TOTP: {page.url}")
                else:
                    log("Could not find TOTP input field")
                    page.screenshot(path="/tmp/pypi_totp_field.png")
            
            # Check if logged in
            if "manage" in page.url or "dashboard" in page.content().lower():
                log("✅ Logged in!")
                
                # Go to token page
                page.goto("https://pypi.org/manage/account/token/", timeout=60000, wait_until="networkidle")
                log(f"Token page loaded")
                
                # Take screenshot for debug
                page.screenshot(path="/tmp/pypi_token_page.png")
                
                # Click Add API token
                add_btn = page.query_selector('a:has-text("Add API token")')
                if add_btn:
                    add_btn.click()
                    page.wait_for_load_state("networkidle")
                    
                    # Fill form
                    name_input = page.query_selector('input[name="name"]')
                    if name_input:
                        name_input.fill(TOKEN_NAME)
                    
                    scope_select = page.query_selector('select[name="scope"]')
                    if scope_select:
                        scope_select.select_option("project:china-indices-watcher")
                    
                    # Submit
                    submit = page.query_selector('button[type="submit"]')
                    if submit:
                        submit.click()
                        page.wait_for_load_state("networkidle")
                        
                        # Get token from page - PyPI shows it in a highlighted box
                        token_elem = page.query_selector('[class*="token"], pre.badge, code, .highlight')
                        if token_elem:
                            token = token_elem.text_content().strip().split('\n')[0]
                            log(f"✅ TOKEN: {token[:30]}...")
                            with open("/tmp/pypi_token.txt", "w") as f:
                                f.write(token)
                            print(f"PYPI_TOKEN={token}")
                        else:
                            # Try to find any input with the token value
                            token_input = page.query_selector('input[readonly]')
                            if token_input:
                                token = token_input.get_attribute("value")
                                log(f"✅ TOKEN (alt): {token[:30]}...")
                                with open("/tmp/pypi_token.txt", "w") as f:
                                    f.write(token)
                                print(f"PYPI_TOKEN={token}")
                            else:
                                page.screenshot(path="/tmp/pypi_token_result.png")
                                log("Token created but couldn't extract text")
                
                browser.close()
                sys.exit(0)
            else:
                log(f"❌ Login failed with secret {TOTP_SECRET[:12]}...")
                page.screenshot(path=f"/tmp/pypi_fail_{TOTP_SECRET[:12]}.png")
                browser.close()
    except Exception as e:
        log(f"Error: {e}")

log("❌ All TOTP secrets failed")
sys.exit(1)
