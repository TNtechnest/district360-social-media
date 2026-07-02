"""AI Reply Suggestion module.

Generates contextually appropriate reply drafts for collected posts based on:
  - Detected language (English / Tamil / Tanglish)
  - Sentiment (positive / negative / neutral)
  - Content category (complaint / emergency / general / appreciation)

Baseline implementation uses template-based generation with variable
substitution.  To upgrade, replace ``_generate_reply`` with a call to an
LLM API (OpenAI, Google Gemini, or a self-hosted Llama / Mistral model).
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reply templates per (language, category) pair
# ---------------------------------------------------------------------------

TEMPLATES: dict[tuple[str, str], list[str]] = {
    # English — complaint
    ('en', 'complaint'): [
        "Thank you for bringing this to our attention. We have noted your complaint regarding '{topic}' "
        "and our team will address it at the earliest. Reference: {ref_id}.",
        "We sincerely apologise for the inconvenience caused. Your complaint about '{topic}' has been "
        "logged (Ref: {ref_id}) and assigned to the concerned department.",
        "Dear resident, we have received your complaint about '{topic}'. Our officers will visit the "
        "location within 48 hours. Track your complaint: {ref_id}.",
    ],
    # English — emergency
    ('en', 'emergency'): [
        "🚨 We have received your emergency report. Our emergency response team has been alerted "
        "immediately. Please call our helpline: 1800-XXX-XXXX if you need urgent assistance. Ref: {ref_id}.",
        "Emergency noted! We have dispatched a response team. Stay safe and call 100/108 if needed. "
        "Tracking ID: {ref_id}.",
    ],
    # English — appreciation
    ('en', 'appreciation'): [
        "Thank you for your kind words! We are glad that our services met your expectations. "
        "Your feedback motivates us to serve better. 🙏",
        "We appreciate your positive feedback! We will continue to work hard for the residents "
        "of {district_name}.",
    ],
    # English — general
    ('en', 'general'): [
        "Thank you for reaching out to {district_name} administration. We will get back to you shortly. "
        "Ref: {ref_id}.",
        "Hello! Thank you for your message. Our team will review it and respond within 24 hours. "
        "Ref: {ref_id}.",
    ],
    # Tanglish — complaint
    ('tanglish', 'complaint'): [
        "Ungal pughar pannathirku nandri. '{topic}' pathi ungal complaint-a note panninom. "
        "Enga team-u 48 mani nerathil paathukuvom. Reference: {ref_id}.",
        "Vanakkam! Ungal '{topic}' complaint-a receive panninom. Concerned department-ku assign "
        "pannagirrom. Ref No: {ref_id}.",
    ],
    # Tanglish — emergency
    ('tanglish', 'emergency'): [
        "🚨 Ungal emergency report-a receive panninom! Enga rescue team-a alert panninom. "
        "Urimai helpline: 1800-XXX-XXXX kku call pannunga. Ref: {ref_id}.",
    ],
    # Tanglish — appreciation
    ('tanglish', 'appreciation'): [
        "Ungal kind words-kku romba nandri! Enga work-a appreciate pannathirku miga santhosham. 🙏",
        "Nandri! {district_name} residents-ku nalla service thara mudiyum enbathu enga kural. Vaazhga!",
    ],
    # Tanglish — general
    ('tanglish', 'general'): [
        "Vanakkam! Ungal message-a receive panninom. Enga team 24 mani nerathil reply pannum. "
        "Ref: {ref_id}.",
    ],
    # Tamil — complaint
    ('ta', 'complaint'): [
        "உங்கள் புகாரை பதிவு செய்தோம். '{topic}' தொடர்பான சிக்கல் 48 மணி நேரத்தில் "
        "தீர்க்கப்படும். குறிப்பு எண்: {ref_id}.",
        "நன்றி! உங்கள் '{topic}' புகாரை சம்பந்தப்பட்ட துறைக்கு அனுப்பியுள்ளோம். "
        "கண்காணிப்பு எண்: {ref_id}.",
    ],
    # Tamil — emergency
    ('ta', 'emergency'): [
        "🚨 அவசர நிலை பதிவு செய்யப்பட்டது! மீட்புக் குழு உடனடியாக அனுப்பப்படுகிறது. "
        "உதவி தேவையெனில் 1800-XXX-XXXX அழைக்கவும். குறிப்பு: {ref_id}.",
    ],
    # Tamil — appreciation
    ('ta', 'appreciation'): [
        "உங்கள் பாராட்டுக்கு நன்றி! {district_name} வாசிகளுக்கு சிறந்த சேவை அளிப்பது "
        "எங்கள் குறிக்கோள். 🙏",
    ],
    # Tamil — general
    ('ta', 'general'): [
        "வணக்கம்! உங்கள் செய்தியை பெற்றோம். 24 மணி நேரத்தில் பதிலளிப்போம். "
        "குறிப்பு: {ref_id}.",
    ],
}


@dataclass
class ReplyResult:
    suggested_reply: str
    category: str        # complaint | emergency | appreciation | general
    language: str
    template_used: str = ''

    def to_dict(self):
        return {
            'suggested_reply': self.suggested_reply,
            'category': self.category,
            'language': self.language,
        }


def suggest_reply(
    text: str,
    language: str,
    is_complaint: bool = False,
    is_emergency: bool = False,
    sentiment_label: str = 'neutral',
    district_name: str = 'District360',
    ref_id: str = 'N/A',
    topic: str = 'the reported issue',
) -> ReplyResult:
    """Generate a reply suggestion for the given social media text.

    Args:
        text:           The original post / comment text.
        language:       Detected language (``'en'``, ``'ta'``, ``'tanglish'``).
        is_complaint:   Whether the AI complaint detector flagged this.
        is_emergency:   Whether the AI emergency detector flagged this.
        sentiment_label: Sentiment label from the sentiment analyser.
        district_name:  District display name for personalisation.
        ref_id:         Tracking / reference ID to include in the reply.
        topic:          Short topic string extracted from trend tags.

    Returns:
        :class:`ReplyResult` with the suggested reply text.
    """
    # Normalise language key
    lang = language if language in ('en', 'ta', 'tanglish') else 'en'

    # Determine category
    if is_emergency:
        category = 'emergency'
    elif is_complaint:
        category = 'complaint'
    elif sentiment_label == 'positive':
        category = 'appreciation'
    else:
        category = 'general'

    # Look up templates, fall back to English general
    templates = (
        TEMPLATES.get((lang, category))
        or TEMPLATES.get(('en', category))
        or TEMPLATES[('en', 'general')]
    )

    # Pick first template (in production, rotate or use LLM)
    template = templates[0]
    reply = template.format(
        topic=topic,
        ref_id=ref_id,
        district_name=district_name,
    )

    return ReplyResult(
        suggested_reply=reply,
        category=category,
        language=lang,
        template_used=template[:60],
    )
