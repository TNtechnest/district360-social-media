"""AI Engine direct-access endpoints.

Routes
------
POST /api/v1/ai/analyze          — run full AI pipeline on arbitrary text
POST /api/v1/ai/sentiment        — sentiment analysis only
POST /api/v1/ai/detect/complaint — complaint detection only
POST /api/v1/ai/detect/emergency — emergency detection only
POST /api/v1/ai/detect/spam      — spam detection only
POST /api/v1/ai/detect/trends    — trend detection only
POST /api/v1/ai/reply            — reply suggestion only
POST /api/v1/ai/language         — language detection only
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from app.services.ai.ai_engine import analyze as ai_analyze
from app.services.ai.language_detector import detect_language
from app.services.ai.sentiment_analyzer import analyze_sentiment
from app.services.ai.detectors import detect_complaint, detect_emergency, detect_spam, detect_trends
from app.services.ai.reply_suggester import suggest_reply
from app.utils.responses import success_response, error_response

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


def _require_text(data: dict):
    text = data.get('text', '').strip()
    if not text:
        return None, error_response('text is required.', 400, 'VALIDATION_ERROR')
    return text, None


@ai_bp.route('/analyze', methods=['POST'])
@jwt_required()
def analyze_text():
    """Run the full AI pipeline on arbitrary text.

    Request body (JSON)::

        {
          "text": "Romba naala tanni varala. Enna problem?",
          "district_name": "Metro District",
          "ref_id": "REF-001"
        }
    """
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    result = ai_analyze(
        text=text,
        district_name=data.get('district_name', 'District360'),
        ref_id=data.get('ref_id', 'N/A'),
    )
    return success_response(data=result.to_dict())


@ai_bp.route('/sentiment', methods=['POST'])
@jwt_required()
def sentiment():
    """Sentiment analysis only."""
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    language = data.get('language') or detect_language(text)
    result = analyze_sentiment(text, language)
    return success_response(data=result.to_dict())


@ai_bp.route('/detect/complaint', methods=['POST'])
@jwt_required()
def complaint():
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    language = data.get('language') or detect_language(text)
    return success_response(data=detect_complaint(text, language))


@ai_bp.route('/detect/emergency', methods=['POST'])
@jwt_required()
def emergency():
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    language = data.get('language') or detect_language(text)
    return success_response(data=detect_emergency(text, language))


@ai_bp.route('/detect/spam', methods=['POST'])
@jwt_required()
def spam():
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    language = data.get('language') or detect_language(text)
    return success_response(data=detect_spam(text, language))


@ai_bp.route('/detect/trends', methods=['POST'])
@jwt_required()
def trends():
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    return success_response(data=detect_trends(text))


@ai_bp.route('/reply', methods=['POST'])
@jwt_required()
def reply():
    """Generate a reply suggestion.

    Request body (JSON)::

        {
          "text": "Tanni varala. Plz fix pannunga.",
          "language": "tanglish",
          "is_complaint": true,
          "district_name": "Metro District",
          "ref_id": "COMP-2026-001"
        }
    """
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    language = data.get('language') or detect_language(text)
    sentiment_result = analyze_sentiment(text, language)
    result = suggest_reply(
        text=text,
        language=language,
        is_complaint=data.get('is_complaint', False),
        is_emergency=data.get('is_emergency', False),
        sentiment_label=sentiment_result.label,
        district_name=data.get('district_name', 'District360'),
        ref_id=data.get('ref_id', 'N/A'),
        topic=data.get('topic', 'the reported issue'),
    )
    return success_response(data=result.to_dict())


@ai_bp.route('/language', methods=['POST'])
@jwt_required()
def language():
    """Detect language of input text."""
    data = request.get_json(silent=True) or {}
    text, err = _require_text(data)
    if err:
        return err
    lang = detect_language(text)
    return success_response(data={'language': lang, 'text_preview': text[:80]})
