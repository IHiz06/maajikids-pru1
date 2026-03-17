import os
import cloudinary
from flask import Flask, jsonify
from flask_talisman import Talisman
from flask_jwt_extended import get_jwt

from config import config_map
from core.extensions import db, jwt, migrate, ma, cors, limiter, swagger


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    app = Flask(__name__, static_folder=None)

    # Load config
    cfg = config_map.get(config_name, config_map["default"])
    app.config.from_object(cfg)

    # ─── Extensions ───────────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})
    limiter.init_app(app)
    swagger.init_app(app)

    # Talisman (security headers) - disabled in dev
    if config_name == "production":
        Talisman(app, force_https=True, content_security_policy=False)

    # ─── Cloudinary ───────────────────────────────────────
    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
    )

    # ─── JWT token blacklist check ─────────────────────────
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from apps.usuarios.models import TokenBlacklist
        jti = jwt_payload["jti"]
        token = db.session.query(TokenBlacklist).filter_by(jti=jti).first()
        return token is not None

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token revocado. Por favor inicia sesión nuevamente."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token expirado. Usa /auth/refresh para renovar."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"error": "Token inválido.", "detail": str(error)}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"error": "Token de autorización requerido."}), 401

    # ─── Register Blueprints ──────────────────────────────
    from apps.usuarios.routes import usuarios_bp
    from apps.talleres.routes import talleres_bp
    from apps.ninos.routes import ninos_bp
    from apps.pagos.routes import pagos_bp
    from apps.evaluaciones.routes import evaluaciones_bp
    from apps.contacto.routes import contacto_bp
    from apps.ia.routes import ia_bp
    from apps.reportes.routes import reportes_bp

    app.register_blueprint(usuarios_bp, url_prefix="/api/v1")
    app.register_blueprint(talleres_bp, url_prefix="/api/v1")
    app.register_blueprint(ninos_bp, url_prefix="/api/v1")
    app.register_blueprint(pagos_bp, url_prefix="/api/v1")
    app.register_blueprint(evaluaciones_bp, url_prefix="/api/v1")
    app.register_blueprint(contacto_bp, url_prefix="/api/v1")
    app.register_blueprint(ia_bp, url_prefix="/api/v1")
    app.register_blueprint(reportes_bp, url_prefix="/api/v1")

    # ─── Health check ─────────────────────────────────────
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "version": "3.0.0", "project": "MaajiKids"})

    # ─── 404 / 405 handlers ───────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Ruta no encontrada"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Método no permitido"}), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "Archivo demasiado grande. Máximo 5MB"}), 413

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"error": "Demasiadas peticiones. Intenta más tarde."}), 429

    return app
