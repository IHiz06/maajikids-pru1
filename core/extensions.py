from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_marshmallow import Marshmallow
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flasgger import Swagger

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
ma = Marshmallow()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "MaajiKids API v3.0",
        "description": "Backend REST para el Centro de Estimulación MaajiKids",
        "version": "3.0.0",
        "contact": {"name": "MaajiKids"},
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Bearer token. Formato: Bearer <token>",
        }
    },
    "security": [{"Bearer": []}],
    "basePath": "/api/v1",
    "tags": [
        {"name": "Autenticación"},
        {"name": "Usuarios"},
        {"name": "Talleres"},
        {"name": "Niños"},
        {"name": "Pagos"},
        {"name": "Inscripciones"},
        {"name": "Evaluaciones"},
        {"name": "Contacto"},
        {"name": "IA - Recomendaciones"},
        {"name": "IA - Chat Maaji"},
        {"name": "Reportes PDF"},
    ],
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}

swagger = Swagger(template=swagger_template, config=swagger_config)
