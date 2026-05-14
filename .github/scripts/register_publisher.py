"""Register a Trusted Publisher on PyPI for a new project, using Playwright.
Runs on GitHub runner (clean IP, accurate clock) to bypass Cloudflare/TOTP issues."""
import os, sys, time, json
from playwright.sync_api import sync_playwright
import pyotp

PYPI_USER = os.environ["PYPI_USER"]
PYPI_PASS = os.environ["PYPI_PASS"]
TOTP_SECRET = os.environ["PYPI_TOTP_SECRET"]
GITHUB_OWNER = "longongzi"
GITHUB_REPO = "china-indices-watcher"
WORKFLOW_FILE = ".github/workflows/pypi-publish.yml"
PACKAGE_NAME = "china-indices-watcher"

totp = pyotp.TOTP(TOTP_SECRET)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = ctx.new_page()

    # Step 1: Go to login page
    log("Navigating to PyPI login...")
    page.goto("https://pypi.org/account/login/", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    log(f"Title: {page.title()}")

    # Step 2: Fill login form
    log("Filling login form...")
    page.fill('input[name="username"]', PYPI_USER)
    page.fill('input[name="password"]', PYPI_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    log(f"After login submit - Title: {page.title()}")

    # Step 3: Handle TOTP
    if "two-factor" in page.url.lower() or "totp" in page.url.lower() or "Two-factor" in page.title():
        log("TOTP page detected, entering code...")
        # Generate TOTP code at the last moment
        code = totp.now()
        log(f"Generated TOTP code: {code}")
        
        # Wait for the input to be visible
        page.wait_for_selector('input[name="code"]', timeout=10000)
        page.fill('input[name="code"]', code)
        
        # Click the submit button (the one in the 2FA form, not search)
        page.click('button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        log(f"After TOTP - Title: {page.title()}, URL: {page.url}")
        
        # Check if we need password confirmation
        time.sleep(2)
        if "password" in page.url.lower():
            log("Password confirmation page...")
            page.fill('input[name="password"]', PYPI_PASS)
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
            log(f"After password confirm - Title: {page.title()}, URL: {page.url}")

    # Step 4: Navigate to project management page
    log("Navigating to manage projects...")
    page.goto("https://pypi.org/manage/project/", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    log(f"Manage projects page: {page.title()}")
    
    # Save page snapshot for debugging
    page.screenshot(path="/tmp/pypi_manage.png")
    html = page.content()
    with open("/tmp/pypi_manage.html", "w") as f:
        f.write(html)
    
    # Step 5: Look for "Create a new project" or "Add a new project" link/button
    # Check for the OIDC/pending publisher form
    log("Checking page content...")
    
    # Try multiple strategies to find the right link
    project_links = page.query_selector_all('a[href*="create"]')
    log(f"Links with 'create': {len(project_links)}")
    
    # Look for "Add a new project" text
    add_links = page.get_by_text("Add a new project", exact=False)
    count = add_links.count()
    log(f"'Add a new project' matches: {count}")
    
    # Step 6: Try the direct URL for setting up trusted publisher
    log("Trying direct trusted publisher setup...")
    
    # First try: go to project creation page
    page.goto("https://pypi.org/manage/project/create/", timeout=30000, wait_until="domcontentloaded")
    log(f"Create page: {page.title()}, URL: {page.url}")
    page.screenshot(path="/tmp/pypi_create.png")
    
    # Check for the OIDC/pending publisher form
    # Look for GitHub-related form elements
    log("Looking for GitHub trusted publisher form...")
    
    # Try to find and fill the trusted publisher form
    # The form typically has fields for GitHub owner, repo, workflow name
    forms_found = page.query_selector_all('form')
    log(f"Forms on page: {len(forms_found)}")
    
    # Also check if we're already on the right page
    full_html = page.content()
    with open("/tmp/pypi_create.html", "w") as f:
        f.write(full_html)
    
    # Try to find GitHub-related sections
    log("Analyzing page...")
    
    # Check various field names that PyPI might use
    for field_name in ["github_owner", "owner", "github_repository", "repository", 
                       "workflow_name", "workflow_filename", "environment"]:
        els = page.query_selector_all(f'[name="{field_name}"]')
        log(f"Field '{field_name}': {len(els)} found")
    
    # If we see a form we can fill, do it
    owner_input = page.query_selector('input[name="owner"]')
    if owner_input:
        log("Found 'owner' field, filling trusted publisher form...")
        owner_input.fill(GITHUB_OWNER)
        repo_input = page.query_selector('input[name="repository"]')
        if repo_input:
            repo_input.fill(GITHUB_REPO)
        wf_input = page.query_selector('input[name="workflow_filename"]')
        if wf_input:
            wf_input.fill(WORKFLOW_FILE)
        
        submit_btn = page.query_selector('button[type="submit"]')
        if submit_btn:
            submit_btn.click()
            page.wait_for_load_state("domcontentloaded")
            log(f"After submitting publisher form - URL: {page.url}")
            
            # Check result
            time.sleep(2)
            page.screenshot(path="/tmp/pypi_publisher_result.png")
            log(f"Final page content excerpt: {page.content()[:1000]}")
    
    # Take final screenshot
    page.screenshot(path="/tmp/pypi_final.png")
    log("Done! Check /tmp/ screenshots for results")
    
    browser.close()
