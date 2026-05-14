"""Create PyPI API token via HTTP with TOTP, handling wide time windows + rate limits."""
import requests, re, os, time, sys
import pyotp

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-actions-publisher"

def bh(referer='https://pypi.org/account/login/', content_type=None):
    h = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': referer,
        'Origin': 'https://pypi.org',
    }
    if content_type:
        h['Content-Type'] = content_type
    return h

def extract_csrf(html):
    m = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)', html)
    if m: return m.group(1)
    m = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']csrf_token["\']', html)
    if m: return m.group(1)
    return None

session = requests.Session()

# === Step 1: GET login page ===
print("=== Step 1: GET login page ===", flush=True)
r = session.get('https://pypi.org/account/login/', headers=bh(), timeout=30)
csrf = extract_csrf(r.text)
print(f"GET login: {r.status_code}, csrf={'OK' if csrf else 'NONE'}", flush=True)
if not csrf:
    print(f"CSRF not found! Login HTML (first 1000 chars):\n{r.text[:1000]}", flush=True)
    sys.exit(1)

# === Step 2: POST login (to get TOTP page) ===
print("\n=== Step 2: POST login ===", flush=True)
r = session.post('https://pypi.org/account/login/',
    data={'csrf_token': csrf, 'username': USER, 'password': PASS},
    headers=bh(content_type='application/x-www-form-urlencoded'),
    allow_redirects=True, timeout=30)
print(f"POST login: {r.status_code}, url={r.url[:120]}", flush=True)

if 'two-factor' not in r.url:
    print(f"ERROR: Expected TOTP page. Body:\n{r.text[:1000]}", flush=True)
    sys.exit(1)

# === Step 3: Submit TOTP ===
print("\n=== Step 3: TOTP (multi-window) ===", flush=True)
totp = pyotp.TOTP(SECRET)
last_response = r  # Keep last response for url/html

totp_url = r.url
# Try 5 windows around current time
for attempt in range(8):
    now = int(time.time())
    # Generate codes for -4 to +4 windows (2 min range)
    codes_tried = set()
    for offset in range(-4, 5):
        codes_tried.add(totp.at(now + offset * 30))
    
    print(f"Attempt {attempt+1}: trying {len(codes_tried)} windows", flush=True)
    
    # Extract CSRF from current TOTP page
    csrf = extract_csrf(last_response.text)
    if not csrf:
        print("NO CSRF IN TOTP PAGE!", flush=True)
        print(f"TOTP page HTML (first 1500 chars):\n{last_response.text[:1500]}", flush=True)
        sys.exit(1)
    
    # Submit each code with fresh CSRF
    for code in sorted(codes_tried):
        r = session.post(totp_url,
            data={'csrf_token': csrf, 'totp_value': code, 'method': 'totp'},
            headers=bh(referer=totp_url, content_type='application/x-www-form-urlencoded'),
            allow_redirects=False, timeout=30)
        
        loc = r.headers.get('location', '')
        print(f"  code={code}: status={r.status_code}, Location={loc[:60]}", flush=True)
        
        if r.status_code in (302, 303, 301):
            print(f"  ✅ TOTP ACCEPTED! Redirecting to: {loc}", flush=True)
            # Follow redirect
            target = loc if loc.startswith('http') else 'https://pypi.org' + loc
            r = session.get(target, headers=bh(referer=totp_url), timeout=30)
            print(f"  After redirect: url={r.url[:80]}", flush=True)
            break
        elif r.status_code == 429:
            print(f"  ⏱️ RATE LIMITED. Waiting 120s...", flush=True)
            # Print body for debugging
            print(f"  Body: {r.text[:500]}", flush=True)
            time.sleep(120)
            # Re-login
            print("  Re-login...", flush=True)
            rl = session.get('https://pypi.org/account/login/', headers=bh(), timeout=30)
            c2 = extract_csrf(rl.text)
            rl = session.post('https://pypi.org/account/login/',
                data={'csrf_token': c2, 'username': USER, 'password': PASS},
                headers=bh(content_type='application/x-www-form-urlencoded'),
                allow_redirects=True, timeout=30)
            if 'two-factor' in rl.url:
                last_response = rl
                totp_url = rl.url
            break
        # 200 means page re-rendered (TOTP rejected or error page)
        errors = re.findall(r'(?i)(?:error|alert|invalid)[^>]*>([^<]+)', r.text)
        print(f"    200 body errors: {errors[:5]}", flush=True)
    else:
        # All codes failed for this TOTP page
        print(f"  All codes failed. Re-fetching TOTP page...", flush=True)
        rl = session.get(totp_url, headers=bh(referer='https://pypi.org/account/login/'), timeout=30)
        last_response = rl
        time.sleep(5)
        continue
    # Break outer loop on success
    break

# === Step 4: Navigate to token page ===
print("\n=== Step 4: Token page ===", flush=True)
# If we got here via redirect, we should be on dashboard. Go to token page.
if 'manage/account/token' not in r.url:
    r = session.get('https://pypi.org/manage/account/token/', headers=bh(), timeout=30)

print(f"Token page: {r.status_code}, url={r.url[:80]}", flush=True)
if 'login' in r.url.lower():
    print("SESSION NOT AUTHENTICATED!", flush=True)
    sys.exit(1)

# === Step 5: Create token ===
csrf = extract_csrf(r.text)
print(f"Create token CSRF: {'OK' if csrf else 'NONE'}", flush=True)
if not csrf:
    print(f"Token page HTML (first 1000):\n{r.text[:1000]}", flush=True)
    sys.exit(1)

r = session.post('https://pypi.org/manage/account/token/',
    data={'csrf_token': csrf, 'name': TOKEN_NAME},
    headers=bh(referer='https://pypi.org/manage/account/token/', content_type='application/x-www-form-urlencoded'),
    allow_redirects=False, timeout=30)
print(f"Create token POST: {r.status_code}", flush=True)

if r.status_code in (302, 303):
    loc = r.headers['location']
    r = session.get(loc if loc.startswith('http') else 'https://pypi.org'+loc,
        headers=bh(), timeout=30)

# Extract token from page
# pypi-xxxx-xxxx format or "Token:" prefix
tok = re.search(r'pypi-[\w-]+', r.text)
if tok:
    token_value = tok.group(0)
    print(f"\n{'='*60}", flush=True)
    print(f"✅ TOKEN: {token_value}", flush=True)
    print(f"{'='*60}", flush=True)
    with open('/tmp/pypi_token.txt', 'w') as f:
        f.write(token_value)
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"token={token_value}\n")
else:
    print(f"Token not found! Checking response...", flush=True)
    # Maybe we need to look for it differently
    print(f"Response body:\n{r.text[:2000]}", flush=True)

print("\n=== Done ===", flush=True)
