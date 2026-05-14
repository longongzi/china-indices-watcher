"""Create a PyPI API token using Playwright and save it for upload."""
import os, sys, json, re, time
from playwright.sync_api import sync_playwright

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-actions-token"
OUTPUT_PATH = "/tmp/pypi_token.txt"

def log(msg):
    print(msg, flush=True)

log("=== PyPI API Token Creator ===")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    # --- Step 1: Login ---
    log("Navigating to login page...")
    page.goto("https://pypi.org/account/login/", wait_until="networkidle", timeout=60000)
    log(f"Login page loaded: {page.url}")

    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=60000)
    log(f"After login: {page.url}")

    # --- Step 2: TOTP if needed ---
    if "two-factor" in page.url.lower():
        log("TOTP page detected, entering code...")
        page.fill('input[name="totp_value"]', "")
        import pyotp
        # Try multiple time windows
        totp = pyotp.TOTP(SECRET)
        base_time = int(time.time()) // 30
        for offset in [-2, -1, 0, 1, 2]:
            code = totp.at(base_time + offset)
            page.fill('input[name="totp_value"]', str(code))
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=60000, state="networkidle")
            if "two-factor" not in page.url.lower():
                log(f"TOTP accepted at offset={offset}, URL: {page.url}")
                break
            log(f"  offset={offset} rejected, trying next...")
            page.goto(page.url, wait_until="networkidle", timeout=30000)
        else:
            log("FATAL: All TOTP offsets failed")
            sys.exit(1)

    # --- Step 3: Navigate to token management page via JS ---
    # IMPORTANT: Use window.location.href instead of page.goto() to preserve session cookies
    log("Navigating to token management page via JS...")
    page.evaluate("""window.location.href = 'https://pypi.org/manage/account/token/'""")
    page.wait_for_load_state("networkidle", timeout=60000)
    log(f"Token page: {page.url} ({len(page.content())} chars)")

    # --- Step 4: Handle password confirmation if needed ---
    page_content = page.content()
    if "confirm_password" in page_content.lower():
        log("Password confirmation required...")
        page.fill('input[name="confirm_password_input"]', PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=60000)
        log(f"After password confirmation: {page.url}")
        # Re-navigate to token page via JS
        page.evaluate("""window.location.href = 'https://pypi.org/manage/account/token/'""")
        page.wait_for_load_state("networkidle", timeout=60000)
        log(f"Token page after confirm: {page.url}")

    # --- Step 5: Create the token ---
    log("Creating API token...")

    page_content = page.content()
    # Try to find and use the create token form
    has_form = page.evaluate("""() => {
        var inputs = document.querySelectorAll('input[name="name"]');
        return inputs.length > 0;
    }""")

    if has_form:
        log("Token creation form detected, filling...")
        page.fill('input[name="name"]', TOKEN_NAME)

        # Submit the form
        page.evaluate("""() => {
            var btn = document.querySelector('button[type="submit"]');
            if (btn) btn.click();
        }""")
        page.wait_for_load_state("networkidle", timeout=60000)
        log(f"After token creation: {page.url}")
    else:
        log("No form detected on token page")

    # --- Step 6: Extract the token ---
    log("Extracting token from page...")
    current_text = page.content()
    token = None

    # Pattern: pypi-xxxx...xxxx (long string)
    # The token appears in a success alert after creation
    for pattern in [
        r'pypi-[A-Za-z0-9_-]{30,}',
        r'pypi-[A-Za-z0-9._-]+'
    ]:
        matches = re.findall(pattern, current_text)
        for m in matches:
            if len(m) > 30:  # Real tokens are long
                token = m
                log(f"Found token candidate: {m[:20]}...")
                break
        if token:
            break

    # Also check the page text more carefully
    body_text = page.evaluate("() => document.body.innerText")
    for pattern in [
        r'pypi-[A-Za-z0-9_-]{30,}',
        r'pypi-[A-Za-z0-9._-]+'
    ]:
        matches = re.findall(pattern, body_text)
        for m in matches:
            if len(m) > 30 and (not token or len(m) > len(token)):
                token = m
                log(f"Found token in body text: {m[:20]}...")
                break
        if token and len(token) > 40:
            break

    if token:
        log(f"\n✅✅ TOKEN FOUND: {token}")
        with open(OUTPUT_PATH, 'w') as f:
            f.write(token.strip())
        log(f"Saved to {OUTPUT_PATH}")

        # Verify the file
        with open(OUTPUT_PATH, 'r') as f:
            verify = f.read().strip()
        log(f"Verified: {verify[:20]}... ({len(verify)} chars)")
    else:
        log("\n❌ Token not found in page response")
        log(f"Body text (first 2000 chars):\n{body_text[:2000]}")
        page.screenshot(path="/tmp/pypi_token_debug.png")
        log("Screenshot saved to /tmp/pypi_token_debug.png")

        # Try to check if we're logged in
        logged_in = "log out" in body_text.lower() or "sign out" in body_text.lower()
        log(f"Logged in: {logged_in}")
        sys.exit(1)

    browser.close()

log("=== Done ===")
