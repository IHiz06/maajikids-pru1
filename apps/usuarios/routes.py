from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, get_jwt,
    create_access_token, decode_token,
)
from marshmallow import ValidationError

from core.extensions import db, limiter
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.usuarios.models import User, RoleEnum
from apps.usuarios.schemas import RegisterSchema, LoginSchema, CreateUserSchema, UpdateUserSchema
from apps.usuarios.services import (
    register_parent, login_user, logout_user,
    create_user, update_user, deactivate_user,
)

usuarios_bp = Blueprint("usuarios", __name__)

# ─── AUTH ─────────────────────────────────────────────────────────────────────

@usuarios_bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per minute")
def auth_register():
    """
    Registro de nuevo padre/madre.
    ---
    tags: [Autenticación]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password, first_name, last_name]
          properties:
            email: {type: string}
            password: {type: string, minLength: 8}
            first_name: {type: string}
            last_name: {type: string}
            phone: {type: string}
    responses:
      201:
        description: Registro exitoso. Retorna access_token y refresh_token.
      400:
        description: Datos inválidos o email ya registrado.
    """
    schema = RegisterSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400
    try:
        result = register_parent(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result), 201


@usuarios_bp.route("/auth/login", methods=["POST"])
@limiter.limit("20 per minute")
def auth_login():
    """
    Login con email y contraseña.
    ---
    tags: [Autenticación]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string}
            password: {type: string}
    responses:
      200:
        description: Login exitoso.
      401:
        description: Credenciales inválidas.
    """
    schema = LoginSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400
    try:
        result = login_user(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    return jsonify(result), 200


@usuarios_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def auth_refresh():
    """
    Renueva el access_token usando refresh_token.
    ---
    tags: [Autenticación]
    security: [{Bearer: []}]
    responses:
      200:
        description: Nuevo access_token generado.
    """
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user or not user.is_active:
        return jsonify({"error": "Usuario inactivo o no encontrado"}), 403
    access_token = create_access_token(
        identity=identity, additional_claims={"role": user.role.value}
    )
    return jsonify({"access_token": access_token}), 200


@usuarios_bp.route("/auth/logout", methods=["POST"])
@jwt_required()
def auth_logout():
    """
    Logout seguro: invalida el token en la blacklist.
    ---
    tags: [Autenticación]
    security: [{Bearer: []}]
    responses:
      200:
        description: Sesión cerrada correctamente.
    """
    jti = get_jwt()["jti"]
    exp = get_jwt()["exp"]
    user_id = int(get_jwt_identity())
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
    logout_user(jti, user_id, expires_at)
    return jsonify({"message": "Sesión cerrada correctamente"}), 200


# ─── USERS (Admin) ────────────────────────────────────────────────────────────

@usuarios_bp.route("/users/", methods=["GET"])
@require_role("admin")
def list_users():
    """
    Lista todos los usuarios del sistema.
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: role
        type: string
        enum: [admin, teacher, secretary, parent]
      - in: query
        name: is_active
        type: boolean
      - in: query
        name: page
        type: integer
      - in: query
        name: per_page
        type: integer
    responses:
      200:
        description: Lista paginada de usuarios.
    """
    role_filter = request.args.get("role")
    is_active_filter = request.args.get("is_active")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    q = User.query
    if role_filter:
        try:
            q = q.filter(User.role == RoleEnum[role_filter])
        except KeyError:
            return jsonify({"error": "Rol inválido"}), 400
    if is_active_filter is not None:
        q = q.filter(User.is_active == (is_active_filter.lower() == "true"))

    paginated = q.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "users": [u.to_dict() for u in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@usuarios_bp.route("/users/", methods=["POST"])
@require_role("admin")
def create_user_endpoint():
    """
    Crea un usuario con cualquier rol (admin, teacher, secretary, parent).
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password, role, first_name, last_name]
          properties:
            email: {type: string}
            password: {type: string}
            role: {type: string, enum: [admin, teacher, secretary, parent]}
            first_name: {type: string}
            last_name: {type: string}
            phone: {type: string}
    responses:
      201:
        description: Usuario creado.
    """
    schema = CreateUserSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400
    try:
        user = create_user(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(user.to_dict()), 201


@usuarios_bp.route("/users/<int:user_id>", methods=["GET"])
@require_auth()
def get_user(user_id):
    """
    Obtiene el perfil completo de un usuario.
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
    responses:
      200:
        description: Perfil del usuario.
      403:
        description: Sin permisos.
      404:
        description: Usuario no encontrado.
    """
    current_id = get_current_user_id()
    current_role = get_current_role()
    # Only admin or the user themselves
    if current_role != "admin" and current_id != user_id:
        return jsonify({"error": "Acceso denegado"}), 403
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(user.to_dict()), 200


@usuarios_bp.route("/users/<int:user_id>", methods=["PATCH"])
@require_auth()
def update_user_endpoint(user_id):
    """
    Actualiza datos del usuario.
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            first_name: {type: string}
            last_name: {type: string}
            phone: {type: string}
            password: {type: string}
            is_active: {type: boolean}
    responses:
      200:
        description: Usuario actualizado.
    """
    current_id = get_current_user_id()
    current_role = get_current_role()
    if current_role != "admin" and current_id != user_id:
        return jsonify({"error": "Acceso denegado"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    schema = UpdateUserSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    # Non-admin cannot change is_active
    if "is_active" in data and current_role != "admin":
        return jsonify({"error": "Solo el admin puede cambiar el estado activo"}), 403

    updated = update_user(user, data)
    return jsonify(updated.to_dict()), 200


@usuarios_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_role("admin")
def delete_user(user_id):
    """
    Desactiva un usuario (soft delete).
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
    responses:
      200:
        description: Usuario desactivado.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    deactivate_user(user)
    return jsonify({"message": f"Usuario {user.email} desactivado correctamente"}), 200


@usuarios_bp.route("/users/me", methods=["GET"])
@require_auth()
def get_me():
    """
    Perfil del usuario autenticado.
    ---
    tags: [Usuarios]
    security: [{Bearer: []}]
    responses:
      200:
        description: Perfil propio.
    """
    user = User.query.get(get_current_user_id())
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(user.to_dict()), 200
