from marshmallow import Schema, fields, validate
from datetime import date


def validate_age_max_6(dob):
    from datetime import date
    today = date.today()
    age_years = (today.year - dob.year) - ((today.month, today.day) < (dob.month, dob.day))
    if age_years > 6:
        from marshmallow import ValidationError
        raise ValidationError("MaajiKids atiende niños de hasta 6 años")
    if dob > today:
        from marshmallow import ValidationError
        raise ValidationError("La fecha de nacimiento no puede ser futura")


class CreateChildSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    date_of_birth = fields.Date(required=True, validate=validate_age_max_6)
    gender = fields.Str(required=True, validate=validate.OneOf(["M", "F", "otro"]))
    medical_info = fields.Str(load_default=None, allow_none=True)
    allergies = fields.Str(load_default=None, allow_none=True)
    emergency_contact = fields.Str(load_default="", validate=validate.Length(max=200))


class UpdateChildSchema(Schema):
    full_name = fields.Str(validate=validate.Length(min=2, max=200))
    date_of_birth = fields.Date(validate=validate_age_max_6)
    gender = fields.Str(validate=validate.OneOf(["M", "F", "otro"]))
    medical_info = fields.Str(allow_none=True)
    allergies = fields.Str(allow_none=True)
    emergency_contact = fields.Str(validate=validate.Length(max=200))
    is_active = fields.Bool()
