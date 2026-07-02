"""AI Collector & collected post endpoints.

Routes
------
GET  /api/v1/social/collected             — list collected posts (filterable)
GET  /api/v1/social/collected/<id>        — get one collected post
PATCH /api/v1/social/collected/<id>/review — update review status
POST /api/v1/social/collected/collect      — trigger collection run
POST /api/v1/social/collected/analyze      — trigger AI analysis batch
POST /api/v1/social/collected/<id>/analyze — re-analyse a single post
"""
from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt
from app.services.social import collector_service
from app.services.social import account_service
from app.services.ai.ai_engine import analyze as ai_analyze
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params
from app.extensions import db

collector_bp = Blueprint('social_collector', __name__, url_prefix='/collected')


def _district():
    return get_jwt().get('district_id', '')


@collector_bp.route('', methods=['GET'])
@require_permission('collected_post', 'read')
def list_collected():
    page, per_page = validate_pagination_params(request.args.get('page', 1), request.args.get('per_page', 20))

    def _bool(key):
        v = request.args.get(key)
        if v is None:
            return None
        return v.lower() in ('1', 'true', 'yes')

    pagination = collector_service.get_collected_posts(
        district_id=_district(), page=page, per_page=per_page,
        platform=request.args.get('platform'),
        sentiment=request.args.get('sentiment'),
        is_complaint=_bool('is_complaint'),
        is_emergency=_bool('is_emergency'),
        is_spam=_bool('is_spam'),
        review_status=request.args.get('review_status'),
        search=request.args.get('search'),
    )
    return paginated_response([p.to_dict() for p in pagination.items], pagination)


@collector_bp.route('/<post_id>', methods=['GET'])
@require_permission('collected_post', 'read')
def get_collected(post_id):
    try:
        return success_response(data=collector_service.get_collected_post(_district(), post_id).to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@collector_bp.route('/<post_id>/review', methods=['PATCH'])
@require_permission('collected_post', 'update')
def update_review(post_id):
    data = request.get_json(silent=True) or {}
    review_status = data.get('review_status', '').strip()
    if not review_status:
        return error_response('review_status is required.', 400, 'VALIDATION_ERROR')
    try:
        post = collector_service.update_review_status(_district(), post_id, review_status)
        return success_response(data=post.to_dict(), message='Review status updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@collector_bp.route('/collect', methods=['POST'])
@require_permission('collected_post', 'create')
def trigger_collect():
    """Trigger a collection run for all active accounts in this district."""
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id')

    limit = min(int(data.get('limit', 50)), 100)
    comment_limit = min(int(data.get('comment_limit', 100)), 250)

    total = collector_service.CollectionSummary()
    per_account = {}

    if account_id:
        try:
            accounts = [account_service.get_account(_district(), account_id)]
        except ValueError as exc:
            return error_response(str(exc), 404, 'NOT_FOUND')
    else:
        from app.models.social_account import SocialAccount
        accounts = SocialAccount.query.filter_by(district_id=_district(), is_active=True).all()

    for account in accounts:
        summary = collector_service.collect_for_account_detailed(
            account,
            limit=limit,
            comment_limit=comment_limit,
            include_comments=account.platform in ('facebook', 'instagram'),
        )
        per_account[account.id] = summary.to_dict()
        total.posts += summary.posts
        total.comments += summary.comments
        total.updated += summary.updated
        total.errors += summary.errors

    payload = {**total.to_dict(), 'accounts': per_account}
    return success_response(data=payload, message=f'{total.new_items} new item(s) collected.')


@collector_bp.route('/analyze', methods=['POST'])
@require_permission('collected_post', 'update')
def trigger_analyze():
    """Run AI analysis on all pending collected posts in this district."""
    data = request.get_json(silent=True) or {}
    batch_size = min(int(data.get('batch_size', 100)), 500)
    count = collector_service.process_pending(batch_size=batch_size)
    return success_response(data={'processed': count}, message=f'{count} post(s) analysed.')


@collector_bp.route('/<post_id>/analyze', methods=['POST'])
@require_permission('collected_post', 'update')
def reanalyze_post(post_id):
    """Re-run AI analysis on a single collected post."""
    try:
        post = collector_service.get_collected_post(_district(), post_id)
        result = ai_analyze(post.raw_text, ref_id=post.id)
        fields = result.to_post_fields()
        for k, v in fields.items():
            setattr(post, k, v)
        db.session.commit()
        return success_response(data=post.to_dict(), message='Post re-analysed.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
