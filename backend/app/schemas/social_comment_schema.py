"""Marshmallow schemas for SocialComment and CommentAnalysis.

Schemas:
  CommentAnalysisSchema   — read schema for AI analysis results
  SocialCommentSchema     — full read schema (optionally embeds analysis)
  CreateCommentSchema     — validate inbound comment data (from platform webhook)
  ReplyCommentSchema      — validate a staff reply to a comment
  ModerateCommentSchema   — validate moderation status update
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

VALID_MODERATION = frozenset({'visible', 'hidden', 'deleted', 'spam'})
VALID_PLATFORMS  = frozenset({'facebook', 'instagram'})


# ── CommentAnalysis ────────────────────────────────────────────────────────────

class SentimentSchema(Schema):
    label = fields.Str(dump_only=True, allow_none=True)
    score = fields.Float(dump_only=True, allow_none=True)


class DetectionSchema(Schema):
    detected   = fields.Bool(dump_only=True)
    confidence = fields.Float(dump_only=True)
    keywords   = fields.List(fields.Str(), dump_only=True)


class SpamSchema(Schema):
    detected   = fields.Bool(dump_only=True)
    confidence = fields.Float(dump_only=True)
    reasons    = fields.List(fields.Str(), dump_only=True)


class TrendsSchema(Schema):
    tags      = fields.List(fields.Str(), dump_only=True)
    top_topic = fields.Str(dump_only=True, allow_none=True)


class ReplyAnalysisSchema(Schema):
    suggested = fields.Str(dump_only=True, allow_none=True)
    category  = fields.Str(dump_only=True, allow_none=True)


class CommentAnalysisSchema(Schema):
    """Read schema for a CommentAnalysis row."""
    id             = fields.Str(dump_only=True)
    district_id    = fields.Str(dump_only=True)
    comment_id     = fields.Str(dump_only=True)
    language       = fields.Str(dump_only=True)
    sentiment      = fields.Nested(SentimentSchema, dump_only=True)
    complaint      = fields.Nested(DetectionSchema, dump_only=True)
    emergency      = fields.Nested(DetectionSchema, dump_only=True)
    spam           = fields.Nested(SpamSchema, dump_only=True)
    category       = fields.Str(dump_only=True)
    issue_type     = fields.Str(dump_only=True, allow_none=True)
    keywords       = fields.List(fields.Str(), dump_only=True)
    summary        = fields.Str(dump_only=True, allow_none=True)
    service_request_id = fields.Str(dump_only=True, allow_none=True)
    trends         = fields.Nested(TrendsSchema, dump_only=True)
    reply          = fields.Nested(ReplyAnalysisSchema, dump_only=True)
    status         = fields.Str(dump_only=True)
    error_message  = fields.Str(dump_only=True, allow_none=True)
    processing_ms  = fields.Int(dump_only=True)
    created_at     = fields.Str(dump_only=True)
    updated_at     = fields.Str(dump_only=True)


# ── SocialComment ──────────────────────────────────────────────────────────────

class SocialCommentSchema(Schema):
    """Full read schema for a social comment."""
    id                  = fields.Str(dump_only=True)
    district_id         = fields.Str(dump_only=True)
    post_id             = fields.Str(dump_only=True)
    parent_comment_id   = fields.Str(dump_only=True, allow_none=True)
    platform            = fields.Str(dump_only=True)
    platform_comment_id = fields.Str(dump_only=True)
    author_platform_id  = fields.Str(dump_only=True, allow_none=True)
    author_name         = fields.Str(dump_only=True, allow_none=True)
    author_username     = fields.Str(dump_only=True, allow_none=True)
    author_profile_url  = fields.Str(dump_only=True, allow_none=True)
    text                = fields.Str(dump_only=True)
    platform_created_at = fields.Str(dump_only=True, allow_none=True)
    likes               = fields.Int(dump_only=True)
    reply_count         = fields.Int(dump_only=True)
    moderation_status   = fields.Str(dump_only=True)
    is_replied          = fields.Bool(dump_only=True)
    reply_text          = fields.Str(dump_only=True, allow_none=True)
    reply_platform_id   = fields.Str(dump_only=True, allow_none=True)
    replied_at          = fields.Str(dump_only=True, allow_none=True)
    replied_by_id       = fields.Str(dump_only=True, allow_none=True)
    language            = fields.Str(dump_only=True)
    sentiment           = fields.Str(dump_only=True, allow_none=True)
    sentiment_score     = fields.Float(dump_only=True, allow_none=True)
    is_complaint        = fields.Bool(dump_only=True)
    is_emergency        = fields.Bool(dump_only=True)
    is_spam             = fields.Bool(dump_only=True)
    suggested_reply     = fields.Str(dump_only=True, allow_none=True)
    ai_status           = fields.Str(dump_only=True)
    analysis            = fields.Nested(CommentAnalysisSchema, dump_only=True, allow_none=True)
    created_at          = fields.Str(dump_only=True)
    updated_at          = fields.Str(dump_only=True)


class SocialCommentListSchema(Schema):
    """Lightweight schema for comment list (no embedded analysis)."""
    id                  = fields.Str(dump_only=True)
    post_id             = fields.Str(dump_only=True)
    parent_comment_id   = fields.Str(dump_only=True, allow_none=True)
    platform            = fields.Str(dump_only=True)
    platform_comment_id = fields.Str(dump_only=True)
    author_name         = fields.Str(dump_only=True, allow_none=True)
    author_username     = fields.Str(dump_only=True, allow_none=True)
    text                = fields.Str(dump_only=True)
    platform_created_at = fields.Str(dump_only=True, allow_none=True)
    likes               = fields.Int(dump_only=True)
    moderation_status   = fields.Str(dump_only=True)
    is_replied          = fields.Bool(dump_only=True)
    sentiment           = fields.Str(dump_only=True, allow_none=True)
    is_complaint        = fields.Bool(dump_only=True)
    is_emergency        = fields.Bool(dump_only=True)
    is_spam             = fields.Bool(dump_only=True)
    ai_status           = fields.Str(dump_only=True)
    created_at          = fields.Str(dump_only=True)


# ── Input schemas ──────────────────────────────────────────────────────────────

class CreateCommentSchema(Schema):
    """Validate inbound comment data (from platform webhook / manual sync)."""
    post_id             = fields.Str(required=True)
    platform            = fields.Str(
        required=True,
        validate=validate.OneOf(sorted(VALID_PLATFORMS),
                                error='platform must be facebook or instagram'),
    )
    platform_comment_id = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    text                = fields.Str(required=True, validate=validate.Length(min=1))
    parent_comment_id   = fields.Str(load_default=None, allow_none=True)
    author_platform_id  = fields.Str(load_default=None, allow_none=True)
    author_name         = fields.Str(load_default=None, allow_none=True)
    author_username     = fields.Str(load_default=None, allow_none=True)
    author_profile_url  = fields.Str(load_default=None, allow_none=True)
    platform_created_at = fields.Str(load_default=None, allow_none=True)
    likes               = fields.Int(load_default=0)
    reply_count         = fields.Int(load_default=0)

    @validates('text')
    def validate_text(self, value):
        if not value or not value.strip():
            raise ValidationError('Comment text cannot be blank.')


class ReplyCommentSchema(Schema):
    """Validate a staff reply to a comment."""
    reply_text = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=8000,
                                 error='reply_text must be 1–8000 characters'),
    )

    @validates('reply_text')
    def validate_reply(self, value):
        if not value or not value.strip():
            raise ValidationError('reply_text cannot be blank.')


class ModerateCommentSchema(Schema):
    """Validate a moderation status update."""
    moderation_status = fields.Str(
        required=True,
        validate=validate.OneOf(sorted(VALID_MODERATION),
                                error='moderation_status must be one of: {choices}'),
    )
    reason = fields.Str(load_default=None, allow_none=True)
