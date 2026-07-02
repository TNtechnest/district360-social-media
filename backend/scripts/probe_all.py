"""Full endpoint probe — run from backend/ with PYTHONPATH set."""
import urllib.request
import json
import sys

BASE         = 'http://127.0.0.1:5000'
DISTRICT_ID  = '9dc98a66-f2bc-4f0f-a839-87802fec96dc'
EMAIL        = 'probe@district360.test'
PASSWORD     = 'ProbePass1'

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
            # Binary response (PDF, Excel) — return status only
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
        extra = f'  <- {msg[:70]}' if msg else ''
    print(f'  {icon}  [{code}]  {method:<6} {path}{extra}')
    return code, payload


# ── Login ────────────────────────────────────────────────────────────────────
code, resp = req('POST', '/api/v1/auth/login', {
    'district_id': DISTRICT_ID, 'email': EMAIL, 'password': PASSWORD,
})
if code != 200:
    print(f'[FATAL] Login failed ({code}): {resp}')
    sys.exit(1)

TOKEN = resp['data']['access_token']
print(f'✓  Login OK — token acquired\n')

# ── Public ───────────────────────────────────────────────────────────────────
print('━━━  PUBLIC ENDPOINTS')
probe('health',       'GET', '/health',                        expect={200, 503})
probe('ping',         'GET', '/api/v1/ping',                   expect={200})
probe('mon-health',   'GET', '/api/v1/monitoring/health',      expect={200, 207, 503})

# ── Auth ─────────────────────────────────────────────────────────────────────
print('\n━━━  AUTHENTICATION')
probe('/me',           'GET',  '/api/v1/users/me',             token=TOKEN)
probe('refresh',       'POST', '/api/v1/auth/refresh',         expect={401, 422})   # access token on refresh route

# ── Core management ──────────────────────────────────────────────────────────
print('\n━━━  CORE MANAGEMENT')
probe('users-list',   'GET', '/api/v1/users',                  token=TOKEN)
probe('districts',    'GET', '/api/v1/districts',              token=TOKEN)
probe('departments',  'GET', '/api/v1/departments',            token=TOKEN)

# ── Social media ─────────────────────────────────────────────────────────────
print('\n━━━  SOCIAL MEDIA')
probe('accounts',     'GET', '/api/v1/social/accounts',        token=TOKEN)
probe('posts',        'GET', '/api/v1/social/posts',           token=TOKEN)
probe('media',        'GET', '/api/v1/social/media',           token=TOKEN)
probe('schedules',    'GET', '/api/v1/social/schedules',       token=TOKEN)
probe('collected',    'GET', '/api/v1/social/collected',       token=TOKEN)

# ── Analytics ────────────────────────────────────────────────────────────────
print('\n━━━  ANALYTICS')
probe('reach',        'GET', '/api/v1/analytics/reach',                   token=TOKEN)
probe('reach/trend',  'GET', '/api/v1/analytics/reach/trend',             token=TOKEN)
probe('engagement',   'GET', '/api/v1/analytics/engagement',              token=TOKEN)
probe('eng/platform', 'GET', '/api/v1/analytics/engagement/platform',     token=TOKEN)
probe('growth',       'GET', '/api/v1/analytics/growth',                  token=TOKEN)
probe('campaigns',    'GET', '/api/v1/analytics/campaigns',               token=TOKEN)
probe('camp/trend',   'GET', '/api/v1/analytics/campaigns/water/trend',   token=TOKEN)

# ── Reports ───────────────────────────────────────────────────────────────────
print('\n━━━  REPORTS')
probe('list',         'GET',  '/api/v1/reports',               token=TOKEN)
c, r = probe('daily',  'POST', '/api/v1/reports',
             {'report_type': 'daily'}, token=TOKEN, expect={200, 201})
if c in {200, 201}:
    rid = r.get('data', {}).get('id', '')
    if rid:
        probe('get-report',     'GET', f'/api/v1/reports/{rid}',              token=TOKEN)
        probe('pdf',            'GET', f'/api/v1/reports/{rid}/export/pdf',   token=TOKEN)
        probe('excel',          'GET', f'/api/v1/reports/{rid}/export/excel', token=TOKEN)
probe('weekly',       'POST', '/api/v1/reports', {'report_type': 'weekly'},   token=TOKEN, expect={200, 201})
probe('monthly',      'POST', '/api/v1/reports', {'report_type': 'monthly'},  token=TOKEN, expect={200, 201})
probe('executive',    'POST', '/api/v1/reports',
      {'report_type': 'executive', 'period_start': '2026-06-01', 'period_end': '2026-06-30'},
      token=TOKEN, expect={200, 201})

# ── Workflow / Approval / SLA ────────────────────────────────────────────────
print('\n━━━  WORKFLOW / APPROVAL / SLA')
probe('approvals',    'GET',  '/api/v1/workflow/approvals',    token=TOKEN)
probe('rules',        'GET',  '/api/v1/workflow/rules',        token=TOKEN)
probe('escalations',  'GET',  '/api/v1/workflow/escalations',  token=TOKEN)
probe('sla-summary',  'GET',  '/api/v1/workflow/sla/summary',  token=TOKEN)
probe('create-rule',  'POST', '/api/v1/workflow/rules',
      {'resource_type': 'social_post', 'name': 'Probe Rule',
       'rule_type': 'approval', 'conditions': {}, 'actions': [], 'sla_minutes': 60},
      token=TOKEN, expect={200, 201})
c, r = probe('create-approval', 'POST', '/api/v1/workflow/approvals',
             {'resource_type': 'social_post', 'resource_id': 'probe-resource-001'},
             token=TOKEN, expect={200, 201})
if c in {200, 201}:
    app_id = r.get('data', {}).get('id', '')
    if app_id:
        probe('review-approval', 'POST', f'/api/v1/workflow/approvals/{app_id}/review',
              {'decision': 'approved', 'comment': 'Probe test approval'},
              token=TOKEN)
probe('run-escalation', 'POST', '/api/v1/workflow/escalations/check', token=TOKEN)

# ── Notifications ────────────────────────────────────────────────────────────
print('\n━━━  NOTIFICATIONS')
probe('notif-list',   'GET',  '/api/v1/notifications',            token=TOKEN)
probe('templates',    'GET',  '/api/v1/notifications/templates',  token=TOKEN)
probe('create-tmpl',  'POST', '/api/v1/notifications/templates',
      {'event_key': 'probe.test', 'channel': 'email',
       'subject': 'Hello {{name}}', 'body': 'Your ref is {{ref}}'},
      token=TOKEN, expect={200, 201})
probe('send-email',   'POST', '/api/v1/notifications/send',
      {'channel': 'email', 'recipient': 'test@example.com',
       'event_key': 'probe.test', 'variables': {'name': 'World', 'ref': 'R1'}},
      token=TOKEN, expect={200, 201})
probe('send-sms',     'POST', '/api/v1/notifications/send',
      {'channel': 'sms', 'recipient': '+919876543210',
       'event_key': 'probe.test', 'body': 'SMS test message'},
      token=TOKEN, expect={200, 201})
probe('send-push',    'POST', '/api/v1/notifications/send',
      {'channel': 'push', 'recipient': 'device-token-xyz',
       'event_key': 'probe.test', 'body': 'Push test message'},
      token=TOKEN, expect={200, 201})
probe('send-wa',      'POST', '/api/v1/notifications/send',
      {'channel': 'whatsapp', 'recipient': '+919876543210',
       'event_key': 'probe.test', 'body': 'WA test message'},
      token=TOKEN, expect={200, 201})

# ── Monitoring ────────────────────────────────────────────────────────────────
print('\n━━━  MONITORING')
probe('mon-health',   'GET', '/api/v1/monitoring/health',   expect={200, 207, 503})
probe('mon-audit',    'GET', '/api/v1/monitoring/audit',    token=TOKEN)
probe('mon-activity', 'GET', '/api/v1/monitoring/activity', token=TOKEN)
probe('mon-errors',   'GET', '/api/v1/monitoring/errors',   token=TOKEN)

# ── Service Requests ─────────────────────────────────────────────────────────
print('\n━━━  SERVICE REQUESTS')
probe('sr-cats',      'GET',  '/api/v1/service-requests/categories', token=TOKEN)
probe('sr-list',      'GET',  '/api/v1/service-requests',            token=TOKEN)

# ── Uploads ──────────────────────────────────────────────────────────────────
print('\n━━━  UPLOADS')
probe('uploads',      'GET',  '/api/v1/uploads',            token=TOKEN)

# ── Payments ─────────────────────────────────────────────────────────────────
print('\n━━━  PAYMENTS')
probe('plans',        'GET',  '/api/v1/payments/plans',        token=TOKEN)
probe('transactions', 'GET',  '/api/v1/payments/transactions', token=TOKEN)

# ── AI Engine ────────────────────────────────────────────────────────────────
print('\n━━━  AI ENGINE')
probe('language',   'POST', '/api/v1/ai/language',
      {'text': 'Vanakkam! Tanni varala. Romba naala complaint pannrom.'}, token=TOKEN)
probe('analyze',    'POST', '/api/v1/ai/analyze',
      {'text': 'The road near junction has a big pothole. Very dangerous!',
       'district_name': 'Probe District', 'ref_id': 'REF-001'}, token=TOKEN)
probe('sentiment',  'POST', '/api/v1/ai/sentiment',
      {'text': 'Excellent service, thank you very much!'}, token=TOKEN)
probe('complaint',  'POST', '/api/v1/ai/detect/complaint',
      {'text': 'garbage not collected, big problem, please fix it complaint!'}, token=TOKEN)
probe('emergency',  'POST', '/api/v1/ai/detect/emergency',
      {'text': 'Fire in building! Send ambulance now urgently!'}, token=TOKEN)
probe('spam',       'POST', '/api/v1/ai/detect/spam',
      {'text': 'Click here win lottery prize free offer limited time!'}, token=TOKEN)
probe('trends',     'POST', '/api/v1/ai/detect/trends',
      {'text': 'water pipeline broken road pothole hospital electricity issue'}, token=TOKEN)
probe('reply',      'POST', '/api/v1/ai/reply',
      {'text': 'tanni varala complaint pannrom', 'is_complaint': True,
       'district_name': 'Probe District', 'ref_id': 'COMP-001'}, token=TOKEN)

# ── Audit Logs ────────────────────────────────────────────────────────────────
print('\n━━━  AUDIT LOGS')
probe('audit-logs',    'GET', '/api/v1/audit/logs',     token=TOKEN)
probe('audit-activity','GET', '/api/v1/audit/activity', token=TOKEN)

# ── Security: unauthenticated should fail ─────────────────────────────────────
print('\n━━━  SECURITY (unauthenticated must be 401)')
probe('no-token-users',    'GET', '/api/v1/users',            expect={401})
probe('no-token-analytics','GET', '/api/v1/analytics/reach',  expect={401})
probe('no-token-reports',  'GET', '/api/v1/reports',          expect={401})
probe('no-token-ai',       'POST','/api/v1/ai/analyze', {},   expect={401})

# ── Summary ───────────────────────────────────────────────────────────────────
total  = len(RESULTS)
passed = sum(1 for r in RESULTS if r[0] == 'PASS')
failed = sum(1 for r in RESULTS if r[0] == 'FAIL')

print('\n' + '━' * 60)
print(f'  TOTAL: {total}   ✓ PASS: {passed}   ✗ FAIL: {failed}')
print('━' * 60)

if failed:
    print('\n  FAILED ENDPOINTS:')
    for r in RESULTS:
        if r[0] == 'FAIL':
            print(f'    [{r[1]}]  {r[2]}  {r[3]}')
else:
    print('\n  ALL ENDPOINTS PASSED ✓')
