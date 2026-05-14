"""Create PyPI API token via HTTP requests from GitHub runner (clean IP + accurate clock).
This avoids Cloudflare browser challenges and TOTP clock drift issues."""
import requests, re, os, json, time, sys
import pyotp

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-trusted-publisher"

BASE = "https://pypi.org"
LOGIN_URL = f"{BASE}/account/login/"
TOTP_URL = f"{BASE}/two-factor/"
TOKEN_URL = f"{BASE}/manage/account/token/create/"
TOKEN_LIST_URL = f"{BASE}/manage/account/token/"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

def get_csrf(html, name="csrf_token"):
    m = re.search(rf'name="{name}"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None

def get_title(html):
    m = re.search(r'<title>([^<]*)', html)
    return m.group(1) if m else "???"

# Step 1: GET login page
print("=== Step 1: GET login page ===", flush=True)
r = session.get(LOGIN_URL, timeout=30)
print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)

csrf = get_csrf(r.text)
if not csrf:
    print("ERROR: No CSRF token found!", flush=True)
    sys.exit(1)
print(f"CSRF: {csrf[:20]}...", flush=True)

# Step 2: POST login
print("\n=== Step 2: POST login ===", flush=True)
r = session.post(LOGIN_URL, data={
    "csrf_token": csrf,
    "username": USER,
    "password": PASS,
}, allow_redirects=False, timeout=30)
print(f"Status: {r.status_code}, Location: {r.headers.get('Location','N/A')}", flush=True)

# Step 3: TOTP
if r.status_code in (302, 303) and "two-factor" in r.headers.get("Location", ""):
    totp_url = BASE + r.headers["Location"]
    print(f"\n=== Step 3: TOTP page ({totp_url}) ===", flush=True)
    r = session.get(totp_url, timeout=30)
    print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)
    
    csrf = get_csrf(r.text)
    if not csrf:
        # Try alternative name
        csrf = get_csrf(r.text, "csrfmiddlewaretoken")
    print(f"CSRF: {csrf[:20] if csrf else 'N/A'}...", flush=True)
    
    # Generate TOTP code
    code = pyotp.TOTP(SECRET).now()
    print(f"TOTP code: {code}", flush=True)
    
    r = session.post(totp_url, data={
        "csrf_token": csrf,
        "code": code,
        "method": "totp",
    }, allow_redirects=False, timeout=30)
    print(f"Status: {r.status_code}, Location: {r.headers.get('Location','N/A')}", flush=True)
    
    # Follow redirect
    if r.status_code in (302, 303):
        next_url = BASE + r.headers["Location"]
        print(f"Following to: {next_url}", flush=True)
        r = session.get(next_url, timeout=30)
        print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)
        
        # Check for password confirmation
        if "password" in r.url.lower() and "confirm" in r.url.lower():
            print("\n=== Password confirmation ===", flush=True)
            csrf = get_csrf(r.text)
            r = session.post(r.url, data={
                "csrf_token": csrf,
                "password": PASS,
            }, allow_redirects=False, timeout=30)
            print(f"Status: {r.status_code}, Location: {r.headers.get('Location','N/A')}", flush=True)
            if r.status_code in (302, 303):
                r = session.get(BASE + r.headers["Location"], timeout=30)
                print(f"After password: Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)

# Step 4: Create token
print(f"\n=== Step 4: Create token '{TOKEN_NAME}' ===", flush=True)
r = session.get(TOKEN_URL, timeout=30)
print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)

csrf = get_csrf(r.text)
print(f"CSRF: {csrf[:20] if csrf else 'N/A'}...", flush=True)

r = session.post(TOKEN_URL, data={
    "csrf_token": csrf,
    "name": TOKEN_NAME,
    "scope": "user",
}, allow_redirects=False, timeout=30)
print(f"Status: {r.status_code}, Location: {r.headers.get('Location','N/A')}", flush=True)

# Step 5: Extract token from response
if r.status_code in (302, 303):
    # Token was created, follow to see it
    token_page = BASE + r.headers["Location"]
    print(f"Token page: {token_page}", flush=True)
    r = session.get(token_page, timeout=30)
    print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)
    
    # Save the page for parsing
    with open("/tmp/token_page.html", "w") as f:
        f.write(r.text)
    
    # Try to find token in page
    m = re.search(r'pypi-[A-Za-z0-9_-]+', r.text)
    if m:
        token = m.group(0)
        print(f"\n{'='*60}", flush=True)
        print(f"TOKEN FOUND: {token}", flush=True)
        print(f"{'='*60}", flush=True)
        # Save to file for later use
        with open("/tmp/pypi_token.txt", "w") as f:
            f.write(token)
        # Also set as output via GITHUB_ENV
        if "GITHUB_ENV" in os.environ:
            with open(os.environ["GITHUB_ENV"], "a") as f:
                f.write(f"PYPI_TOKEN={token}\n")
        # Set as step output
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"token={token}\n")
        print("\nToken saved to /tmp/pypi_token.txt", flush=True)
    else:
        print("Token pattern not found in page. Looking for alternatives...", flush=True)
        # Check if it's in a flash message or alert
        m2 = re.search(r'(?:token|Token)[:\s]+([A-Za-z0-9_-]+)', r.text)
        if m2:
            print(f"Alternative match: {m2.group(1)}", flush=True)
        # Print part of page for debugging
        print(f"\nPage snippet (500-1500): {r.text[500:1500]}", flush=True)

elif r.status_code == 200 and "token" in r.text.lower():
    print("Got 200 response, token might be in response body", flush=True)
    with open("/tmp/token_response.html", "w") as f:
        f.write(r.text)
    m = re.search(r'pypi-[A-Za-z0-9_-]+', r.text)
    if m:
        token = m.group(0)
        print(f"\nTOKEN: {token}", flush=True)
        with open("/tmp/pypi_token.txt", "w") as f:
            f.write(token)

# Check token list to confirm
print(f"\n=== Checking token list ===", flush=True)
r = session.get(TOKEN_LIST_URL, timeout=30)
print(f"Status: {r.status_code}, Title: {get_title(r.text)}", flush=True)
if TOKEN_NAME in r.text:
    print(f"✓ Token '{TOKEN_NAME}' confirmed in token list!", flush=True)
else:
    print(f"Token '{TOKEN_NAME}' not found in list", flush=True)
