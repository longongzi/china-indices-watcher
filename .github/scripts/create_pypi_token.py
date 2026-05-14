"""Create PyPI API token via Playwright headless browser on GitHub runner."""
import os, sys, json, re
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-actions-publisher"

import pyotp

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='UTC',
        )
        page = ctx.new_page()
        
        # 1. Go to login
        print("=== Navigate to login ===", flush=True)
        page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        
        # 2. Fill login form
        print("=== Fill login form ===", flush=True)
        page.fill('input[name="username"]', USER)
        page.fill('input[name="password"]', PASS)
        
        # Click login button - wait for navigation
        print("=== Submit login ===", flush=True)
        with page.expect_navigation(timeout=30000) as nav_info:
            page.click('button[type="submit"]')
        
        final_url = nav_info.value.url
        print(f"After login: {final_url}", flush=True)
        
        # 3. Handle TOTP
        if 'two-factor' in final_url:
            print("=== TOTP page ===", flush=True)
            page.wait_for_timeout(1000)
            
            # Try up to 3 times with different TOTP codes
            for attempt in range(3):
                code = pyotp.TOTP(SECRET).now()
                print(f"TOTP attempt {attempt+1}: code={code}", flush=True)
                
                page.fill('input[name="totp_value"]', code)
                
                try:
                    with page.expect_navigation(timeout=30000) as nav_info2:
                        page.click('button[type="submit"]')
                    
                    result_url = nav_info2.value.url
                    print(f"After TOTP: {result_url}", flush=True)
                    
                    # Check if we got past TOTP
                    if 'two-factor' not in result_url.lower():
                        print("✅ TOTP accepted!", flush=True)
                        break
                    else:
                        # Try to find error message
                        error_el = page.query_selector('.error-message, .alert-error, [class*="error"]')
                        if error_el:
                            print(f"Error on page: {error_el.inner_text()}", flush=True)
                        print(f"Still on TOTP page, retrying...", flush=True)
                        
                        # Handle rate limit: wait 90 seconds
                        if 'too many' in (page.content().lower()):
                            print("Rate limited! Waiting 90 seconds...", flush=True)
                            page.wait_for_timeout(90000)
                            # Reload and re-login
                            page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=30000)
                            page.fill('input[name="username"]', USER)
                            page.fill('input[name="password"]', PASS)
                            with page.expect_navigation(timeout=30000):
                                page.click('button[type="submit"]')
                            page.wait_for_timeout(2000)
                            continue
                        
                        # Give up after attempt
                        if attempt >= 2:
                            print("❌ TOTP failed after all attempts", flush=True)
                            page.screenshot(path='/tmp/totp_failed.png')
                            sys.exit(1)
                except PwTimeout:
                    print(f"Timeout on TOTP attempt {attempt+1}", flush=True)
                    page.screenshot(path=f'/tmp/totp_timeout_{attempt}.png')
            
        else:
            print("No TOTP required, already logged in?", flush=True)
        
        # 4. Navigate to token creation
        print("=== Navigate to token page ===", flush=True)
        page.goto('https://pypi.org/manage/account/token/', wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        
        if 'login' in page.url.lower():
            print("❌ Redirected to login - session not authenticated", flush=True)
            page.screenshot(path='/tmp/redirected_to_login.png')
            sys.exit(1)
        
        # 5. Find token name input and submit
        print("=== Create token ===", flush=True)
        name_input = page.query_selector('input[name="name"]')
        if name_input:
            name_input.fill(TOKEN_NAME)
            with page.expect_navigation(timeout=30000) as nav_info3:
                page.click('button[type="submit"]')
            
            token_url = nav_info3.value.url
            print(f"After create: {token_url}", flush=True)
            
            # Wait for the page to load
            page.wait_for_timeout(2000)
            
            # Extract token from page
            content = page.content()
            
            # PyPI shows the token in a special div/section
            # Try multiple patterns
            token_patterns = [
                r'pypi-[\w-]+',
                r'value="(pypi-[^"]+)"',
                r'(pypi-[A-Za-z0-9_-]+)',
                r'[A-Za-z0-9_-]{40,}',
            ]
            
            found_token = None
            for p in token_patterns:
                m = re.search(p, content)
                if m:
                    found_token = m.group(1) if m.lastindex else m.group(0)
                    if found_token.startswith('pypi-'):
                        break
            
            if found_token:
                print(f"\n{'='*60}", flush=True)
                print(f"✅ TOKEN: {found_token}", flush=True)
                print(f"{'='*60}", flush=True)
                with open('/tmp/pypi_token.txt', 'w') as f:
                    f.write(found_token)
                if 'GITHUB_OUTPUT' in os.environ:
                    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                        f.write(f"token={found_token}\n")
            else:
                # Check for success alert
                success_els = page.query_selector_all('.alert-block, .alert-success')
                for el in success_els:
                    text = el.inner_text()
                    print(f"Success alert: {text[:200]}", flush=True)
                    if not found_token:
                        for p in token_patterns:
                            m = re.search(p, text)
                            if m:
                                found_token = m.group(0)
                                print(f"✅ TOKEN from alert: {found_token}", flush=True)
                                break
                
                if not found_token:
                    print(f"Token not found in page. Content preview: {content[:1000]}", flush=True)
                    page.screenshot(path='/tmp/token_page.png')
        else:
            print(f"No name input found. Page: {page.content()[:1000]}", flush=True)
            # Maybe the form structure is different
            inputs = page.query_selector_all('input')
            for inp in inputs:
                print(f"  Input: name={inp.get_attribute('name')}, type={inp.get_attribute('type')}", flush=True)
            page.screenshot(path='/tmp/token_form.png')
        
        # 6. Verify
        print("=== Verify ===", flush=True)
        page.goto('https://pypi.org/manage/account/token/', wait_until='networkidle', timeout=30000)
        if TOKEN_NAME in page.content():
            print(f"✅ Token '{TOKEN_NAME}' verified on page!", flush=True)
        elif os.path.exists('/tmp/pypi_token.txt'):
            print("✅ Token file exists.", flush=True)
        else:
            print("❌ Token verification failed", flush=True)
        
        browser.close()
        print("\n=== Done ===", flush=True)

if __name__ == '__main__':
    main()
