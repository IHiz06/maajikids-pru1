from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.pagos.models import Payment, Enrollment, PaymentStatus, EnrollmentStatus
from apps.pagos.schemas import CreatePreferenceSchema, UpdateEnrollmentSchema
from apps.pagos.services import create_mp_preference, process_webhook

pagos_bp = Blueprint("pagos", __name__)


@pagos_bp.route("/payments/create-preference", methods=["POST"])
@require_role("parent")
def create_preference():
    """
    Genera preferencia de pago en MercadoPago y retorna URL de pago.
    ---
    tags: [Pagos]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [workshop_id, child_id]
          properties:
            workshop_id: {type: integer}
            child_id: {type: integer}
    responses:
      201:
        description: Preferencia creada. Retorna init_point URL.
      400:
        description: Sin cupo, ya inscrito, o error de validación.
    """
    schema = CreatePreferenceSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    try:
        result = create_mp_preference(
            parent_id=get_current_user_id(),
            workshop_id=data["workshop_id"],
            child_id=data["child_id"],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result), 201


@pagos_bp.route("/payments/webhook", methods=["POST"])
def mp_webhook():
    """
    Webhook de MercadoPago. Verifica y procesa notificaciones de pago.
    ---
    tags: [Pagos]
    parameters:
      - in: body
        name: body
        schema:
          type: object
    responses:
      200:
        description: Webhook procesado.
    """
    payload = request.get_json(force=True, silent=True) or {}
    signature = request.headers.get("X-Signature", "")
    try:
        process_webhook(payload, signature)
    except Exception as e:
        # Always return 200 to MP to avoid retries on logic errors
        return jsonify({"status": "error", "detail": str(e)}), 200
    return jsonify({"status": "ok"}), 200


@pagos_bp.route("/payments/", methods=["GET"])
@require_role("admin", "secretary")
def list_payments():
    """
    Lista todos los pagos del sistema.
    ---
    tags: [Pagos]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: status
        type: string
        enum: [pending, approved, rejected, cancelled]
      - in: query
        name: page
        type: integer
      - in: query
        name: per_page
        type: integer
    responses:
      200:
        description: Lista paginada de pagos.
    """
    status_filter = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    q = Payment.query
    if status_filter:
        try:
            q = q.filter(Payment.status == PaymentStatus[status_filter])
        except KeyError:
            return jsonify({"error": "Estado inválido"}), 400

    paginated = q.order_by(Payment.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "payments": [p.to_dict() for p in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


@pagos_bp.route("/payments/overdue", methods=["GET"])
@require_role("admin", "secretary")
def overdue_payments():
    """
    Pagos pendientes o rechazados para seguimiento.
    ---
    tags: [Pagos]
    security: [{Bearer: []}]
    responses:
      200:
        description: Pagos con atención requerida.
    """
    payments = Payment.query.filter(
        Payment.status.in_([PaymentStatus.pending, PaymentStatus.rejected])
    ).order_by(Payment.created_at.asc()).all()
    return jsonify({"payments": [p.to_dict() for p in payments], "total": len(payments)}), 200


@pagos_bp.route("/payments/parent/<int:parent_id>", methods=["GET"])
@require_auth()
def parent_payments(parent_id):
    """
    Historial de pagos de un padre/madre.
    ---
    tags: [Pagos]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: parent_id
        required: true
        type: integer
    responses:
      200:
        description: Pagos del padre.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    if current_role == "parent" and current_id != parent_id:
        return jsonify({"error": "Acceso denegado"}), 403

    payments = Payment.query.filter_by(parent_id=parent_id).order_by(Payment.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payments]), 200


@pagos_bp.route("/payments/<int:payment_id>", methods=["GET"])
@require_auth()
def get_payment(payment_id):
    """
    Detalle de un pago específico.
    ---
    tags: [Pagos]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: payment_id
        required: true
        type: integer
    responses:
      200:
        description: Detalle del pago.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "Pago no encontrado"}), 404
    if current_role == "parent" and payment.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403
    return jsonify(payment.to_dict()), 200


# ─── ENROLLMENTS ─────────────────────────────────────────────────────────────

@pagos_bp.route("/enrollments/", methods=["GET"])
@require_role("admin", "secretary")
def list_enrollments():
    """
    Lista todas las inscripciones del sistema.
    ---
    tags: [Inscripciones]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: status
        type: string
        enum: [active, completed, cancelled]
      - in: query
        name: workshop_id
        type: integer
      - in: query
        name: page
        type: integer
      - in: query
        name: per_page
        type: integer
    responses:
      200:
        description: Lista de inscripciones.
    """
    status_filter = request.args.get("status")
    workshop_filter = request.args.get("workshop_id")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    q = Enrollment.query
    if status_filter:
        try:
            q = q.filter(Enrollment.status == EnrollmentStatus[status_filter])
        except KeyError:
            return jsonify({"error": "Estado inválido"}), 400
    if workshop_filter:
        q = q.filter(Enrollment.workshop_id == int(workshop_filter))

    paginated = q.order_by(Enrollment.enrolled_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "enrollments": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


@pagos_bp.route("/enrollments/<int:enrollment_id>", methods=["PATCH"])
@require_role("admin")
def update_enrollment(enrollment_id):
    """
    Cambia el estado de una inscripción (solo admin).
    ---
    tags: [Inscripciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: enrollment_id
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
              enum: [active, completed, cancelled]
    responses:
      200:
        description: Inscripción actualizada.
    """
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return jsonify({"error": "Inscripción no encontrada"}), 404

    schema = UpdateEnrollmentSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    old_status = enrollment.status
    new_status = EnrollmentStatus[data["status"]]
    enrollment.status = new_status

    # Adjust workshop counter
    workshop = enrollment.workshop
    if old_status == EnrollmentStatus.active and new_status == EnrollmentStatus.cancelled:
        workshop.current_enrolled = max(0, workshop.current_enrolled - 1)
    elif old_status == EnrollmentStatus.cancelled and new_status == EnrollmentStatus.active:
        if not workshop.is_full:
            workshop.current_enrolled += 1

    db.session.commit()
    return jsonify(enrollment.to_dict()), 200
