"""Debug: trace PyPI login cookies and session behavior with Playwright."""
import os, sys, json, time
from playwright.sync_api import sync_playwright

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]

def log(msg):
    print(msg, flush=True)

log("=== Debug PyPI Login Session ===")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    )
    
    # --- Login ---
    page = context.new_page()
    page.goto('https://pypi.org/account/login/', wait_until='networkidle', timeout=60000)
    
    log(f"Before login - cookies: {context.cookies()}")
    form_action = page.evaluate('''() => {
        const form = document.querySelector('form[action*="login"], form');
        if (form) return form.action || form.getAttribute('action');
        return 'no form found';
    }')
    log(f"Login form action: {form_action}")
    
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    
    # Listen for all responses
    responses = []
    page.on('response', lambda r: responses.append({
        'url': r.url,
        'status': r.status,
        'headers': dict(r.headers),
    }))
    
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle', timeout=60000)
    
    log(f"After login - URL: {page.url}")
    log(f"After login - cookies: {context.cookies()}")
    log(f"After login - storage: {json.dumps(context.storage_state() or {})[:500]}")
    
    # Check page content for session info
    session_info = page.evaluate('''() => {
        const body = document.body;
        const hasLogout = document.body.innerText.includes('Log out') || document.body.innerText.includes('Sign out');
        const hasLogin = document.body.innerText.includes('Log in') || document.body.innerText.includes('Sign in');
        const nav = document.querySelector('nav') || document.querySelector('.header');
        return {
            hasLogout,
            hasLogin,
            pageSourceSubstring: document.body.innerHTML.substring(0, 4000),
        };
    }')
    log(f"Session check: {json.dumps(session_info, indent=2)[:3000]}")
    
    # --- Check if we can access token page via click navigation ---
    # Look for any "account" or "settings" link
    account_links = page.evaluate('''() => {
        const links = Array.from(document.querySelectorAll('a'));
        return links.filter(l => 
            l.href.includes('account') || l.href.includes('token') || 
            l.href.includes('settings') || l.href.includes('profile')
        ).map(l => ({text: l.innerText.trim(), href: l.href}));
    }')
    log(f"Account-related links: {json.dumps(account_links, indent=2)}")
    
    # Try JavaScript navigation instead of goto
    log("Trying JS navigation to token page...")
    page.evaluate('window.location.href = "https://pypi.org/manage/account/token/"')
    page.wait_for_load_state('networkidle', timeout=60000)
    log(f"After JS nav - URL: {page.url}")
    log(f"After JS nav - cookies: {context.cookies()}")
    
    page.screenshot(path='/tmp/pypi_debug_final.png')
    
    # Try once more: create a new page in the same context
    log("Trying new page in same context...")
    page2 = context.new_page()
    page2.goto('https://pypi.org/manage/account/token/', wait_until='networkidle', timeout=60000)
    log(f"New page URL: {page2.url}")
    page2.screenshot(path='/tmp/pypi_debug_newpage.png')
    
    log("\n=== Debug Done ===")
    browser.close()
