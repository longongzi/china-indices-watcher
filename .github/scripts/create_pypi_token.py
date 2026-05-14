"""Create PyPI token - tries multiple TOTP time windows, prints full responses."""
import requests, re, os, time, sys
import pyotp

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-actions-publisher"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/x-www-form-urlencoded',
}

session = requests.Session()

# 1) GET login page
print("=== Step 1: Get login page ===", flush=True)
r = session.get('https://pypi.org/account/login/', headers=headers, timeout=30)
csrf = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
csrf = csrf.group(1) if csrf else None
print(f"GET login: {r.status_code}, csrf={csrf[:20] if csrf else None}", flush=True)

# 2) POST login credentials
print("\n=== Step 2: Login ===", flush=True)
r = session.post('https://pypi.org/account/login/',
    data={'csrf_token': csrf, 'username': USER, 'password': PASS},
    headers=headers, timeout=30)
print(f"POST login: {r.status_code}, url={r.url[:100]}", flush=True)

if 'two-factor' not in r.url:
    print(f"ERROR: Not on TOTP page. Body: {r.text[:800]}", flush=True)
    # Maybe no TOTP needed? Try token page directly
    print("\n=== Trying token page directly ===", flush=True)
    r2 = session.get('https://pypi.org/manage/account/token/', headers=headers, timeout=30)
    print(f"Token page: {r2.status_code}, url={r2.url[:80]}", flush=True)
    if 'login' in r2.url.lower():
        print("Session not authenticated.", flush=True)
        sys.exit(1)
    print("Already on token page!", flush=True)
    sys.exit(0)

# 3) Submit TOTP with wide window
print(f"\n=== Step 3: TOTP ===", flush=True)
topt_url = r.url.split('?')[0]  # Base URL without query params
totp_page_html = r.text

totp = pyotp.TOTP(SECRET)
for attempt in range(5):
    csrf = re.search(r'name="csrf_token".*?value="([^"]+)"', totp_page_html)
    csrf = csrf.group(1) if csrf else None
    
    # Try codes from multiple time windows (-60s to +60s)
    now = int(time.time())
    codes = set()
    for offset in range(-2, 3):
        codes.add(totp.at(now + offset*30))
    
    print(f"Attempt {attempt+1}: windows={[totp.at(now+i*30) for i in range(-2,3)]}", flush=True)
    
    for code in codes:
        r = session.post(r.url, 
            data={'csrf_token': csrf, 'totp_value': code, 'method': 'totp'},
            headers=headers, allow_redirects=False, timeout=30)
        
        print(f"  TOTP code={code}: status={r.status_code}, Location={r.headers.get('location','none')[:60]}", flush=True)
        
        if r.status_code in (302, 303):
            loc = r.headers['location']
            print(f"  ✅ TOTP accepted! Redirect to: {loc[:60]}", flush=True)
            r2 = session.get(loc if loc.startswith('http') else 'https://pypi.org'+loc,
                headers=headers, timeout=30)
            print(f"  After redirect: {r2.status_code}, url={r2.url[:80]}", flush=True)
            break
        elif r.status_code == 429:
            print(f"  ⏱️ Rate limited! Body: {r.text[:300]}", flush=True)
            time.sleep(90)
            # Re-login
            print("  Re-login...", flush=True)
            r_log = session.get('https://pypi.org/account/login/', headers=headers, timeout=30)
            csrf2 = re.search(r'name="csrf_token".*?value="([^"]+)"', r_log.text)
            csrf2 = csrf2.group(1) if csrf2 else None
            r_log = session.post('https://pypi.org/account/login/',
                data={'csrf_token': csrf2, 'username': USER, 'password': PASS},
                headers=headers, timeout=30)
            if 'two-factor' in r_log.url:
                totp_page_html = r_log.text
                r = r_log  # Update r.url to the new TOTP page URL
        elif r.status_code == 200:
            # Look for error message in the page
            errors = re.findall(r'(?:error|alert|invalid)[^>]*>([^<]+)', r.text, re.IGNORECASE)
            print(f"  ❌ TOTP rejected. Page errors: {errors[:5]}", flush=True)
            # Print some key parts of the page
            title = re.search(r'<title>([^<]+)', r.text)
            print(f"  Page title: {title.group(1) if title else 'N/A'}", flush=True)
            # Check if it's the TOTP page again
            if 'two-factor' in r.url:
                print(f"  (Stayed on TOTP page)", flush=True)
    else:
        if attempt >= 3:
            print("TOTP failed after all attempts", flush=True)
            # Print full TOTP page HTML
            print(f"\nFull TOTP page ({len(totp_page_html)} chars):", flush=True)
            print(totp_page_html[:2000], flush=True)
            sys.exit(1)
        time.sleep(2)
        continue
    break

# 4) Create token
print(f"\n=== Step 4: Create token ===", flush=True)
r = session.get('https://pypi.org/manage/account/token/', headers=headers, timeout=30)
print(f"Token page: {r.status_code}, url={r.url[:80]}", flush=True)

if 'login' in r.url.lower():
    print("Session not authenticated!", flush=True)
    sys.exit(1)

csrf = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
csrf = csrf.group(1) if csrf else None
print(f"CSRF: {csrf[:30] if csrf else 'NONE'}", flush=True)

r = session.post('https://pypi.org/manage/account/token/',
    data={'csrf_token': csrf, 'name': TOKEN_NAME},
    headers=headers, allow_redirects=False, timeout=30)
print(f"Create token: {r.status_code}", flush=True)

if r.status_code in (302, 303):
    loc = r.headers['location']
    r = session.get(loc if loc.startswith('http') else 'https://pypi.org'+loc,
        headers=headers, timeout=30)

# Extract token
tok = re.search(r'pypi-[\w-]+', r.text)
if tok:
    print(f"\n{'='*60}", flush=True)
    print(f"✅ TOKEN: {tok.group(0)}", flush=True)
    print(f"{'='*60}", flush=True)
    with open('/tmp/pypi_token.txt', 'w') as f:
        f.write(tok.group(0))
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"token={tok.group(0)}\n")
else:
    print(f"Token not found in response. Body: {r.text[:1500]}", flush=True)

print("\n=== Done ===", flush=True)
