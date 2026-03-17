from marshmallow import Schema, fields, validate, validates, ValidationError, pre_load


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(load_default=None, validate=validate.Length(max=20))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class CreateUserSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    role = fields.Str(
        required=True,
        validate=validate.OneOf(["admin", "teacher", "secretary", "parent"]),
    )
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(load_default=None, validate=validate.Length(max=20))


class UpdateUserSchema(Schema):
    first_name = fields.Str(validate=validate.Length(min=1, max=100))
    last_name = fields.Str(validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(max=20), allow_none=True)
    password = fields.Str(validate=validate.Length(min=8))
    is_active = fields.Bool()


class UserOutSchema(Schema):
    id = fields.Int()
    email = fields.Email()
    role = fields.Str()
    first_name = fields.Str()
    last_name = fields.Str()
    full_name = fields.Method("get_full_name")
    phone = fields.Str()
    is_active = fields.Bool()
    created_at = fields.DateTime(format="iso")
    last_login = fields.DateTime(format="iso", allow_none=True)

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
