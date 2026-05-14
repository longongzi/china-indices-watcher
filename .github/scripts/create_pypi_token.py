"""Create PyPI API token via HTTP with full browser headers, from GitHub runner."""
import requests, re, os, time, sys
import pyotp

USER = os.environ["PYPI_USER"]
PASS = os.environ["PYPI_PASS"]
SECRET = os.environ["PYPI_TOTP_SECRET"]
TOKEN_NAME = "gh-actions-publisher"

def bh(referer=None, origin=None, ct=None):
    h = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'DNT': '1',
    }
    if referer: h['Referer'] = referer
    if origin: h['Origin'] = origin
    if ct: h['Content-Type'] = ct
    return h

def extract_csrf(html):
    for p in [r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', r'name="csrf_token".*?value="([^"]+)"']:
        m = re.search(p, html)
        if m: return m.group(1)
    return None

def do_login(s):
    """Login and return (session, TOTP page URL). Handles rate limits."""
    print("=== Login ===", flush=True)
    r = s.get('https://pypi.org/account/login/', timeout=30, headers=bh())
    csrf = extract_csrf(r.text)
    print(f"GET login: {r.status_code}, CSRF: {csrf[:20] if csrf else 'NONE'}", flush=True)

    r = s.post('https://pypi.org/account/login/', 
        data={'csrf_token': csrf, 'username': USER, 'password': PASS},
        headers=bh(referer='https://pypi.org/account/login/'), timeout=30)
    print(f"POST login: {r.status_code}, URL: {r.url[:80]}", flush=True)
    
    # Handle rate limit
    if r.status_code == 429:
        print("Rate limited! Waiting 90 seconds...", flush=True)
        time.sleep(90)
        return do_login(s)
    
    if 'two-factor' not in r.url:
        print(f"ERROR: Expected two-factor page, got: {r.url}", flush=True)
        print(f"Body: {r.text[:500]}", flush=True)
        return False
    
    return r  # Success - TOTP page

def do_totp(s, totp_page_resp):
    """Submit TOTP code. Returns (success_bool, response_after_totp_or_None)."""
    for attempt in range(3):
        print(f"\n=== TOTP (attempt {attempt+1}) ===", flush=True)
        csrf = extract_csrf(totp_page_resp.text)
        if not csrf:
            print(f"No CSRF found! Page title: {re.search(r'<title>([^<]+)', totp_page_resp.text)}", flush=True)
            return False, None
        code = pyotp.TOTP(SECRET).now()
        print(f"Code: {code}, CSRF: {csrf[:20]}", flush=True)
        
        r = s.post(totp_page_resp.url, 
            data={'csrf_token': csrf, 'totp_value': code, 'method': 'totp'},
            headers=bh(referer=totp_page_resp.url, origin='https://pypi.org'), 
            allow_redirects=False, timeout=30)
        print(f"TOTP POST: {r.status_code}, Location: {r.headers.get('location','none')}", flush=True)
        
        if r.status_code in (302, 303):
            loc = r.headers['location']
            loc_url = loc if loc.startswith('http') else 'https://pypi.org' + loc
            print(f"Redirect to: {loc_url[:80]}", flush=True)
            r = s.get(loc_url, headers=bh(referer=totp_page_resp.url), timeout=30)
            print(f"After TOTP: {r.status_code}, URL: {r.url[:80]}", flush=True)
            
            # Handle password confirmation (PyPI may ask for password again after 2FA)
            if 'password' in r.url.lower() and 'confirm' in r.url.lower():
                print("\n=== Password confirmation ===", flush=True)
                csrf = extract_csrf(r.text)
                r = s.post(r.url, data={'csrf_token': csrf, 'password': PASS},
                    headers=bh(referer=r.url, origin='https://pypi.org'),
                    allow_redirects=False, timeout=30)
                if r.status_code in (302, 303):
                    loc = r.headers['location']
                    r = s.get(loc if loc.startswith('http') else 'https://pypi.org' + loc, 
                        headers=bh(referer=r.url), timeout=30)
                    print(f"After password: {r.status_code}, URL: {r.url[:80]}", flush=True)
            return True, r
        
        # Handle 429: wait and re-login
        if r.status_code == 429:
            print("Rate limited on TOTP! Waiting 90 seconds, then re-login...", flush=True)
            time.sleep(90)
            totp_page_resp = do_login(s)
            if not totp_page_resp:
                return False, None
            continue  # Retry with fresh session
        
        # Other failures: try re-login and retry once
        if attempt < 2:
            print("TOTP failed, re-login and retry...", flush=True)
            time.sleep(2)
            totp_page_resp = do_login(s)
            if not totp_page_resp:
                return False, None
    
    print("TOTP failed after all retries", flush=True)
    return False, None

# === Main ===
s = requests.Session()

# 1. Login + TOTP
totp_page = do_login(s)
if not totp_page:
    sys.exit(1)

success, resp = do_totp(s, totp_page)
if not success:
    sys.exit(1)

# 2. Go to token page
print("\n=== Token page ===", flush=True)
r = s.get('https://pypi.org/manage/account/token/', timeout=30, headers=bh(referer='https://pypi.org/'))
print(f"GET token: {r.status_code}, URL: {r.url[:80]}", flush=True)

if 'login' in r.url.lower():
    print(f"ERROR: Redirected to login. Session not authenticated.", flush=True)
    print(f"HTML: {r.text[:1000]}", flush=True)
    sys.exit(1)

# 3. Create token
print(f"\n=== Create token '{TOKEN_NAME}' ===", flush=True)
csrf = extract_csrf(r.text)
inputs = re.findall(r'<input[^>]*name="([^"]*)"', r.text, re.IGNORECASE)
print(f"Inputs: {inputs}", flush=True)
print(f"CSRF: {csrf[:30] if csrf else 'NONE'}", flush=True)

if csrf and 'name' in inputs:
    post_data = 'csrf_token=' + requests.utils.quote(csrf) + '&name=' + requests.utils.quote(TOKEN_NAME)
    h = bh(referer='https://pypi.org/manage/account/token/', origin='https://pypi.org')
    h['Content-Type'] = 'application/x-www-form-urlencoded'
    
    r = s.post('https://pypi.org/manage/account/token/', data=post_data, headers=h, 
               allow_redirects=False, timeout=30)
    print(f"Create: {r.status_code}, Location: {r.headers.get('location','none')}", flush=True)
    
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
    elif r.is_redirect:
        loc = r.headers['location']
        loc_url = loc if loc.startswith('http') else 'https://pypi.org' + loc
        r2 = s.get(loc_url, headers=bh(referer='https://pypi.org/manage/account/token/'), timeout=30)
        print(f"Redirect to: {r2.url[:80]}", flush=True)
        
        alerts = re.findall(r'class="[^"]*alert-success[^"]*"[^>]*>([^<]+)', r2.text)
        print(f"Alerts: {alerts}", flush=True)
        
        for p in [r'pypi-[\w-]+', r'[A-Za-z0-9_-]{40,}']:
            m = re.search(p, r2.text)
            if m:
                print(f"\n✅ TOKEN: {m.group(0)}", flush=True)
                with open('/tmp/pypi_token.txt', 'w') as f:
                    f.write(m.group(0))
                break
else:
    print(f"Cannot create. Page ({len(r.text)} chars): {r.text[:1000]}", flush=True)

# 4. Verify
print(f"\n=== Verify ===", flush=True)
r = s.get('https://pypi.org/manage/account/token/', timeout=30, headers=bh())
print(f"Verify: {r.status_code}, URL: {r.url[:80]}", flush=True)
if TOKEN_NAME in r.text:
    print(f"✅ Token '{TOKEN_NAME}' verified on page!", flush=True)
elif os.path.exists('/tmp/pypi_token.txt'):
    print("Token file exists.", flush=True)
else:
    print("Token not found.", flush=True)

print(f"\n=== Done ===", flush=True)
