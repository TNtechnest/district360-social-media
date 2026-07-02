"""Phase 2 tests — SocialComment and CommentAnalysis.

Covers: models, schemas, service layer, and API endpoints.
"""
import pytest
from app.models import (
    SocialAccount, SocialPost, SocialComment, CommentAnalysis, Permission,
    ServiceRequest, Department,
)
from app.schemas.social_comment_schema import (
    CreateCommentSchema, ReplyCommentSchema, ModerateCommentSchema,
    SocialCommentSchema, CommentAnalysisSchema,
)
from app.services.social.comment_service import (
    upsert_comment, get_comments, get_comment,
    moderate_comment, bulk_analyse, analyse_comment,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


@pytest.fixture
def social_account(db_session, district):
    a = SocialAccount(
        district_id=district.id, platform='facebook',
        label='Test Page', platform_account_id='page_123',
        credentials={'page_access_token': 'tok', 'page_id': 'page_123'},
        is_active=True, config={},
    )
    db_session.add(a)
    db_session.flush()
    return a


@pytest.fixture
def social_post(db_session, district, social_account, admin_user):
    p = SocialPost(
        district_id=district.id, account_id=social_account.id,
        author_id=admin_user.id, status='published',
        content='Test published post.', platform='facebook',
        platform_post_id='fb_post_001', meta={}, ai_analysis={},
        social_comment_count=0,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def social_comment(db_session, district, social_post):
    c = SocialComment(
        district_id=district.id, post_id=social_post.id,
        platform='facebook', platform_comment_id='comment_001',
        text='This road is terrible! Big pothole near junction.',
        author_name='Test Citizen', author_username='citizen_01',
        likes=3, reply_count=0, moderation_status='visible',
        is_replied=False, ai_status='pending', language='unknown',
    )
    db_session.add(c)
    db_session.flush()
    return c


# ── Model tests ───────────────────────────────────────────────────────────────

class TestSocialCommentModel:
    def test_to_dict_keys(self, social_comment):
        d = social_comment.to_dict()
        required = [
            'id', 'district_id', 'post_id', 'platform', 'platform_comment_id',
            'text', 'likes', 'moderation_status', 'is_replied',
            'sentiment', 'is_complaint', 'is_emergency', 'is_spam', 'ai_status',
        ]
        for k in required:
            assert k in d, f'Missing key: {k}'

    def test_to_dict_defaults(self, social_comment):
        d = social_comment.to_dict()
        assert d['is_replied'] is False
        assert d['moderation_status'] == 'visible'
        assert d['ai_status'] == 'pending'

    def test_relationship_to_post(self, db_session, social_comment, social_post):
        assert social_comment.post_id == social_post.id

    def test_parent_comment_null_by_default(self, social_comment):
        assert social_comment.parent_comment_id is None

    def test_reply_threading(self, db_session, district, social_comment):
        reply = SocialComment(
            district_id=district.id,
            post_id=social_comment.post_id,
            parent_comment_id=social_comment.id,
            platform='facebook',
            platform_comment_id='reply_001',
            text='We will fix it soon!',
            moderation_status='visible', is_replied=False,
            ai_status='pending', language='en',
        )
        db_session.add(reply)
        db_session.flush()
        assert reply.parent_comment_id == social_comment.id


class TestCommentAnalysisModel:
    def test_create_analysis(self, db_session, district, social_comment):
        a = CommentAnalysis(
            district_id=district.id, comment_id=social_comment.id,
            language='en', sentiment_label='negative', sentiment_score=-0.6,
            is_complaint=True, complaint_confidence=0.75,
            is_emergency=False, emergency_confidence=0.0,
            is_spam=False, spam_confidence=0.0,
            trend_tags=['roads'], top_topic='roads',
            suggested_reply='We will fix it.', reply_category='complaint',
            status='processed', raw_result={}, processing_ms=120,
        )
        db_session.add(a)
        db_session.flush()
        assert a.id is not None

    def test_to_dict_structure(self, db_session, district, social_comment):
        a = CommentAnalysis(
            district_id=district.id, comment_id=social_comment.id,
            language='en', sentiment_label='negative', sentiment_score=-0.5,
            is_complaint=True, complaint_confidence=0.8,
            is_emergency=False, emergency_confidence=0.0,
            is_spam=False, spam_confidence=0.0,
            trend_tags=['water'], top_topic='water',
            suggested_reply='Thank you.', reply_category='complaint',
            status='processed', raw_result={}, processing_ms=80,
        )
        db_session.add(a)
        db_session.flush()
        d = a.to_dict()
        assert 'sentiment' in d
        assert 'complaint' in d
        assert 'emergency' in d
        assert 'spam' in d
        assert d['category'] == 'neutral'
        assert d['keywords'] == []
        assert d['summary'] is None
        assert 'trends' in d
        assert 'reply' in d
        assert d['complaint']['detected'] is True


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestCreateCommentSchema:
    def test_valid_payload(self):
        schema = CreateCommentSchema()
        result = schema.load({
            'post_id': 'post-uuid-001',
            'platform': 'facebook',
            'platform_comment_id': 'fb_comment_123',
            'text': 'There is a big pothole on the road!',
            'author_name': 'Jane Citizen',
            'likes': 5,
        })
        assert result['platform'] == 'facebook'
        assert result['text'] == 'There is a big pothole on the road!'

    def test_instagram_platform_valid(self):
        from marshmallow import ValidationError as ME
        schema = CreateCommentSchema()
        result = schema.load({
            'post_id': 'post-001',
            'platform': 'instagram',
            'platform_comment_id': 'ig_001',
            'text': 'Great work!',
        })
        assert result['platform'] == 'instagram'

    def test_invalid_platform_rejected(self):
        from marshmallow import ValidationError as ME
        schema = CreateCommentSchema()
        with pytest.raises(ME):
            schema.load({
                'post_id': 'post-001',
                'platform': 'tiktok',
                'platform_comment_id': 'tk_001',
                'text': 'Hello',
            })

    def test_blank_text_rejected(self):
        from marshmallow import ValidationError as ME
        schema = CreateCommentSchema()
        with pytest.raises(ME):
            schema.load({
                'post_id': 'post-001',
                'platform': 'facebook',
                'platform_comment_id': 'fb_001',
                'text': '   ',
            })

    def test_missing_required_fields(self):
        from marshmallow import ValidationError as ME
        schema = CreateCommentSchema()
        with pytest.raises(ME):
            schema.load({'platform': 'facebook'})

    def test_defaults_applied(self):
        schema = CreateCommentSchema()
        result = schema.load({
            'post_id': 'post-001',
            'platform': 'facebook',
            'platform_comment_id': 'fb_001',
            'text': 'Hello',
        })
        assert result['likes'] == 0
        assert result['reply_count'] == 0
        assert result['parent_comment_id'] is None


class TestReplyCommentSchema:
    def test_valid_reply(self):
        schema = ReplyCommentSchema()
        result = schema.load({'reply_text': 'Thank you for your feedback!'})
        assert result['reply_text'] == 'Thank you for your feedback!'

    def test_blank_reply_rejected(self):
        from marshmallow import ValidationError as ME
        schema = ReplyCommentSchema()
        with pytest.raises(ME):
            schema.load({'reply_text': ''})

    def test_missing_reply_text_rejected(self):
        from marshmallow import ValidationError as ME
        schema = ReplyCommentSchema()
        with pytest.raises(ME):
            schema.load({})

    def test_too_long_reply_rejected(self):
        from marshmallow import ValidationError as ME
        schema = ReplyCommentSchema()
        with pytest.raises(ME):
            schema.load({'reply_text': 'x' * 8001})


class TestModerateCommentSchema:
    def test_valid_hidden(self):
        schema = ModerateCommentSchema()
        result = schema.load({'moderation_status': 'hidden'})
        assert result['moderation_status'] == 'hidden'

    def test_valid_spam(self):
        schema = ModerateCommentSchema()
        result = schema.load({'moderation_status': 'spam', 'reason': 'Spam link'})
        assert result['reason'] == 'Spam link'

    def test_invalid_status_rejected(self):
        from marshmallow import ValidationError as ME
        schema = ModerateCommentSchema()
        with pytest.raises(ME):
            schema.load({'moderation_status': 'banned'})

    def test_all_valid_statuses(self):
        schema = ModerateCommentSchema()
        for status in ('visible', 'hidden', 'deleted', 'spam'):
            result = schema.load({'moderation_status': status})
            assert result['moderation_status'] == status


# ── Service layer tests ───────────────────────────────────────────────────────

class TestCommentService:
    def test_upsert_creates_new_comment(self, db_session, district, social_post):
        comment, created = upsert_comment(
            district_id=district.id,
            post_id=social_post.id,
            platform='facebook',
            platform_comment_id='svc_test_001',
            text='Road is broken near main junction.',
            author_name='Test User',
            likes=2,
            run_ai=False,
        )
        assert created is True
        assert comment.id is not None
        assert comment.platform == 'facebook'
        assert comment.text == 'Road is broken near main junction.'
        assert comment.moderation_status == 'visible'

    def test_upsert_updates_existing_comment(self, db_session, district, social_post):
        upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='dup_test_001',
            text='Original text', likes=1, run_ai=False,
        )
        comment, created = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='dup_test_001',
            text='Updated text', likes=5, run_ai=False,
        )
        assert created is False
        assert comment.likes == 5
        assert comment.text == 'Updated text'

    def test_upsert_runs_ai_analysis(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_test_001',
            text='The road has a pothole. Very dangerous problem!',
            run_ai=True,
        )
        db_session.flush()
        assert comment.ai_status == 'processed'
        assert comment.language in ('en', 'tanglish', 'unknown')

    def test_upsert_increments_post_comment_count(self, db_session, district, social_post):
        initial = social_post.social_comment_count or 0
        upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='count_test_001',
            text='Great post!', run_ai=False,
        )
        db_session.refresh(social_post)
        assert (social_post.social_comment_count or 0) == initial + 1

    def test_upsert_threaded_reply(self, db_session, district, social_post, social_comment):
        reply, created = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='reply_test_001',
            text='Thank you for reporting.',
            parent_comment_id=social_comment.id,
            run_ai=False,
        )
        assert created is True
        assert reply.parent_comment_id == social_comment.id

    def test_get_comments_returns_paginated(self, db_session, district, social_post, social_comment):
        pagination = get_comments(district_id=district.id, post_id=social_post.id)
        assert pagination.total >= 1

    def test_get_comments_filter_platform(self, db_session, district, social_post, social_comment):
        pagination = get_comments(
            district_id=district.id,
            post_id=social_post.id,
            platform='facebook',
        )
        for c in pagination.items:
            assert c.platform == 'facebook'

    def test_get_comments_filter_is_replied(self, db_session, district, social_post, social_comment):
        pagination = get_comments(
            district_id=district.id,
            is_replied=False,
        )
        for c in pagination.items:
            assert c.is_replied is False

    def test_get_comment_by_id(self, db_session, district, social_comment):
        found = get_comment(district.id, social_comment.id)
        assert found.id == social_comment.id

    def test_get_comment_wrong_district_raises(self, db_session, social_comment):
        with pytest.raises(ValueError, match='not found'):
            get_comment('wrong-district-id', social_comment.id)

    def test_get_comment_nonexistent_raises(self, db_session, district):
        with pytest.raises(ValueError, match='not found'):
            get_comment(district.id, 'nonexistent-uuid')

    def test_moderate_comment_to_hidden(self, db_session, district, social_comment, admin_user):
        comment = moderate_comment(
            district_id=district.id,
            comment_id=social_comment.id,
            moderation_status='hidden',
            actor_id=admin_user.id,
            reason='Test moderation',
        )
        assert comment.moderation_status == 'hidden'

    def test_moderate_comment_to_spam(self, db_session, district, social_comment, admin_user):
        comment = moderate_comment(
            district_id=district.id,
            comment_id=social_comment.id,
            moderation_status='spam',
            actor_id=admin_user.id,
        )
        assert comment.moderation_status == 'spam'

    def test_moderate_invalid_status_raises(self, db_session, district, social_comment, admin_user):
        with pytest.raises(ValueError):
            moderate_comment(
                district_id=district.id,
                comment_id=social_comment.id,
                moderation_status='banned',
                actor_id=admin_user.id,
            )

    def test_bulk_analyse_processes_pending(self, db_session, district, social_post):
        # Create a fresh pending comment
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='bulk_ai_001',
            text='Water supply cut for 3 days! No response from office.',
            run_ai=False,
        )
        assert comment.ai_status == 'pending'
        count = bulk_analyse(district.id, batch_size=10)
        assert count >= 1
        db_session.refresh(comment)
        assert comment.ai_status == 'processed'


# ── AI analysis integration tests ────────────────────────────────────────────

class TestCommentAIAnalysis:
    def test_english_complaint_detected(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_eng_complaint_001',
            text='The road has a huge pothole and is very dangerous. This is a serious problem.',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        assert comment.is_complaint is True
        # AI may detect en or tanglish depending on keyword overlap — both are valid
        assert comment.language in ('en', 'tanglish')

    def test_emergency_detected(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_emergency_001',
            text='Fire in the building near school! Send ambulance urgently!',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        assert comment.is_emergency is True

    def test_spam_detected(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_spam_001',
            text='Click here to win lottery prize! Free offer limited time!',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        assert comment.is_spam is True

    def test_tanglish_detected(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_tanglish_001',
            text='Vanakkam! Romba naala tanni varala. Complaint pannrom.',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        assert comment.language == 'tanglish'
        assert comment.is_complaint is True

    def test_positive_sentiment_no_flags(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_positive_001',
            text='Excellent service! The team fixed the issue very quickly. Thank you!',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        # Sentiment may vary — key assertion is no emergency or spam
        assert comment.sentiment in ('positive', 'mixed', 'neutral')
        assert comment.is_spam is False
        assert comment.is_emergency is False

    def test_comment_analysis_record_created(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='instagram', platform_comment_id='ai_analysis_record_001',
            text='Garbage bin near our area is overflowing. Please clean it.',
            run_ai=True,
        )
        assert comment.ai_status == 'processed'
        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        assert analysis is not None
        assert analysis.status == 'processed'
        assert analysis.language is not None
        assert analysis.category in ('complaint', 'negative')
        assert analysis.issue_type == 'garbage'
        assert analysis.service_request_id is not None
        assert isinstance(analysis.keywords, list)
        assert analysis.summary
        assert isinstance(analysis.trend_tags, list)

    def test_suggested_reply_generated(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id, post_id=social_post.id,
            platform='facebook', platform_comment_id='ai_reply_001',
            text='The street light is broken for 2 weeks. No one is responding.',
            run_ai=True,
        )
        assert comment.suggested_reply is not None
        assert len(comment.suggested_reply) > 10

    def test_phase6_categories_keywords_and_summary_stored(self, db_session, district, social_post):
        comment, _ = upsert_comment(
            district_id=district.id,
            post_id=social_post.id,
            platform='facebook',
            platform_comment_id='phase6_analysis_001',
            text='When will the broken streetlight near the school be fixed?',
            run_ai=True,
        )
        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        assert analysis is not None
        assert analysis.category in ('complaint', 'question')
        assert analysis.issue_type == 'electricity'
        assert 'streetlight' in analysis.keywords or 'electricity' in analysis.keywords
        assert analysis.summary.startswith(analysis.category.title())

    @pytest.mark.parametrize(
        ('platform_id', 'text', 'issue_type', 'department_code'),
        [
            ('phase7_water_001', 'No water supply for 3 days. Please fix this issue.', 'water', 'WATER'),
            ('phase7_roads_001', 'Huge pothole and road damage near the junction.', 'roads', 'ROADS'),
            ('phase7_electricity_001', 'Power cut and streetlight not working on our street.', 'electricity', 'ELECTRICITY'),
            ('phase7_garbage_001', 'Garbage and waste are overflowing near the school.', 'garbage', 'SANITATION'),
            ('phase7_drainage_001', 'Blocked drain and sewage waterlogging outside our homes.', 'drainage', 'DRAINAGE'),
        ],
    )
    def test_phase7_auto_creates_service_requests(
        self, db_session, district, social_post, platform_id, text, issue_type, department_code
    ):
        comment, _ = upsert_comment(
            district_id=district.id,
            post_id=social_post.id,
            platform='facebook',
            platform_comment_id=platform_id,
            text=text,
            run_ai=True,
        )

        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        assert analysis.issue_type == issue_type
        assert analysis.service_request_id is not None

        request = ServiceRequest.query.get(analysis.service_request_id)
        assert request is not None
        assert request.status == 'submitted'
        assert f'issue:{issue_type}' in request.tags

        department = Department.query.get(request.department_id)
        assert department.code == department_code

    def test_phase7_reanalysis_does_not_duplicate_service_request(
        self, db_session, district, social_post
    ):
        comment, _ = upsert_comment(
            district_id=district.id,
            post_id=social_post.id,
            platform='facebook',
            platform_comment_id='phase7_idempotent_001',
            text='No water supply and pipeline leak near our street.',
            run_ai=True,
        )
        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        first_request_id = analysis.service_request_id

        analyse_comment(district.id, comment.id)
        db_session.refresh(analysis)

        assert analysis.service_request_id == first_request_id
        matches = [
            req for req in ServiceRequest.query.filter_by(district_id=district.id).all()
            if f'comment:{comment.id}' in (req.tags or [])
        ]
        assert len(matches) == 1


# ── API endpoint tests ────────────────────────────────────────────────────────

class TestCommentAPI:
    """Integration tests for /api/v1/social/comments and /posts/<id>/comments."""

    def _grant_all(self, db_session, admin_role):
        for action in ('create', 'read', 'update', 'reply', 'moderate'):
            _grant(db_session, admin_role, 'social_comment', action)

    def test_list_all_comments_requires_auth(self, client):
        resp = client.get('/api/v1/social/comments')
        assert resp.status_code == 401

    def test_list_all_comments_success(self, client, auth_headers, admin_role,
                                       db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get('/api/v1/social/comments', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['meta']['total'] >= 1

    def test_list_post_comments_success(self, client, auth_headers, admin_role,
                                        db_session, social_comment, social_post):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        for c in data:
            assert c['post_id'] == social_post.id

    def test_ingest_comment_success(self, client, auth_headers, admin_role,
                                    db_session, social_post):
        _grant(db_session, admin_role, 'social_comment', 'create')
        resp = client.post(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
            json={
                'platform': 'facebook',
                'platform_comment_id': 'api_ingest_001',
                'text': 'Water supply is cut for 2 days! Please fix.',
                'author_name': 'Resident A',
                'likes': 4,
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()['data']
        assert body['platform'] == 'facebook'
        assert body['text'] == 'Water supply is cut for 2 days! Please fix.'

    def test_ingest_comment_invalid_platform(self, client, auth_headers, admin_role,
                                             db_session, social_post):
        _grant(db_session, admin_role, 'social_comment', 'create')
        resp = client.post(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
            json={
                'platform': 'youtube',
                'platform_comment_id': 'yt_001',
                'text': 'hello',
            },
        )
        assert resp.status_code == 400

    def test_ingest_comment_blank_text(self, client, auth_headers, admin_role,
                                       db_session, social_post):
        _grant(db_session, admin_role, 'social_comment', 'create')
        resp = client.post(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
            json={
                'platform': 'facebook',
                'platform_comment_id': 'blank_001',
                'text': '   ',
            },
        )
        assert resp.status_code == 400

    def test_ingest_duplicate_returns_200(self, client, auth_headers, admin_role,
                                          db_session, social_comment, social_post):
        _grant(db_session, admin_role, 'social_comment', 'create')
        resp = client.post(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
            json={
                'platform': social_comment.platform,
                'platform_comment_id': social_comment.platform_comment_id,
                'text': 'Updated text',
                'likes': 10,
            },
        )
        assert resp.status_code == 200  # upsert

    def test_get_single_comment(self, client, auth_headers, admin_role,
                                db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get(
            f'/api/v1/social/comments/{social_comment.id}',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == social_comment.id

    def test_get_comment_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get('/api/v1/social/comments/nonexistent', headers=auth_headers)
        assert resp.status_code == 404

    def test_get_replies_empty(self, client, auth_headers, admin_role,
                               db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get(
            f'/api/v1/social/comments/{social_comment.id}/replies',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()['data'] == []

    def test_moderate_to_hidden(self, client, auth_headers, admin_role,
                                db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'moderate')
        resp = client.post(
            f'/api/v1/social/comments/{social_comment.id}/moderate',
            headers=auth_headers,
            json={'moderation_status': 'hidden', 'reason': 'Abusive content'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['data']['moderation_status'] == 'hidden'

    def test_moderate_invalid_status(self, client, auth_headers, admin_role,
                                     db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'moderate')
        resp = client.post(
            f'/api/v1/social/comments/{social_comment.id}/moderate',
            headers=auth_headers,
            json={'moderation_status': 'banned'},
        )
        assert resp.status_code == 400

    def test_analyse_single_comment(self, client, auth_headers, admin_role,
                                    db_session, social_comment):
        _grant(db_session, admin_role, 'social_comment', 'update')
        resp = client.post(
            f'/api/v1/social/comments/{social_comment.id}/analyse',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['status'] == 'processed'
        assert 'sentiment' in data
        assert 'complaint' in data

    def test_bulk_analyse_endpoint(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'social_comment', 'update')
        resp = client.post(
            '/api/v1/social/comments/analyse',
            headers=auth_headers,
            json={'batch_size': 10},
        )
        assert resp.status_code == 200
        assert 'processed' in resp.get_json()['data']

    def test_filter_by_sentiment(self, client, auth_headers, admin_role,
                                 db_session, social_post):
        _grant(db_session, admin_role, 'social_comment', 'read')
        _grant(db_session, admin_role, 'social_comment', 'create')
        # Ingest and process a clearly negative comment
        client.post(
            f'/api/v1/social/posts/{social_post.id}/comments',
            headers=auth_headers,
            json={
                'platform': 'facebook',
                'platform_comment_id': 'sentiment_filter_001',
                'text': 'Terrible service! Road is broken, garbage everywhere!',
            },
        )
        resp = client.get(
            '/api/v1/social/comments?sentiment=negative',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # Each returned item must have negative sentiment
        for item in resp.get_json()['data']:
            if item['sentiment']:
                assert item['sentiment'] == 'negative'

    def test_filter_complaints(self, client, auth_headers, admin_role,
                               db_session, social_post):
        _grant(db_session, admin_role, 'social_comment', 'read')
        resp = client.get(
            '/api/v1/social/comments?is_complaint=true',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for item in resp.get_json()['data']:
            assert item['is_complaint'] is True

    def test_unauthenticated_moderate_rejected(self, client, social_comment):
        resp = client.post(
            f'/api/v1/social/comments/{social_comment.id}/moderate',
            json={'moderation_status': 'hidden'},
        )
        assert resp.status_code == 401

