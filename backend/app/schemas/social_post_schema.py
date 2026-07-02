"""Marshmallow schemas for SocialPost serialisation and validation.

Schemas:
  SocialPostSchema        — read schema (full post including media)
  CreatePostSchema        — validation for POST /social/posts (draft / schedule)
  UpdatePostSchema        — validation for PATCH /social/posts/<id>
  PublishPostSchema       — optional extra params for POST /social/posts/<id>/publish
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

VALID_STATUSES  = frozenset({'draft', 'scheduled', 'published', 'failed', 'cancelled'})
VALID_PLATFORMS = frozenset({'facebook', 'instagram', 'youtube', 'x', 'telegram'})


class MediaItemRefSchema(Schema):
    """Embedded media item in a post response."""
    id            = fields.Str(dump_only=True)
    media_type    = fields.Str(dump_only=True)
    filename      = fields.Str(dump_only=True)
    url           = fields.Str(dump_only=True)
    thumbnail_url = fields.Str(dump_only=True, allow_none=True)
    alt_text      = fields.Str(dump_only=True, allow_none=True)
    mime_type     = fields.Str(dump_only=True, allow_none=True)
    file_size     = fields.Int(dump_only=True)


class SocialPostSchema(Schema):
    """Full read schema for a social post."""
    id                  = fields.Str(dump_only=True)
    district_id         = fields.Str(dump_only=True)
    account_id          = fields.Str(dump_only=True)
    author_id           = fields.Str(dump_only=True, allow_none=True)
    status              = fields.Str(dump_only=True)
    content             = fields.Str(dump_only=True)
    platform            = fields.Str(dump_only=True)
    platform_post_id    = fields.Str(dump_only=True, allow_none=True)
    scheduled_at        = fields.Str(dump_only=True, allow_none=True)
    published_at        = fields.Str(dump_only=True, allow_none=True)
    likes               = fields.Int(dump_only=True)
    comments            = fields.Int(dump_only=True)
    shares              = fields.Int(dump_only=True)
    views               = fields.Int(dump_only=True)
    social_comment_count= fields.Int(dump_only=True)
    meta                = fields.Dict(dump_only=True)
    ai_analysis         = fields.Dict(dump_only=True)
    error_message       = fields.Str(dump_only=True, allow_none=True)
    media               = fields.List(fields.Nested(MediaItemRefSchema), dump_only=True)
    created_at          = fields.Str(dump_only=True)
    updated_at          = fields.Str(dump_only=True)


class CreatePostSchema(Schema):
    """Input validation for creating a draft or scheduled post."""
    account_id   = fields.Str(required=True)
    content      = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=63206,
                                 error='content must be 1–63,206 characters'),
    )
    scheduled_at = fields.Str(load_default=None, allow_none=True)
    meta         = fields.Dict(load_default=dict)
    media_ids    = fields.List(fields.Str(), load_default=list)

    @validates('content')
    def validate_content(self, value):
        if not value or not value.strip():
            raise ValidationError('content cannot be blank.')


class UpdatePostSchema(Schema):
    """Input validation for editing a draft / scheduled post."""
    content      = fields.Str(validate=validate.Length(min=1, max=63206))
    scheduled_at = fields.Str(allow_none=True)
    meta         = fields.Dict()
    status       = fields.Str(
        validate=validate.OneOf(['draft', 'scheduled', 'cancelled'],
                                error='status must be draft, scheduled, or cancelled'),
    )


class PublishPostSchema(Schema):
    """Optional extra params when triggering immediate publish."""
    override_content = fields.Str(
        load_default=None, allow_none=True,
        validate=validate.Length(max=63206),
    )
    meta = fields.Dict(load_default=dict)
