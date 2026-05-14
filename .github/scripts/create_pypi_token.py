"""Debug: trace PyPI login cookies and session behavior with Playwright."""
import os, sys, json, time
from playwright.sync_api import sync_playwright

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]

def log(msg):
    print(msg, flush=True)

log("=== Debug PyPI Login Session ===")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=[
        "--no-sandbox", "--disable-setuid-sandbox"
    ])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    )
    
    # --- Login ---
    page = context.new_page()
    page.goto("https://pypi.org/account/login/", wait_until="networkidle", timeout=60000)
    
    log("Before login - cookies: " + str(context.cookies()))
    
    # form action
    fa = page.evaluate("""() => {
        var f = document.querySelector('form');
        if (f) return f.action || f.getAttribute('action');
        return 'no form found';
    }""")
    log("Login form action: " + str(fa))
    
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    
    # Listen for responses
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=60000)
    
    log("After login - URL: " + page.url)
    log("After login - cookies: " + str(context.cookies()))
    
    # Check session indicators
    has_logout = page.evaluate("""() => {
        var txt = document.body.innerText;
        return txt.indexOf('Log out') >= 0 || txt.indexOf('Sign out') >= 0;
    }""")
    has_login = page.evaluate("""() => {
        var txt = document.body.innerText;
        return txt.indexOf('Log in') >= 0 || txt.indexOf('Sign in') >= 0;
    }""")
    log("Has Log out link: " + str(has_logout))
    log("Has Log in link: " + str(has_login))
    
    # Account links
    links = page.evaluate("""() => {
        var all = Array.from(document.querySelectorAll('a'));
        var matches = [];
        for (var i = 0; i < all.length; i++) {
            var h = all[i].href;
            if (h.indexOf('account') >= 0 || h.indexOf('settings') >= 0 || h.indexOf('token') >= 0) {
                matches.push({text: all[i].innerText.trim(), href: h});
            }
        }
        return JSON.stringify(matches);
    }""")
    log("Account links: " + links)
    
    # Try JS navigation
    log("Trying JS navigation to token page...")
    page.evaluate("""window.location.href = 'https://pypi.org/manage/account/token/'""")
    page.wait_for_load_state("networkidle", timeout=60000)
    log("After JS nav - URL: " + page.url)
    log("After JS nav - cookies: " + str(context.cookies()))
    
    page.screenshot(path="/tmp/pypi_debug_final.png")
    
    # Try new page in same context
    log("Trying new page in same context...")
    page2 = context.new_page()
    page2.goto("https://pypi.org/manage/account/token/", wait_until="networkidle", timeout=60000)
    log("New page URL: " + page2.url)
    page2.screenshot(path="/tmp/pypi_debug_newpage.png")
    
    log("=== Debug Done ===")
    browser.close()
