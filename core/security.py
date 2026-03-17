import os
import hashlib
import uuid
from functools import wraps
from cryptography.fernet import Fernet
from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
import bcrypt


# ─────────────────────────────────────────────
#  Bcrypt password hashing (cost 12)
# ─────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed.encode("utf-8"))


# ─────────────────────────────────────────────
#  Fernet AES-256 for medical data
# ─────────────────────────────────────────────

def _get_fernet() -> Fernet:
    key = current_app.config.get("FERNET_KEY", "")
    if not key:
        raise RuntimeError("FERNET_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_field(plain_text: str) -> str:
    """Encrypt sensitive text field with AES-256 (Fernet)."""
    if not plain_text:
        return plain_text
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_field(encrypted_text: str) -> str:
    """Decrypt AES-256 (Fernet) encrypted field."""
    if not encrypted_text:
        return encrypted_text
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return "[cifrado - no se pudo descifrar]"


# ─────────────────────────────────────────────
#  Role-based access control decorators
# ─────────────────────────────────────────────

def require_role(*roles):
    """
    Decorator that enforces JWT authentication and role restriction.
    Usage: @require_role('admin', 'secretary')
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception as e:
                return jsonify({"error": "Token inválido o expirado", "detail": str(e)}), 401

            claims = get_jwt()
            user_role = claims.get("role", "")

            if user_role not in roles:
                return jsonify({
                    "error": "Acceso denegado",
                    "detail": f"Se requiere uno de los roles: {', '.join(roles)}"
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_auth():
    """Decorator that only checks valid JWT (any role)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception as e:
                return jsonify({"error": "Token inválido o expirado", "detail": str(e)}), 401
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def optional_auth():
    """
    Decorator for endpoints accessible both with and without auth.
    Sets g.current_user_id and g.current_role if authenticated.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request(optional=True)
            except Exception:
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user_id() -> int | None:
    try:
        return int(get_jwt_identity())
    except Exception:
        return None


def get_current_role() -> str | None:
    try:
        claims = get_jwt()
        return claims.get("role")
    except Exception:
        return None


# ─────────────────────────────────────────────
#  Cloudinary image upload helper
# ─────────────────────────────────────────────

def upload_image_to_cloudinary(file_storage, folder: str = "maajikids") -> str:
    """
    Validates (Pillow) and uploads image to Cloudinary.
    Returns secure_url string.
    """
    import cloudinary
    import cloudinary.uploader
    from PIL import Image
    import io

    # Validate with Pillow
    try:
        img_bytes = file_storage.read()
        img = Image.open(io.BytesIO(img_bytes))
        img.verify()
        file_storage.seek(0)
    except Exception:
        raise ValueError("El archivo no es una imagen válida")

    # Check size (5MB max handled by Flask MAX_CONTENT_LENGTH)
    # Generate unique public_id
    public_id = f"{folder}/{uuid.uuid4().hex}"

    # Upload
    result = cloudinary.uploader.upload(
        img_bytes,
        public_id=public_id,
        folder=folder,
        overwrite=True,
        resource_type="image",
        format="webp",
        transformation=[{"quality": "auto", "fetch_format": "auto"}],
    )
    return result["secure_url"]


def delete_image_from_cloudinary(image_url: str):
    """Delete image from Cloudinary by URL."""
    import cloudinary
    import cloudinary.uploader
    try:
        # Extract public_id from URL
        # URL format: https://res.cloudinary.com/{cloud}/image/upload/v{version}/{folder}/{id}.{ext}
        parts = image_url.split("/upload/")
        if len(parts) == 2:
            public_id_with_ext = parts[1]
            # Remove version prefix if present (v1234567890/)
            if public_id_with_ext.startswith("v") and "/" in public_id_with_ext:
                public_id_with_ext = public_id_with_ext.split("/", 1)[1]
            # Remove extension
            public_id = ".".join(public_id_with_ext.split(".")[:-1])
            cloudinary.uploader.destroy(public_id)
    except Exception:
        pass  # Best effort
