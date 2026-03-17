from marshmallow import Schema, fields, validate


class GenerateRecommendationSchema(Schema):
    evaluation_id = fields.Int(required=True)


class ChatSchema(Schema):
    message = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
    session_id = fields.Int(load_default=None, allow_none=True)


class VisibilitySchema(Schema):
    is_visible_to_parent = fields.Bool(required=True)
