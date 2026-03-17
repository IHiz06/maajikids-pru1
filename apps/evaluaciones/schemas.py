from marshmallow import Schema, fields, validate, validates, ValidationError


class CreateEvaluationSchema(Schema):
    child_id = fields.Int(required=True)
    workshop_id = fields.Int(required=True)
    evaluation_date = fields.Date(required=True)
    score_language = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    score_motor = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    score_social = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    score_cognitive = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    observations = fields.Str(load_default=None, allow_none=True)


class UpdateEvaluationSchema(Schema):
    evaluation_date = fields.Date()
    score_language = fields.Int(validate=validate.Range(min=1, max=10))
    score_motor = fields.Int(validate=validate.Range(min=1, max=10))
    score_social = fields.Int(validate=validate.Range(min=1, max=10))
    score_cognitive = fields.Int(validate=validate.Range(min=1, max=10))
    observations = fields.Str(allow_none=True)
