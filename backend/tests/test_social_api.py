"""Integration tests for social media API endpoints.

Covers:
  - Social account CRUD (connect, list, get, update, disconnect)
  - Content (posts) CRUD
  - Media library CRUD
  - Post schedules CRUD
  - Collected posts (list, get, review, re-analyse)
  - AI direct endpoints (/api/v1/ai/*)
"""
import pytest
from app.models import Permission, SocialAccount, SocialPost, MediaItem, CollectedPost, PostSchedule


def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


def _grant_all_social(db_session, role):
    resources = [
        ('social_account', 'create'), ('social_account', 'read'),
        ('social_account', 'update'), ('social_account', 'delete'),
        ('social_post', 'create'), ('social_post', 'read'),
        ('social_post', 'update'), ('social_post', 'delete'), ('social_post', 'publish'),
        ('media', 'create'), ('media', 'read'), ('media', 'update'), ('media', 'delete'),
        ('schedule', 'create'), ('schedule', 'read'), ('schedule', 'update'), ('schedule', 'delete'),
        ('collected_post', 'create'), ('collected_post', 'read'), ('collected_post', 'update'),
    ]
    for res, act in resources:
        _grant(db_session, role, res, act)


@pytest.fixture
def social_account(db_session, district):
    account = SocialAccount(
        district_id=district.id,
        platform='telegram',
        label='Test Telegram',
        platform_account_id='@test_channel',
        credentials={'bot_token': 'fake-token', 'chat_id': '@test_channel'},
        is_active=True,
        config={},
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture
def social_post(db_session, district, social_account, admin_user):
    post = SocialPost(
        district_id=district.id,
        account_id=social_account.id,
        author_id=admin_user.id,
        content='Test post content for district service.',
        platform='telegram',
        status='draft',
        meta={},
        ai_analysis={},
    )
    db_session.add(post)
    db_session.flush()
    return post


@pytest.fixture
def media_item(db_session, district, admin_user):
    item = MediaItem(
        district_id=district.id,
        filename='test.jpg',
        url='https://storage.example.com/test.jpg',
        media_type='image',
        uploaded_by=admin_user.id,
        folder='/',
        tags=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


@pytest.fixture
def collected_post(db_session, district, social_account):
    post = CollectedPost(
        district_id=district.id,
        account_id=social_account.id,
        platform='telegram',
        content_type='post',
        platform_content_id='unique-123',
        raw_text='Tanni varala. Complaint pannrom.',
        ai_status='pending',
        review_status='unreviewed',
    )
    db_session.add(post)
    db_session.flush()
    return post


# ===========================================================================
# Social Accounts
# ===========================================================================

class TestSocialAccounts:
    def test_requires_auth(self, client):
        resp = client.get('/api/v1/social/accounts')
        assert resp.status_code == 401

    def test_list_accounts(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_account', 'read')
        resp = client.get('/api/v1/social/accounts', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_connect_account(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'social_account', 'create')
        _grant(db_session, admin_role, 'social_account', 'read')
        resp = client.post('/api/v1/social/accounts', headers=auth_headers, json={
            'platform': 'telegram',
            'label': 'New Channel',
            'platform_account_id': '@new_channel_abc',
            'credentials': {'bot_token': 'tok', 'chat_id': '@new_channel_abc'},
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['platform'] == 'telegram'

    def test_connect_invalid_platform(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'social_account', 'create')
        resp = client.post('/api/v1/social/accounts', headers=auth_headers, json={
            'platform': 'tiktok',
            'label': 'TikTok',
            'platform_account_id': '@tok',
            'credentials': {},
        })
        assert resp.status_code == 400

    def test_connect_duplicate(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_account', 'create')
        resp = client.post('/api/v1/social/accounts', headers=auth_headers, json={
            'platform': social_account.platform,
            'label': 'Dup',
            'platform_account_id': social_account.platform_account_id,
            'credentials': {},
        })
        assert resp.status_code == 400

    def test_get_account(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_account', 'read')
        resp = client.get(f'/api/v1/social/accounts/{social_account.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == social_account.id

    def test_disconnect_account(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_account', 'delete')
        resp = client.delete(f'/api/v1/social/accounts/{social_account.id}', headers=auth_headers)
        assert resp.status_code == 200


# ===========================================================================
# Content (Posts)
# ===========================================================================

class TestContentPosts:
    def test_create_post(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_post', 'create')
        _grant(db_session, admin_role, 'social_post', 'read')
        resp = client.post('/api/v1/social/posts', headers=auth_headers, json={
            'account_id': social_account.id,
            'content': 'Hello world from district admin!',
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['status'] == 'draft'

    def test_create_post_missing_content(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'social_post', 'create')
        resp = client.post('/api/v1/social/posts', headers=auth_headers, json={
            'account_id': social_account.id,
            'content': '   ',
        })
        assert resp.status_code == 400

    def test_list_posts(self, client, auth_headers, admin_role, db_session, social_post):
        _grant(db_session, admin_role, 'social_post', 'read')
        resp = client.get('/api/v1/social/posts', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_get_post(self, client, auth_headers, admin_role, db_session, social_post):
        _grant(db_session, admin_role, 'social_post', 'read')
        resp = client.get(f'/api/v1/social/posts/{social_post.id}', headers=auth_headers)
        assert resp.status_code == 200

    def test_update_post(self, client, auth_headers, admin_role, db_session, social_post):
        _grant(db_session, admin_role, 'social_post', 'update')
        resp = client.patch(f'/api/v1/social/posts/{social_post.id}', headers=auth_headers, json={
            'content': 'Updated content here.',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['content'] == 'Updated content here.'

    def test_delete_post(self, client, auth_headers, admin_role, db_session, social_post):
        _grant(db_session, admin_role, 'social_post', 'delete')
        resp = client.delete(f'/api/v1/social/posts/{social_post.id}', headers=auth_headers)
        assert resp.status_code == 200


# ===========================================================================
# Media Library
# ===========================================================================

class TestMediaLibrary:
    def test_add_media(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'media', 'create')
        _grant(db_session, admin_role, 'media', 'read')
        resp = client.post('/api/v1/social/media', headers=auth_headers, json={
            'filename': 'photo.jpg',
            'url': 'https://cdn.example.com/photo.jpg',
            'media_type': 'image',
            'alt_text': 'District event photo',
        })
        assert resp.status_code == 201

    def test_list_media(self, client, auth_headers, admin_role, db_session, media_item):
        _grant(db_session, admin_role, 'media', 'read')
        resp = client.get('/api/v1/social/media', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_get_media_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'media', 'read')
        resp = client.get('/api/v1/social/media/nonexistent', headers=auth_headers)
        assert resp.status_code == 404

    def test_update_media_alt_text(self, client, auth_headers, admin_role, db_session, media_item):
        _grant(db_session, admin_role, 'media', 'update')
        resp = client.patch(f'/api/v1/social/media/{media_item.id}', headers=auth_headers, json={
            'alt_text': 'Updated alt text',
        })
        assert resp.status_code == 200

    def test_delete_media(self, client, auth_headers, admin_role, db_session, media_item):
        _grant(db_session, admin_role, 'media', 'delete')
        resp = client.delete(f'/api/v1/social/media/{media_item.id}', headers=auth_headers)
        assert resp.status_code == 200


# ===========================================================================
# Schedules
# ===========================================================================

class TestSchedules:
    def test_create_schedule(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'schedule', 'create')
        _grant(db_session, admin_role, 'schedule', 'read')
        resp = client.post('/api/v1/social/schedules', headers=auth_headers, json={
            'account_id': social_account.id,
            'name': 'Daily Update',
            'content_template': 'Good morning from {district}!',
            'next_run_at': '2026-07-01T09:00:00+00:00',
            'recurrence': 'daily',
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['recurrence'] == 'daily'

    def test_create_invalid_recurrence(self, client, auth_headers, admin_role, db_session, social_account):
        _grant(db_session, admin_role, 'schedule', 'create')
        resp = client.post('/api/v1/social/schedules', headers=auth_headers, json={
            'account_id': social_account.id,
            'name': 'Bad',
            'content_template': 'x',
            'next_run_at': '2026-07-01T09:00:00',
            'recurrence': 'hourly',  # invalid
        })
        assert resp.status_code == 400


# ===========================================================================
# Collected Posts
# ===========================================================================

class TestCollectedPosts:
    def test_list_collected(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'read')
        resp = client.get('/api/v1/social/collected', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_filter_by_platform(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'read')
        resp = client.get('/api/v1/social/collected?platform=telegram', headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()['data']:
            assert item['platform'] == 'telegram'

    def test_get_collected(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'read')
        resp = client.get(f'/api/v1/social/collected/{collected_post.id}', headers=auth_headers)
        assert resp.status_code == 200

    def test_update_review_status(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'update')
        resp = client.patch(
            f'/api/v1/social/collected/{collected_post.id}/review',
            headers=auth_headers,
            json={'review_status': 'reviewed'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['data']['review_status'] == 'reviewed'

    def test_invalid_review_status(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'update')
        resp = client.patch(
            f'/api/v1/social/collected/{collected_post.id}/review',
            headers=auth_headers,
            json={'review_status': 'bogus_status'},
        )
        assert resp.status_code == 400

    def test_reanalyze_post(self, client, auth_headers, admin_role, db_session, collected_post):
        _grant(db_session, admin_role, 'collected_post', 'update')
        resp = client.post(
            f'/api/v1/social/collected/{collected_post.id}/analyze',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['ai_status'] == 'processed'


# ===========================================================================
# AI direct endpoints
# ===========================================================================

class TestAIEndpoints:
    def test_analyze(self, client, auth_headers):
        resp = client.post('/api/v1/ai/analyze', headers=auth_headers, json={
            'text': 'The road has a big pothole. Very dangerous!',
            'district_name': 'Test District',
        })
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert 'sentiment' in body
        assert 'complaint' in body
        assert 'emergency' in body

    def test_analyze_missing_text(self, client, auth_headers):
        resp = client.post('/api/v1/ai/analyze', headers=auth_headers, json={})
        assert resp.status_code == 400

    def test_sentiment(self, client, auth_headers):
        resp = client.post('/api/v1/ai/sentiment', headers=auth_headers, json={
            'text': 'Excellent service. Thank you!',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['label'] == 'positive'

    def test_detect_complaint(self, client, auth_headers):
        resp = client.post('/api/v1/ai/detect/complaint', headers=auth_headers, json={
            'text': 'There is garbage all over the street. Big problem.',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['is_complaint'] is True

    def test_detect_emergency(self, client, auth_headers):
        resp = client.post('/api/v1/ai/detect/emergency', headers=auth_headers, json={
            'text': 'Fire in the building! Send ambulance now!',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['is_emergency'] is True

    def test_detect_spam(self, client, auth_headers):
        resp = client.post('/api/v1/ai/detect/spam', headers=auth_headers, json={
            'text': 'Click here to win a lottery prize! Limited time offer!',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['is_spam'] is True

    def test_detect_trends(self, client, auth_headers):
        resp = client.post('/api/v1/ai/detect/trends', headers=auth_headers, json={
            'text': 'water pipeline broken and road pothole near hospital',
        })
        assert resp.status_code == 200
        tags = resp.get_json()['data']['tags']
        assert 'water' in tags or 'roads' in tags

    def test_reply_suggestion(self, client, auth_headers):
        resp = client.post('/api/v1/ai/reply', headers=auth_headers, json={
            'text': 'The sewage is overflowing. Please fix it!',
            'is_complaint': True,
            'district_name': 'Test District',
            'ref_id': 'COMP-001',
        })
        assert resp.status_code == 200
        assert len(resp.get_json()['data']['suggested_reply']) > 10

    def test_language_detection(self, client, auth_headers):
        resp = client.post('/api/v1/ai/language', headers=auth_headers, json={
            'text': 'Vanakkam! Romba naala tanni varala.',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['language'] == 'tanglish'

    def test_unauthorized(self, client):
        resp = client.post('/api/v1/ai/analyze', json={'text': 'test'})
        assert resp.status_code == 401
