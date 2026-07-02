"""Marshmallow schemas for SocialAccount serialisation and validation.

Schemas:
  SocialAccountSchema        — full read schema (no credentials)
  SocialAccountWithCredsSchema — includes credentials (admin-only)
  ConnectAccountSchema       — validation for POST /social/accounts
  UpdateAccountSchema        — validation for PATCH /social/accounts/<id>
"""
from marshmallow import Schema, fields, validate, validates, ValidationError, post_load

VALID_PLATFORMS = frozenset({'facebook', 'instagram', 'youtube', 'x', 'telegram'})


class SocialAccountSchema(Schema):
    """Read schema — safe for any authenticated user (no credentials)."""
    id                  = fields.Str(dump_only=True)
    district_id         = fields.Str(dump_only=True)
    platform            = fields.Str(dump_only=True)
    label               = fields.Str(dump_only=True)
    platform_account_id = fields.Str(dump_only=True)
    username            = fields.Str(dump_only=True, allow_none=True)
    is_active           = fields.Bool(dump_only=True)
    config              = fields.Dict(dump_only=True)
    created_at          = fields.Str(dump_only=True)
    updated_at          = fields.Str(dump_only=True)


class SocialAccountWithCredsSchema(SocialAccountSchema):
    """Admin-only schema that includes credentials."""
    credentials = fields.Dict(dump_only=True)


class ConnectAccountSchema(Schema):
    """Validation schema for connecting a new social account."""
    platform = fields.Str(
        required=True,
        validate=validate.OneOf(sorted(VALID_PLATFORMS),
                                error='Platform must be one of: {choices}'),
    )
    label = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255,
                                 error='label must be 1–255 characters'),
    )
    platform_account_id = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
    )
    credentials = fields.Dict(
        required=True,
        error_messages={'required': 'credentials dict is required'},
    )
    username    = fields.Str(load_default=None, allow_none=True)
    webhook_secret = fields.Str(load_default=None, allow_none=True)
    config      = fields.Dict(load_default=dict)

    @validates('credentials')
    def validate_credentials(self, value):
        if not isinstance(value, dict) or not value:
            raise ValidationError('credentials must be a non-empty dict.')


class UpdateAccountSchema(Schema):
    """Validation schema for updating a social account."""
    label           = fields.Str(validate=validate.Length(min=1, max=255))
    username        = fields.Str(allow_none=True)
    credentials     = fields.Dict(allow_none=False)
    webhook_secret  = fields.Str(allow_none=True)
    is_active       = fields.Bool()
    config          = fields.Dict()
