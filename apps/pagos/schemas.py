from marshmallow import Schema, fields, validate


class CreatePreferenceSchema(Schema):
    workshop_id = fields.Int(required=True)
    child_id = fields.Int(required=True)


class UpdateEnrollmentSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(["active", "completed", "cancelled"])
    )
