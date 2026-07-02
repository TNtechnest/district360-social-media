"""Unit tests for the AI Engine and all sub-modules.

Covers:
  - Language detection (English, Tamil, Tanglish, unknown)
  - Sentiment analysis (positive, negative, neutral, mixed — all three languages)
  - Complaint detection
  - Emergency detection
  - Spam detection
  - Trend detection
  - Reply suggestion
  - Full AI pipeline (ai_engine.analyze)
"""
import pytest
from app.services.ai.language_detector import detect_language, normalize_tanglish
from app.services.ai.sentiment_analyzer import analyze_sentiment
from app.services.ai.detectors import detect_complaint, detect_emergency, detect_spam, detect_trends
from app.services.ai.reply_suggester import suggest_reply
from app.services.ai.ai_engine import analyze


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestLanguageDetector:
    def test_english(self):
        assert detect_language('The water supply is broken near our area.') == 'en'

    def test_tamil_unicode(self):
        assert detect_language('தண்ணீர் வரவில்லை. உதவி வேண்டும்.') == 'ta'

    def test_tanglish(self):
        assert detect_language('Vanakkam! Romba naala tanni varala. Plz sollunga.') == 'tanglish'

    def test_empty_text(self):
        assert detect_language('') == 'unknown'

    def test_whitespace_only(self):
        assert detect_language('   ') == 'unknown'

    def test_normalize_tanglish(self):
        result = normalize_tanglish('  VANAKKAM   bro  ')
        assert result == 'vanakkam   bro'


# ---------------------------------------------------------------------------
# Sentiment analysis
# ---------------------------------------------------------------------------

class TestSentimentAnalyzer:
    def test_english_positive(self):
        r = analyze_sentiment('The service was excellent and I am very happy!', 'en')
        assert r.label == 'positive'
        assert r.score > 0

    def test_english_negative(self):
        r = analyze_sentiment('The road is terrible and completely broken. Worst service ever.', 'en')
        assert r.label == 'negative'
        assert r.score < 0

    def test_english_neutral(self):
        r = analyze_sentiment('Hello, I am testing this system.', 'en')
        assert r.label == 'neutral'
        assert r.score == 0.0

    def test_english_mixed(self):
        r = analyze_sentiment('The team is helpful but the road is terrible.', 'en')
        assert r.label in ('mixed', 'negative', 'positive')

    def test_tamil_positive(self):
        r = analyze_sentiment('நன்றி! மிகவும் நல்ல சேவை. திருப்தி.', 'ta')
        assert r.label in ('positive', 'neutral')

    def test_tamil_negative(self):
        r = analyze_sentiment('தண்ணீர் இல்லை. ஊழல் நடக்கிறது. புகார்.', 'ta')
        assert r.label in ('negative', 'mixed')

    def test_tanglish_positive(self):
        r = analyze_sentiment('Romba nalla service. Thanks bro.', 'tanglish')
        assert r.label in ('positive', 'neutral')

    def test_tanglish_negative(self):
        r = analyze_sentiment('Romba mosama iruku. Waste complaint pannala.', 'tanglish')
        assert r.label in ('negative', 'mixed')

    def test_empty_text(self):
        r = analyze_sentiment('', 'en')
        assert r.label == 'neutral'
        assert r.score == 0.0


# ---------------------------------------------------------------------------
# Complaint detection
# ---------------------------------------------------------------------------

class TestComplaintDetector:
    def test_detects_english_complaint(self):
        r = detect_complaint('There is a pothole in the road. It is a serious problem.', 'en')
        assert r['is_complaint'] is True
        assert r['confidence'] > 0

    def test_detects_tanglish_complaint(self):
        r = detect_complaint('Tanni varala bro. Complaint panrom.', 'tanglish')
        assert r['is_complaint'] is True

    def test_detects_tamil_complaint(self):
        r = detect_complaint('தண்ணீர் இல்லை. புகார் செய்கிறேன்.', 'ta')
        assert r['is_complaint'] is True

    def test_no_complaint(self):
        r = detect_complaint('Good morning! Have a great day.', 'en')
        assert r['is_complaint'] is False

    def test_result_keys(self):
        r = detect_complaint('broken road', 'en')
        assert 'is_complaint' in r
        assert 'confidence' in r
        assert 'matched_keywords' in r


# ---------------------------------------------------------------------------
# Emergency detection
# ---------------------------------------------------------------------------

class TestEmergencyDetector:
    def test_fire_emergency(self):
        r = detect_emergency('There is a fire in building 3, please send ambulance urgently!', 'en')
        assert r['is_emergency'] is True
        assert r['confidence'] >= 0.8

    def test_flood_emergency(self):
        r = detect_emergency('flood aaguthu! Help pannunga!', 'tanglish')
        assert r['is_emergency'] is True

    def test_tamil_emergency(self):
        r = detect_emergency('தீ பிடித்துவிட்டது! உதவி வேண்டும்.', 'ta')
        assert r['is_emergency'] is True

    def test_no_emergency(self):
        r = detect_emergency('Please fix the streetlight at corner.', 'en')
        assert r['is_emergency'] is False

    def test_result_keys(self):
        r = detect_emergency('help', 'en')
        assert 'is_emergency' in r
        assert 'confidence' in r
        assert 'matched_keywords' in r


# ---------------------------------------------------------------------------
# Spam detection
# ---------------------------------------------------------------------------

class TestSpamDetector:
    def test_detects_spam_keywords(self):
        r = detect_spam('Click here to win a lottery prize! Limited time offer.', 'en')
        assert r['is_spam'] is True
        assert r['confidence'] > 0

    def test_detects_multiple_urls(self):
        r = detect_spam('Check https://a.com and https://b.com and https://c.com', 'en')
        assert r['is_spam'] is True

    def test_no_spam(self):
        r = detect_spam('The garbage bin near my house has not been emptied for 3 days.', 'en')
        assert r['is_spam'] is False

    def test_result_keys(self):
        r = detect_spam('buy now', 'en')
        assert 'is_spam' in r
        assert 'confidence' in r
        assert 'reasons' in r


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

class TestTrendDetector:
    def test_water_topic(self):
        r = detect_trends('The water supply pipeline is leaking near the junction.')
        assert 'water' in r['tags']
        assert r['top_topic'] == 'water'

    def test_roads_topic(self):
        r = detect_trends('There are huge potholes on the main road. Traffic is stuck.')
        assert 'roads' in r['tags']

    def test_multiple_topics(self):
        r = detect_trends('No water and the road has a pothole near the hospital.')
        assert len(r['tags']) >= 2

    def test_no_topic(self):
        r = detect_trends('Hello world, testing 1 2 3.')
        assert r['top_topic'] is None

    def test_corruption_topic(self):
        r = detect_trends('There is corruption and bribe taking in the office.')
        assert 'corruption' in r['tags']


# ---------------------------------------------------------------------------
# Reply suggestion
# ---------------------------------------------------------------------------

class TestReplySuggester:
    def test_english_complaint_reply(self):
        r = suggest_reply(
            text='The road is broken.', language='en',
            is_complaint=True, district_name='Test District', ref_id='REF-001',
        )
        assert r.category == 'complaint'
        assert 'REF-001' in r.suggested_reply
        assert len(r.suggested_reply) > 20

    def test_english_emergency_reply(self):
        r = suggest_reply(text='fire!', language='en', is_emergency=True, ref_id='EMG-001')
        assert r.category == 'emergency'
        assert '🚨' in r.suggested_reply

    def test_tanglish_complaint_reply(self):
        r = suggest_reply(
            text='tanni varala', language='tanglish',
            is_complaint=True, ref_id='TG-001',
        )
        assert r.language == 'tanglish'
        assert len(r.suggested_reply) > 10

    def test_tamil_reply(self):
        r = suggest_reply(text='புகார்', language='ta', is_complaint=True, ref_id='TA-001')
        assert r.language == 'ta'
        assert len(r.suggested_reply) > 10

    def test_positive_sentiment_appreciation(self):
        r = suggest_reply(text='great service!', language='en',
                          sentiment_label='positive', district_name='Metro')
        assert r.category == 'appreciation'

    def test_result_keys(self):
        r = suggest_reply('hello', 'en')
        d = r.to_dict()
        assert 'suggested_reply' in d
        assert 'category' in d
        assert 'language' in d


# ---------------------------------------------------------------------------
# Full AI Engine pipeline
# ---------------------------------------------------------------------------

class TestAIEngine:
    def test_full_pipeline_english_complaint(self):
        result = analyze(
            'The pothole on main road is very dangerous. It caused an accident.',
            district_name='Test District', ref_id='REF-TEST',
        )
        assert result.language == 'en'
        assert result.is_complaint is True
        assert result.sentiment_label in ('negative', 'mixed', 'neutral')
        assert result.trend_tags  # should have 'roads' or 'safety'
        assert len(result.suggested_reply) > 10

    def test_full_pipeline_tanglish(self):
        result = analyze('Vanakkam! Romba naala tanni varala. Complaint panrom.', ref_id='TG-2026')
        assert result.language == 'tanglish'
        assert result.is_complaint is True

    def test_full_pipeline_tamil_emergency(self):
        result = analyze('தீ பிடித்துவிட்டது! உதவி வேண்டும்.')
        assert result.language == 'ta'
        assert result.is_emergency is True

    def test_empty_text(self):
        result = analyze('')
        assert result.language == 'unknown'
        assert result.sentiment_label == 'neutral'

    def test_to_post_fields(self):
        result = analyze('broken road near junction')
        fields = result.to_post_fields()
        assert 'language' in fields
        assert 'sentiment' in fields
        assert 'is_complaint' in fields
        assert 'ai_status' in fields
        assert fields['ai_status'] == 'processed'

    def test_to_dict(self):
        result = analyze('water leak problem')
        d = result.to_dict()
        assert 'sentiment' in d
        assert 'complaint' in d
        assert 'emergency' in d
        assert 'spam' in d
        assert 'trends' in d
        assert 'reply' in d
