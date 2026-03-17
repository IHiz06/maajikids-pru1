from datetime import datetime
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.contacto.models import ContactMessage
from apps.contacto.schemas import CreateContactMessageSchema, UpdateContactStatusSchema, ReplyContactSchema

contacto_bp = Blueprint("contacto", __name__)


@contacto_bp.route("/contact/", methods=["POST"])
def send_message():
    """
    Envía un mensaje de consulta al centro.
    Puede ser usado con o sin autenticación JWT.
    Si no está autenticado, debe proveer sender_name y sender_email.
    ---
    tags: [Contacto]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [sender_name, sender_email, subject, body]
          properties:
            sender_name: {type: string}
            sender_email: {type: string}
            subject: {type: string}
            body: {type: string}
    responses:
      201:
        description: Mensaje enviado correctamente.
      400:
        description: Datos inválidos.
    """
    # Optional auth - get user if authenticated
    sender_id = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            sender_id = int(identity)
    except Exception:
        pass

    schema = CreateContactMessageSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    # If authenticated, fill name/email from profile if not provided
    if sender_id and not data.get("sender_name"):
        from apps.usuarios.models import User
        user = User.query.get(sender_id)
        if user:
            data["sender_name"] = f"{user.first_name} {user.last_name}"
            data["sender_email"] = user.email

    message = ContactMessage(
        sender_id=sender_id,
        sender_name=data["sender_name"],
        sender_email=data["sender_email"],
        subject=data["subject"],
        body=data["body"],
        status="unread",
    )
    db.session.add(message)
    db.session.commit()
    return jsonify({"message": "Mensaje enviado. Te contactaremos pronto.", "id": message.id}), 201


@contacto_bp.route("/contact/", methods=["GET"])
@require_role("admin", "secretary")
def list_messages():
    """
    Lista todos los mensajes de contacto.
    ---
    tags: [Contacto]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: status
        type: string
        enum: [unread, read, replied]
      - in: query
        name: page
        type: integer
      - in: query
        name: per_page
        type: integer
    responses:
      200:
        description: Lista de mensajes.
    """
    status_filter = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    q = ContactMessage.query
    if status_filter:
        q = q.filter(ContactMessage.status == status_filter)

    paginated = q.order_by(ContactMessage.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "messages": [m.to_dict() for m in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
        "unread_count": ContactMessage.query.filter_by(status="unread").count(),
    }), 200


@contacto_bp.route("/contact/<int:message_id>", methods=["GET"])
@require_role("admin", "secretary")
def get_message(message_id):
    """
    Detalle de un mensaje de contacto.
    ---
    tags: [Contacto]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: message_id
        required: true
        type: integer
    responses:
      200:
        description: Mensaje completo.
    """
    message = ContactMessage.query.get(message_id)
    if not message:
        return jsonify({"error": "Mensaje no encontrado"}), 404
    # Mark as read automatically
    if message.status == "unread":
        message.status = "read"
        db.session.commit()
    return jsonify(message.to_dict()), 200


@contacto_bp.route("/contact/<int:message_id>/status", methods=["PATCH"])
@require_role("admin", "secretary")
def update_message_status(message_id):
    """
    Cambia el estado de un mensaje (read | replied).
    ---
    tags: [Contacto]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: message_id
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [status]
          properties:
            status:
              type: string
              enum: [read, replied]
    responses:
      200:
        description: Estado actualizado.
    """
    message = ContactMessage.query.get(message_id)
    if not message:
        return jsonify({"error": "Mensaje no encontrado"}), 404

    schema = UpdateContactStatusSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    message.status = data["status"]
    db.session.commit()
    return jsonify(message.to_dict()), 200


@contacto_bp.route("/contact/<int:message_id>/reply", methods=["POST"])
@require_role("admin", "secretary")
def reply_message(message_id):
    """
    Admin/Secretaria responde un mensaje desde el sistema web.
    Guarda la respuesta en BD y marca como 'replied'.
    ---
    tags: [Contacto]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: message_id
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [reply_body]
          properties:
            reply_body:
              type: string
              description: Texto de la respuesta al padre/madre.
    responses:
      200:
        description: Respuesta guardada y mensaje marcado como respondido.
    """
    message = ContactMessage.query.get(message_id)
    if not message:
        return jsonify({"error": "Mensaje no encontrado"}), 404

    schema = ReplyContactSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    current_id = get_current_user_id()
    message.reply_body = data["reply_body"]
    message.replied_by_id = current_id
    message.replied_at = datetime.utcnow()
    message.status = "replied"
    db.session.commit()

    return jsonify({
        "message": "Respuesta registrada correctamente",
        "contact_message": message.to_dict(),
    }), 200


@contacto_bp.route("/contact/<int:message_id>", methods=["DELETE"])
@require_role("admin")
def delete_message(message_id):
    """
    Elimina un mensaje de contacto (solo admin).
    ---
    tags: [Contacto]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: message_id
        required: true
        type: integer
    responses:
      200:
        description: Mensaje eliminado.
    """
    message = ContactMessage.query.get(message_id)
    if not message:
        return jsonify({"error": "Mensaje no encontrado"}), 404
    db.session.delete(message)
    db.session.commit()
    return jsonify({"message": "Mensaje eliminado"}), 200
