from marshmallow import Schema, fields, validate


class CreateWorkshopSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default="")
    teacher_id = fields.Int(load_default=None, allow_none=True)
    schedule = fields.Str(load_default="")
    max_capacity = fields.Int(required=True, validate=validate.Range(min=1, max=100))
    price = fields.Float(required=True, validate=validate.Range(min=0))
    is_active = fields.Bool(load_default=True)


class UpdateWorkshopSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str()
    teacher_id = fields.Int(allow_none=True)
    schedule = fields.Str()
    max_capacity = fields.Int(validate=validate.Range(min=1, max=100))
    price = fields.Float(validate=validate.Range(min=0))
    is_active = fields.Bool()
