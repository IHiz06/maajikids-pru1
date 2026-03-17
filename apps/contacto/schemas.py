from marshmallow import Schema, fields, validate


class CreateContactMessageSchema(Schema):
    sender_name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    sender_email = fields.Email(required=True)
    subject = fields.Str(required=True, validate=validate.Length(min=2, max=300))
    body = fields.Str(required=True, validate=validate.Length(min=10))


class UpdateContactStatusSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(["read", "replied"])
    )


class ReplyContactSchema(Schema):
    reply_body = fields.Str(required=True, validate=validate.Length(min=5))
