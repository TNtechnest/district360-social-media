"""Phase 2 endpoint probe — verify comment API is live."""
import urllib.request
import json
import sys

BASE        = 'http://127.0.0.1:5000'
DISTRICT_ID = '1363d5e9-1afa-4140-943e-a45baf380d3c'

RESULTS = []


def req(method, path, body=None, token=None):
    url  = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    h    = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = 'Bearer ' + token
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=6) as resp:
            raw = resp.read()
            ct  = resp.headers.get('Content-Type', '')
            if 'json' in ct:
                return resp.status, json.loads(raw)
            return resp.status, {'_binary': True, '_bytes': len(raw)}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def probe(label, method, path, body=None, token=None, expect=None):
    ok_codes = expect if expect else {200, 201, 204}
    code, payload = req(method, path, body, token)
    status = 'PASS' if code in ok_codes else 'FAIL'
    RESULTS.append((status, code, method, path))
    icon  = '✓' if status == 'PASS' else '✗'
    extra = ''
    if status == 'FAIL':
        msg = payload.get('error', {}).get('message', '') if isinstance(payload, dict) else ''
        extra = f'  <- {msg[:60]}' if msg else ''
    print(f'  {icon}  [{code}]  {method:<6} {path}{extra}')
    return code, payload


# Login
code, resp = req('POST', '/api/v1/auth/login', {
    'district_id': DISTRICT_ID,
    'email': 'probe@district360.test',
    'password': 'ProbePass1',
})
if code != 200:
    print(f'[FATAL] Login failed: {code}')
    sys.exit(1)
TOKEN = resp['data']['access_token']
print(f'✓  Login OK\n')

# Seed permissions
from app import create_app
from app.services.rbac_service import seed_system_roles_and_permissions
app = create_app('development')
with app.app_context():
    seed_system_roles_and_permissions()

# Re-login to get fresh token with new permissions
code, resp = req('POST', '/api/v1/auth/login', {
    'district_id': DISTRICT_ID,
    'email': 'probe@district360.test',
    'password': 'ProbePass1',
})
TOKEN = resp['data']['access_token']

# --- Need a published post with a platform_post_id to test comment endpoints ---
# First get or create an account
code, resp = req('GET', '/api/v1/social/accounts', token=TOKEN)
accounts = resp.get('data', [])
if accounts:
    ACCOUNT_ID = accounts[0]['id']
    PLATFORM   = accounts[0]['platform']
else:
    code, resp = req('POST', '/api/v1/social/accounts', {
        'platform': 'facebook',
        'label': 'Probe Page',
        'platform_account_id': 'probe_page_002',
        'credentials': {'page_access_token': 'fake', 'page_id': 'probe_page_002'},
    }, token=TOKEN)
    ACCOUNT_ID = resp['data']['id']
    PLATFORM   = 'facebook'

# Create a published post (or use existing)
code, resp = req('GET', '/api/v1/social/posts?status=published', token=TOKEN)
posts = resp.get('data', [])
POST_ID = None
for p in posts:
    if p.get('platform_post_id'):
        POST_ID = p['id']
        break

if not POST_ID:
    code, resp = req('POST', '/api/v1/social/posts', {
        'account_id': ACCOUNT_ID,
        'content': 'Probe post for comment testing.',
    }, token=TOKEN)
    raw_post_id = resp['data']['id']
    # Manually mark as published with a fake platform_post_id
    from app.extensions import db
    from app.models.social_post import SocialPost
    with app.app_context():
        p = SocialPost.query.get(raw_post_id)
        if p:
            p.status = 'published'
            p.platform_post_id = 'probe_fb_post_001'
            db.session.commit()
    POST_ID = raw_post_id

print(f'Using POST_ID: {POST_ID}')
print(f'Using ACCOUNT_ID: {ACCOUNT_ID}\n')

# ── Comment endpoints ─────────────────────────────────────────────────────────

print('━━━  COMMENT ENDPOINTS')

probe('list all (no auth)',    'GET',  '/api/v1/social/comments', expect={401})

probe('list all comments',     'GET',  '/api/v1/social/comments',               token=TOKEN)
probe('list post comments',    'GET',  f'/api/v1/social/posts/{POST_ID}/comments', token=TOKEN)

c, r = probe('ingest comment', 'POST', f'/api/v1/social/posts/{POST_ID}/comments', {
    'platform': PLATFORM,
    'platform_comment_id': f'live_probe_comment_{POST_ID[:8]}',
    'text': 'Road near junction has a big pothole. Complaint pannrom!',
    'author_name': 'Live Probe Citizen',
    'likes': 3,
}, token=TOKEN, expect={200, 201})

COMMENT_ID = r.get('data', {}).get('id') if c in {200, 201} else None
print(f'  Comment ID: {COMMENT_ID}')

if COMMENT_ID:
    probe('get comment',        'GET',  f'/api/v1/social/comments/{COMMENT_ID}',            token=TOKEN)
    probe('get replies',        'GET',  f'/api/v1/social/comments/{COMMENT_ID}/replies',     token=TOKEN)
    probe('analyse comment',    'POST', f'/api/v1/social/comments/{COMMENT_ID}/analyse',    token=TOKEN)
    probe('moderate hidden',    'POST', f'/api/v1/social/comments/{COMMENT_ID}/moderate',
          {'moderation_status': 'hidden', 'reason': 'Probe test'}, token=TOKEN)
    probe('moderate visible',   'POST', f'/api/v1/social/comments/{COMMENT_ID}/moderate',
          {'moderation_status': 'visible'}, token=TOKEN)

probe('bulk analyse',          'POST', '/api/v1/social/comments/analyse',
      {'batch_size': 5}, token=TOKEN)

probe('get comment not found', 'GET',  '/api/v1/social/comments/nonexistent',   token=TOKEN, expect={404})
probe('ingest invalid platform','POST',f'/api/v1/social/posts/{POST_ID}/comments',
      {'platform': 'youtube', 'platform_comment_id': 'yt001', 'text': 'hi'},
      token=TOKEN, expect={400})
probe('ingest blank text',     'POST', f'/api/v1/social/posts/{POST_ID}/comments',
      {'platform': PLATFORM, 'platform_comment_id': 'blank001', 'text': '   '},
      token=TOKEN, expect={400})
probe('reply no permission',   'POST',
      f'/api/v1/social/comments/{COMMENT_ID or "none"}/reply',
      {'reply_text': 'We will fix it.'}, expect={401})

print('\n' + '━' * 60)
total  = len(RESULTS)
passed = sum(1 for r in RESULTS if r[0] == 'PASS')
failed = sum(1 for r in RESULTS if r[0] == 'FAIL')
print(f'  PHASE 2 COMMENT PROBE: {total} tests  ✓ {passed} passed  ✗ {failed} failed')
print('━' * 60)

if failed:
    print('\nFAILED:')
    for r in RESULTS:
        if r[0] == 'FAIL':
            print(f'  [{r[1]}] {r[2]} {r[3]}')
