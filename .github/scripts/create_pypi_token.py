"""Create PyPI API token using Playwright (real browser).
Uses password-only login (no TOTP needed from GitHub runner IP)."""
import os, sys, re, time
from playwright.sync_api import sync_playwright

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
TOKEN_NAME = "gh-actions-publisher"

def log(msg):
    print(msg, flush=True)

log("=== Starting Playwright PyPI Token Creator ===")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=[
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
    ])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        locale='en-US',
    )
    
    # === Step 1: Login ===
    log("Step 1: Navigating to login page...")
    page = context.new_page()
    page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=60000)
    page.screenshot(path='/tmp/pypi_01_login_page.png')
    log(f"  URL: {page.url}")
    
    log("Step 2: Filling login form...")
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    
    # Click submit and wait for navigation
    with page.expect_navigation(wait_until='networkidle', timeout=60000):
        page.click('button[type="submit"]')
    
    page.screenshot(path='/tmp/pypi_02_after_login.png')
    log(f"  URL: {page.url}")
    
    # Check if we hit TOTP page
    if 'two-factor' in page.url.lower():
        log("  ⚠️ TOTP page appeared! Trying codes...")
        import pyotp
        secret = os.environ.get("PYPI_TOTP_SECRET", "")
        if not secret:
            log("  ❌ No TOTP secret configured!")
            browser.close()
            sys.exit(1)
        totp = pyotp.TOTP(secret)
        now = int(time.time())
        codes = set()
        for offset in range(-4, 5):
            codes.add(totp.at(now + offset * 30))
        
        success = False
        for code in sorted(codes):
            log(f"  Trying code={code}...", end='')
            page.fill('input[name="totp_value"]', str(code))
            with page.expect_navigation(wait_until='networkidle', timeout=30000):
                page.click('button[type="submit"]')
            if 'two-factor' not in page.url.lower() and 'login' not in page.url.lower():
                log(" ✅")
                success = True
                page.screenshot(path='/tmp/pypi_02_totp_success.png')
                break
            log(" ❌")
            page.screenshot(path='/tmp/pypi_02_totp_fail.png')
        
        if not success:
            log("  ❌ All TOTP codes failed!")
            browser.close()
            sys.exit(1)
    
    # === Step 2: Verify session is active ===
    log(f"Step 3: Verifying session (URL: {page.url})...")
    page_content = page.content()
    page.screenshot(path='/tmp/pypi_03_session_check.png')
    
    # Check if we see any logged-in indicators
    is_logged_in = False
    if 'Log out' in page_content or 'logout' in page_content.lower():
        is_logged_in = True
        log("  ✅ Session active (found 'Log out' link)")
    elif 'login' in page.url.lower() and 'next' in page.url:
        log("  ❌ Redirected to login - session not established")
        # Save full HTML for debugging
        with open('/tmp/pypi_login_page_debug.html', 'w') as f:
            f.write(page_content[:10000])
        browser.close()
        sys.exit(1)
    
    if not is_logged_in:
        log("  ⚠️ Could not confirm login status, proceeding anyway...")
    
    # === Step 3: Navigate to token page ===
    log("Step 4: Going to token management page...")
    # Use goto - should maintain cookies from the same context
    page.goto('https://pypi.org/manage/account/token/', wait_until='networkidle', timeout=60000)
    page.screenshot(path='/tmp/pypi_04_token_page.png')
    log(f"  URL: {page.url}")
    
    if 'login' in page.url.lower():
        log("  ❌ Session not authenticated for token page!")
        
        # Maybe the original page had the session but cookies didn't carry
        # Try going through account link
        log("  Trying alternative: use context cookies to re-authenticate...")
        
        # Go back to home and check if we're logged in there
        page.goto('https://pypi.org/', wait_until='networkidle', timeout=30000)
        log(f"  Home URL: {page.url}")
        content = page.content()
        if 'Log out' in content or 'logout' in content.lower():
            log("  ✅ Session present on homepage! Clicking account link...")
            # Click the account/user menu to find token link
            account_link = page.query_selector('a[href*="account"]')
            if account_link:
                account_link.click()
                page.wait_for_load_state('networkidle', timeout=30000)
                log(f"  Account URL: {page.url}")
                page.screenshot(path='/tmp/pypi_04_account_page.png')
                
                # Find token management link
                token_link = page.query_selector('a[href*="token"]')
                if token_link:
                    token_link.click()
                    page.wait_for_load_state('networkidle', timeout=30000)
                    log(f"  Token URL: {page.url}")
                    page.screenshot(path='/tmp/pypi_04_token_via_link.png')
        else:
            log("  ❌ Session also lost on homepage!")
            with open('/tmp/pypi_homepage_debug.html', 'w') as f:
                f.write(content[:5000])
            browser.close()
            sys.exit(1)
    
    if 'login' in page.url.lower():
        log("  ❌ Still not authenticated!")
        browser.close()
        sys.exit(1)
    
    log("  ✅ Token page loaded successfully!")
    
    # === Step 4: Handle password confirmation if needed ===
    confirm_input = page.query_selector('input[name="confirm_password_input"]')
    if confirm_input:
        log("Step 5: Password confirmation required...")
        confirm_input.fill(PASS)
        with page.expect_navigation(wait_until='networkidle', timeout=30000):
            page.click('button[type="submit"]')
        page.screenshot(path='/tmp/pypi_05_confirmed.png')
        log(f"  URL: {page.url}")
        if 'login' in page.url.lower():
            log("  ❌ Auth lost during password confirmation!")
            browser.close()
            sys.exit(1)
    
    # === Step 5: Create token ===
    log("Step 6: Creating token...")
    name_input = page.query_selector('input[name="name"]')
    if not name_input:
        log("  ❌ Could not find token name input!")
        log(f"  HTML snippet: {page.content()[:2000]}")
        page.screenshot(path='/tmp/pypi_06_no_input.png')
        browser.close()
        sys.exit(1)
    
    name_input.fill(TOKEN_NAME)
    with page.expect_navigation(wait_until='networkidle', timeout=30000):
        page.click('button[type="submit"]')
    
    page.screenshot(path='/tmp/pypi_06_token_submitted.png')
    log(f"  URL: {page.url}")
    
    # === Step 6: Extract token ===
    log("Step 7: Extracting token...")
    content = page.content()
    
    # Look for pypi-xxx token pattern
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
        # Try alert boxes
        alerts = re.findall(r'class="[^"]*alert-success[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
        for alert in alerts:
            m = re.search(r'pypi-[\w-]{30,}', alert)
            if m:
                token = m.group(0)
                log(f"✅ TOKEN (from alert): {token}")
                with open('/tmp/pypi_token.txt', 'w') as f:
                    f.write(token)
                break
        else:
            log("❌ Token not found!")
            log(f"  Page content (first 3000):\n{content[:3000]}")
    
    browser.close()
    log("\n=== Done ===")
