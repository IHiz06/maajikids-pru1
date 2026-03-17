from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.talleres.models import Workshop
from apps.talleres.schemas import CreateWorkshopSchema, UpdateWorkshopSchema
from apps.talleres.services import (
    get_all_workshops, create_workshop, update_workshop, deactivate_workshop
)
from apps.ninos.models import Child
from apps.pagos.models import Enrollment, EnrollmentStatus
from apps.evaluaciones.models import Evaluation

talleres_bp = Blueprint("talleres", __name__)


@talleres_bp.route("/workshops/", methods=["GET"])
@require_auth()
def list_workshops():
    """
    Lista talleres. Padres/Secretaria ven solo activos. Admin/Teacher ven todos.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: only_active
        type: boolean
      - in: query
        name: teacher_id
        type: integer
    responses:
      200:
        description: Lista de talleres.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    only_active = True
    teacher_id_filter = None

    if current_role in ("admin", "secretary"):
        only_active_param = request.args.get("only_active", "true")
        only_active = only_active_param.lower() == "true"
    elif current_role == "teacher":
        only_active = False
        teacher_id_filter = current_id  # Teacher sees only their workshops

    workshops = get_all_workshops(only_active=only_active, teacher_id=teacher_id_filter)
    return jsonify([w.to_dict() for w in workshops]), 200


@talleres_bp.route("/workshops/", methods=["POST"])
@require_role("admin")
def create_workshop_endpoint():
    """
    Crea un nuevo taller. Soporta multipart/form-data para subir imagen.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    consumes: [multipart/form-data]
    parameters:
      - in: formData
        name: title
        required: true
        type: string
      - in: formData
        name: description
        type: string
      - in: formData
        name: teacher_id
        type: integer
      - in: formData
        name: schedule
        type: string
      - in: formData
        name: max_capacity
        required: true
        type: integer
      - in: formData
        name: price
        required: true
        type: number
      - in: formData
        name: image
        type: file
    responses:
      201:
        description: Taller creado.
    """
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_file = request.files.get("image")
    else:
        data = request.get_json(force=True) or {}
        image_file = None

    schema = CreateWorkshopSchema()
    try:
        validated = schema.load(data)
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400
    try:
        workshop = create_workshop(validated, image_file=image_file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(workshop.to_dict()), 201


@talleres_bp.route("/workshops/<int:workshop_id>", methods=["GET"])
@require_auth()
def get_workshop(workshop_id):
    """
    Detalle de un taller.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: workshop_id
        required: true
        type: integer
    responses:
      200:
        description: Detalle del taller.
      404:
        description: No encontrado.
    """
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404
    return jsonify(workshop.to_dict()), 200


@talleres_bp.route("/workshops/<int:workshop_id>", methods=["PATCH"])
@require_role("admin")
def update_workshop_endpoint(workshop_id):
    """
    Edita datos del taller. Soporta multipart para actualizar imagen.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    consumes: [multipart/form-data]
    parameters:
      - in: path
        name: workshop_id
        required: true
        type: integer
      - in: formData
        name: title
        type: string
      - in: formData
        name: description
        type: string
      - in: formData
        name: teacher_id
        type: integer
      - in: formData
        name: schedule
        type: string
      - in: formData
        name: max_capacity
        type: integer
      - in: formData
        name: price
        type: number
      - in: formData
        name: is_active
        type: boolean
      - in: formData
        name: image
        type: file
    responses:
      200:
        description: Taller actualizado.
    """
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404

    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_file = request.files.get("image")
    else:
        data = request.get_json(force=True) or {}
        image_file = None

    schema = UpdateWorkshopSchema()
    try:
        validated = schema.load(data)
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400
    try:
        updated = update_workshop(workshop, validated, image_file=image_file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(updated.to_dict()), 200


@talleres_bp.route("/workshops/<int:workshop_id>", methods=["DELETE"])
@require_role("admin")
def delete_workshop(workshop_id):
    """
    Desactiva un taller (soft delete).
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: workshop_id
        required: true
        type: integer
    responses:
      200:
        description: Taller desactivado.
    """
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404
    deactivate_workshop(workshop)
    return jsonify({"message": f"Taller '{workshop.title}' desactivado"}), 200


@talleres_bp.route("/workshops/<int:workshop_id>/children", methods=["GET"])
@require_role("admin", "teacher", "secretary")
def workshop_children(workshop_id):
    """
    Lista niños inscritos en el taller.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: workshop_id
        required: true
        type: integer
    responses:
      200:
        description: Niños inscritos.
    """
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404

    current_role = get_current_role()
    current_id = get_current_user_id()
    if current_role == "teacher" and workshop.teacher_id != current_id:
        return jsonify({"error": "Solo puedes ver los niños de tus talleres"}), 403

    enrollments = (
        Enrollment.query
        .filter_by(workshop_id=workshop_id, status=EnrollmentStatus.active)
        .all()
    )
    children = []
    for e in enrollments:
        c = e.child
        children.append({
            "child_id": c.id,
            "full_name": c.full_name,
            "age_years": c.age_years,
            "age_months": c.age_months,
            "gender": c.gender,
            "photo_url": c.photo_url,
            "parent_name": f"{c.parent.first_name} {c.parent.last_name}" if c.parent else None,
            "enrollment_id": e.id,
            "enrolled_at": e.enrolled_at.isoformat(),
        })
    return jsonify({"workshop": workshop.title, "children": children, "total": len(children)}), 200


@talleres_bp.route("/workshops/<int:workshop_id>/evaluations", methods=["GET"])
@require_role("admin", "teacher")
def workshop_evaluations(workshop_id):
    """
    Lista evaluaciones del taller.
    ---
    tags: [Talleres]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: workshop_id
        required: true
        type: integer
    responses:
      200:
        description: Evaluaciones del taller.
    """
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404

    current_role = get_current_role()
    current_id = get_current_user_id()
    if current_role == "teacher" and workshop.teacher_id != current_id:
        return jsonify({"error": "Solo puedes ver las evaluaciones de tus talleres"}), 403

    evals = (
        Evaluation.query
        .filter_by(workshop_id=workshop_id)
        .order_by(Evaluation.evaluation_date.desc())
        .all()
    )
    return jsonify({"workshop": workshop.title, "evaluations": [e.to_dict() for e in evals]}), 200


talleres_bp.route("/workshops/<int:workshop_id>/image", methods=["DELETE"])
@require_role("admin")
def delete_workshop_image(workshop_id):
    """Remove taller image from Cloudinary and DB."""
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({"error": "Taller no encontrado"}), 404
    if workshop.image_url:
        from core.security import delete_image_from_cloudinary
        delete_image_from_cloudinary(workshop.image_url)
        workshop.image_url = None
        db.session.commit()
    return jsonify({"message": "Imagen eliminada"}), 200
