from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.ninos.models import Child
from apps.ninos.schemas import CreateChildSchema, UpdateChildSchema
from apps.ninos.services import create_child, update_child, decrypt_child_sensitive
from apps.pagos.models import Enrollment, EnrollmentStatus
from apps.evaluaciones.models import Evaluation
from apps.ia.models import AIRecommendation

ninos_bp = Blueprint("ninos", __name__)


@ninos_bp.route("/children/", methods=["GET"])
@require_role("admin", "teacher", "secretary")
def list_children():
    """
    Lista niños. Teacher solo ve los de sus talleres. Admin/Secretaria ven todos.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
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
        description: Lista de niños.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    is_active = request.args.get("is_active")

    if current_role == "teacher":
        # Teacher: only children enrolled in their workshops
        from apps.talleres.models import Workshop
        from apps.pagos.models import Enrollment, EnrollmentStatus
        teacher_workshop_ids = [w.id for w in Workshop.query.filter_by(teacher_id=current_id).all()]
        child_ids = db.session.query(Enrollment.child_id).filter(
            Enrollment.workshop_id.in_(teacher_workshop_ids),
            Enrollment.status == EnrollmentStatus.active
        ).distinct()
        q = Child.query.filter(Child.id.in_(child_ids))
    else:
        q = Child.query

    if is_active is not None:
        q = q.filter(Child.is_active == (is_active.lower() == "true"))

    paginated = q.order_by(Child.full_name).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "children": [c.to_dict() for c in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


@ninos_bp.route("/children/", methods=["POST"])
@require_auth()
def create_child_endpoint():
    """
    Crea perfil de niño. Soporta multipart para foto.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    consumes: [multipart/form-data]
    parameters:
      - in: formData
        name: full_name
        required: true
        type: string
      - in: formData
        name: date_of_birth
        required: true
        type: string
        format: date
        description: YYYY-MM-DD. Máximo 6 años de edad.
      - in: formData
        name: gender
        required: true
        type: string
        enum: [M, F, otro]
      - in: formData
        name: medical_info
        type: string
        description: Se cifra con AES-256.
      - in: formData
        name: allergies
        type: string
        description: Se cifra con AES-256.
      - in: formData
        name: emergency_contact
        type: string
      - in: formData
        name: photo
        type: file
    responses:
      201:
        description: Niño registrado.
      400:
        description: Error de validación.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    if current_role not in ("admin", "secretary", "parent"):
        return jsonify({"error": "Sin permisos para crear perfiles de niños"}), 403

    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_file = request.files.get("photo")
    else:
        data = request.get_json(force=True) or {}
        image_file = None

    # Parent ID: parent uses their own, admin/secretary can specify
    if current_role == "parent":
        parent_id = current_id
    else:
        parent_id = int(data.pop("parent_id", current_id))

    schema = CreateChildSchema()
    try:
        validated = schema.load(data)
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    try:
        child = create_child(validated, parent_id=parent_id, image_file=image_file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(child.to_dict()), 201


@ninos_bp.route("/children/<int:child_id>", methods=["GET"])
@require_auth()
def get_child(child_id):
    """
    Detalle del niño. Incluye datos médicos descifrados para admin/teacher/parent propio.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    responses:
      200:
        description: Perfil del niño con datos sensibles descifrados.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404

    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403
    if current_role == "teacher":
        # Check teacher has this child in one of their workshops
        from apps.talleres.models import Workshop
        teacher_workshop_ids = [w.id for w in Workshop.query.filter_by(teacher_id=current_id).all()]
        enrolled = Enrollment.query.filter(
            Enrollment.child_id == child_id,
            Enrollment.workshop_id.in_(teacher_workshop_ids)
        ).first()
        if not enrolled:
            return jsonify({"error": "Este niño no está en tus talleres"}), 403

    data = decrypt_child_sensitive(child)
    return jsonify(data), 200


@ninos_bp.route("/children/<int:child_id>", methods=["PATCH"])
@require_auth()
def update_child_endpoint(child_id):
    """
    Actualiza datos del niño. Soporta multipart para foto.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    consumes: [multipart/form-data]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
      - in: formData
        name: full_name
        type: string
      - in: formData
        name: date_of_birth
        type: string
        format: date
      - in: formData
        name: gender
        type: string
        enum: [M, F, otro]
      - in: formData
        name: medical_info
        type: string
      - in: formData
        name: allergies
        type: string
      - in: formData
        name: emergency_contact
        type: string
      - in: formData
        name: photo
        type: file
    responses:
      200:
        description: Niño actualizado.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404

    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403
    if current_role not in ("admin", "parent"):
        return jsonify({"error": "Acceso denegado"}), 403

    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_file = request.files.get("photo")
    else:
        data = request.get_json(force=True) or {}
        image_file = None

    schema = UpdateChildSchema()
    try:
        validated = schema.load(data)
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    try:
        updated = update_child(child, validated, image_file=image_file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(decrypt_child_sensitive(updated)), 200


@ninos_bp.route("/children/<int:child_id>/enrollments", methods=["GET"])
@require_auth()
def child_enrollments(child_id):
    """
    Talleres en los que está inscrito el niño.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    responses:
      200:
        description: Inscripciones activas del niño.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404
    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    enrollments = Enrollment.query.filter_by(child_id=child_id).all()
    return jsonify([e.to_dict() for e in enrollments]), 200


@ninos_bp.route("/children/<int:child_id>/evaluations", methods=["GET"])
@require_auth()
def child_evaluations(child_id):
    """
    Historial de evaluaciones del niño.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    responses:
      200:
        description: Evaluaciones del niño.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404
    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    evals = (
        Evaluation.query
        .filter_by(child_id=child_id)
        .order_by(Evaluation.evaluation_date.desc())
        .all()
    )
    return jsonify([e.to_dict() for e in evals]), 200


@ninos_bp.route("/children/<int:child_id>/recommendations", methods=["GET"])
@require_auth()
def child_recommendations(child_id):
    """
    Recomendaciones IA generadas para el niño.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    responses:
      200:
        description: Recomendaciones del niño.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404
    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    q = AIRecommendation.query.filter_by(child_id=child_id)
    if current_role == "parent":
        q = q.filter_by(is_visible_to_parent=True)
    recs = q.order_by(AIRecommendation.generated_at.desc()).all()
    return jsonify([r.to_dict() for r in recs]), 200


@ninos_bp.route("/parent/<int:parent_id>/children", methods=["GET"])
@require_auth()
def parent_children(parent_id):
    """
    Todos los hijos registrados por un padre/madre.
    ---
    tags: [Niños]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: parent_id
        required: true
        type: integer
    responses:
      200:
        description: Hijos del padre.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    if current_role == "parent" and current_id != parent_id:
        return jsonify({"error": "Acceso denegado"}), 403

    children = Child.query.filter_by(parent_id=parent_id, is_active=True).all()
    return jsonify([c.to_dict() for c in children]), 200
