"""Create PyPI API token using Playwright (real browser) + TOTP."""
import os, sys, re, time
import pyotp
from playwright.sync_api import sync_playwright

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ.get("PYPI_TOTP_SECRET", "")
TOKEN_NAME = "gh-actions-publisher"

def log(msg):
    print(msg, flush=True)

log("=== Starting Playwright PyPI Token Creator ===")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
    ])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    # === Step 1: Go to login page ===
    log("Step 1: Navigating to login page...")
    page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=60000)
    page.screenshot(path='/tmp/pypi_step1_login.png')
    log(f"  URL: {page.url}")
    
    # === Step 2: Fill login form ===
    log("Step 2: Filling login form...")
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle', timeout=60000)
    page.screenshot(path='/tmp/pypi_step2_after_login.png')
    log(f"  URL: {page.url}")
    
    # === Step 3: Handle TOTP if needed ===
    if 'two-factor' in page.url.lower() or 'totp' in page.url.lower():
        log("Step 3: TOTP page detected, trying codes...")
        totp = pyotp.TOTP(SECRET)
        now = int(time.time())
        
        # Collect unique codes across wide time range
        codes_tried = set()
        for offset in range(-4, 5):
            codes_tried.add(totp.at(now + offset * 30))
        
        log(f"  Generated {len(codes_tried)} codes across ±4 windows")
        
        # Look for TOTP input
        totp_input = page.query_selector('input[name="totp_value"]')
        if not totp_input:
            log("  ❌ Could not find TOTP input field!")
            page.screenshot(path='/tmp/pypi_step3_totp_page.png')
            log(f"  Page HTML (first 2000 chars):\n{page.content()[:2000]}")
            browser.close()
            sys.exit(1)
        
        success = False
        for code in sorted(codes_tried):
            log(f"  Trying code={code}...", end='')
            totp_input.fill(str(code))
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=30000)
            
            if 'two-factor' not in page.url.lower() and 'login' not in page.url.lower():
                log(f" ✅ SUCCESS! Redirected to: {page.url[:80]}")
                success = True
                page.screenshot(path='/tmp/pypi_step3_totp_success.png')
                break
            elif 'Too Many Failed' in page.content() or 'too many' in page.content().lower():
                log(f" ❌ RATE LIMITED!")
                page.screenshot(path='/tmp/pypi_step3_ratelimited.png')
                # Re-navigate to login
                page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=60000)
                page.fill('input[name="username"]', USER)
                page.fill('input[name="password"]', PASS)
                page.click('button[type="submit"]')
                page.wait_for_load_state('networkidle', timeout=60000)
                if 'two-factor' in page.url.lower():
                    totp_input = page.query_selector('input[name="totp_value"]')
                else:
                    log("  After re-login, no TOTP page - checking status")
                    log(f"  URL: {page.url}")
                    break
            else:
                log(f" ❌ Rejected (URL: {page.url[:70]})")
        
        if not success:
            log("❌ All TOTP codes failed!")
            page.screenshot(path='/tmp/pypi_step3_all_failed.png')
            browser.close()
            sys.exit(1)
    else:
        log(f"Step 3: No TOTP required (URL: {page.url[:80]})")
        page.screenshot(path='/tmp/pypi_step3_no_totp.png')
    
    # === Step 4: Navigate to token page ===
    log("Step 4: Navigating to token management...")
    page.goto('https://pypi.org/manage/account/token/', wait_until='networkidle', timeout=60000)
    log(f"  URL: {page.url}")
    page.screenshot(path='/tmp/pypi_step4_token_page.png')
    
    if 'login' in page.url.lower():
        log("❌ SESSION NOT AUTHENTICATED!")
        browser.close()
        sys.exit(1)
    
    # === Step 5: Create token ===
    log("Step 5: Creating token...")
    
    # Handle optional password confirmation
    confirm_input = page.query_selector('input[name="confirm_password_input"]')
    if confirm_input:
        log("  Password confirmation required...")
        confirm_input.fill(PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle', timeout=30000)
        page.screenshot(path='/tmp/pypi_step5_confirmed.png')
        log(f"  After confirm: {page.url}")
    
    # Fill token name and submit
    name_input = page.query_selector('input[name="name"]')
    if name_input:
        name_input.fill(TOKEN_NAME)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle', timeout=30000)
        page.screenshot(path='/tmp/pypi_step6_token_created.png')
        log(f"  After submit: {page.url}")
    else:
        log("  ❌ Could not find token name input!")
        log(f"  Page HTML (first 2000):\n{page.content()[:2000]}")
        browser.close()
        sys.exit(1)
    
    # === Step 6: Extract token ===
    log("Step 6: Extracting token from page...")
    content = page.content()
    
    # Look for token pattern: pypi-xxxx...
    token_match = re.search(r'pypi-[\w-]{30,}', content)
    if token_match:
        token = token_match.group(0)
        log(f"\n{'='*60}")
        log(f"✅ TOKEN: {token}")
        log(f"{'='*60}")
        with open('/tmp/pypi_token.txt', 'w') as f:
            f.write(token)
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"token={token}\n")
    else:
        log("❌ Token not found in page!")
        # Try to find it in success alerts
        alerts = re.findall(r'class="[^"]*alert-success[^"]*"[^>]*>(.*?)</', content)
        for alert in alerts:
            m = re.search(r'pypi-[\w-]{30,}', alert)
            if m:
                token = m.group(0)
                log(f"✅ TOKEN (from alert): {token}")
                with open('/tmp/pypi_token.txt', 'w') as f:
                    f.write(token)
                break
        else:
            log(f"  Last URL: {page.url}")
            page.screenshot(path='/tmp/pypi_step6_no_token.png')
    
    browser.close()
    log("\n=== Done ===")
