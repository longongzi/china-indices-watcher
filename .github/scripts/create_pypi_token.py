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

s = requests.Session()

# 1. Login
print("=== Login ===", flush=True)
r = s.get('https://pypi.org/account/login/', timeout=30, headers=bh())
csrf = extract_csrf(r.text)
print(f"GET login: {r.status_code}, CSRF: {csrf[:20] if csrf else 'NONE'}", flush=True)

r = s.post('https://pypi.org/account/login/', 
    data={'csrf_token': csrf, 'username': USER, 'password': PASS},
    headers=bh(referer='https://pypi.org/account/login/'), timeout=30)
print(f"POST login: {r.status_code}, URL: {r.url}", flush=True)

# CRITICAL: Complete TOTP IMMEDIATELY after login, before doing anything else
totp_retries = 3
if 'two-factor' in r.url:
    for attempt in range(totp_retries):
        print(f"\n=== TOTP (attempt {attempt+1}) ===", flush=True)
        csrf = extract_csrf(r.text)
        code = pyotp.TOTP(SECRET).now()
        print(f"Code: {code}, CSRF: {csrf[:20] if csrf else 'NONE'}", flush=True)
        
        r = s.post(r.url, data={'csrf_token': csrf or '', 'totp_value': code, 'method': 'totp'},
            headers=bh(referer=r.url, origin='https://pypi.org'), 
            allow_redirects=False, timeout=30)
        print(f"TOTP POST: {r.status_code}, Location: {r.headers.get('location','none')}", flush=True)
        
        if r.status_code in (302, 303):
            loc = r.headers['location']
            loc_url = loc if loc.startswith('http') else 'https://pypi.org' + loc
            print(f"TOTP redirect to: {loc_url}", flush=True)
            r = s.get(loc_url, headers=bh(referer=r.url), timeout=30)
            print(f"After TOTP: {r.status_code}, URL: {r.url}", flush=True)
            
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
                    print(f"After password: {r.status_code}, URL: {r.url}", flush=True)
            break
        else:
            print(f"TOTP failed: {r.status_code}, body: {r.text[:800]}", flush=True)
            if attempt < totp_retries - 1:
                time.sleep(1)
    else:
        print("TOTP failed after all retries", flush=True)
        sys.exit(1)

# 2. Now go to token page (session should be fully authenticated)
print("\n=== Token page ===", flush=True)
r = s.get('https://pypi.org/manage/account/token/', timeout=30, headers=bh(referer='https://pypi.org/'))
print(f"GET token: {r.status_code}, URL: {r.url}", flush=True)

# If redirected back to login, something went wrong with TOTP
if 'login' in r.url.lower():
    print(f"ERROR: Redirected to login after TOTP. Session not authenticated.", flush=True)
    print(f"HTML: {r.text[:1000]}", flush=True)
    sys.exit(1)

# 4. Create token
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
        # Also set step output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"token={tok.group(0)}\n")
    elif r.is_redirect:
        loc = r.headers['location']
        loc_url = loc if loc.startswith('http') else 'https://pypi.org' + loc
        r2 = s.get(loc_url, headers=bh(referer='https://pypi.org/manage/account/token/'), timeout=30)
        print(f"Redirect: {r2.url}", flush=True)
        
        # Look for token in alert boxes
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
    print(f"Cannot create. HTML ({len(r.text)}): {r.text[:1000]}", flush=True)

print(f"\n=== Done ===", flush=True)
r = s.get('https://pypi.org/manage/account/token/', timeout=30, headers=bh())
if TOKEN_NAME in r.text:
    print(f"✅ Token '{TOKEN_NAME}' verified!", flush=True)
elif 'pypi_token.txt' in os.popen('ls -la /tmp/pypi_token.txt 2>/dev/null').read():
    print("Token file exists but couldn't verify page content", flush=True)
