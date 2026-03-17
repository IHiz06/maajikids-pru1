from datetime import datetime, timezone
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt
from core.extensions import db
from core.security import hash_password, verify_password, get_current_user_id
from apps.usuarios.models import User, TokenBlacklist, RoleEnum


def register_parent(data: dict) -> dict:
    if User.query.filter_by(email=data["email"]).first():
        raise ValueError("El email ya está registrado")
    user = User(
        email=data["email"].lower().strip(),
        password_hash=hash_password(data["password"]),
        role=RoleEnum.parent,
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        phone=data.get("phone"),
    )
    db.session.add(user)
    db.session.commit()
    access_token = create_access_token(
        identity=str(user.id), additional_claims={"role": user.role.value}
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    return {"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token}


def login_user(data: dict) -> dict:
    user = User.query.filter_by(email=data["email"].lower().strip()).first()
    if not user or not verify_password(data["password"], user.password_hash):
        raise ValueError("Credenciales inválidas")
    if not user.is_active:
        raise ValueError("Cuenta desactivada. Contacta al administrador")
    user.last_login = datetime.utcnow()
    db.session.commit()
    access_token = create_access_token(
        identity=str(user.id), additional_claims={"role": user.role.value}
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    return {"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token}


def logout_user(jti: str, user_id: int, expires_at: datetime):
    blacklist_entry = TokenBlacklist(jti=jti, user_id=user_id, expires_at=expires_at)
    db.session.add(blacklist_entry)
    db.session.commit()


def create_user(data: dict) -> User:
    if User.query.filter_by(email=data["email"]).first():
        raise ValueError("El email ya está registrado")
    role = RoleEnum[data["role"]]
    user = User(
        email=data["email"].lower().strip(),
        password_hash=hash_password(data["password"]),
        role=role,
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        phone=data.get("phone"),
    )
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user: User, data: dict) -> User:
    if "first_name" in data:
        user.first_name = data["first_name"].strip()
    if "last_name" in data:
        user.last_name = data["last_name"].strip()
    if "phone" in data:
        user.phone = data["phone"]
    if "password" in data:
        user.password_hash = hash_password(data["password"])
    if "is_active" in data:
        user.is_active = data["is_active"]
    db.session.commit()
    return user


def deactivate_user(user: User) -> User:
    user.is_active = False
    db.session.commit()
    return user


def clean_expired_blacklist():
    """Cleanup job: remove expired blacklist entries."""
    now = datetime.utcnow()
    TokenBlacklist.query.filter(TokenBlacklist.expires_at < now).delete()
    db.session.commit()
