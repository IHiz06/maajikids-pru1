from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.evaluaciones.models import Evaluation
from apps.evaluaciones.schemas import CreateEvaluationSchema, UpdateEvaluationSchema
from apps.evaluaciones.services import create_evaluation, update_evaluation

evaluaciones_bp = Blueprint("evaluaciones", __name__)


@evaluaciones_bp.route("/evaluations/", methods=["POST"])
@require_role("teacher", "admin")
def create_evaluation_endpoint():
    """
    Registra una evaluación de un niño. Teacher solo puede evaluar en sus talleres.
    ---
    tags: [Evaluaciones]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [child_id, workshop_id, evaluation_date, score_language, score_motor, score_social, score_cognitive]
          properties:
            child_id: {type: integer}
            workshop_id: {type: integer}
            evaluation_date: {type: string, format: date}
            score_language: {type: integer, minimum: 1, maximum: 10}
            score_motor: {type: integer, minimum: 1, maximum: 10}
            score_social: {type: integer, minimum: 1, maximum: 10}
            score_cognitive: {type: integer, minimum: 1, maximum: 10}
            observations: {type: string}
    responses:
      201:
        description: Evaluación registrada.
    """
    schema = CreateEvaluationSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    current_role = get_current_role()
    current_id = get_current_user_id()

    try:
        if current_role == "teacher":
            eval_ = create_evaluation(data, teacher_id=current_id)
        else:
            # Admin can evaluate on behalf of any teacher — use workshop's teacher or admin as author
            from apps.talleres.models import Workshop
            workshop = Workshop.query.get(data["workshop_id"])
            teacher_id = workshop.teacher_id if workshop and workshop.teacher_id else current_id
            # Admin bypass: skip enrollment check
            from apps.evaluaciones.models import Evaluation
            eval_ = Evaluation(
                child_id=data["child_id"],
                teacher_id=teacher_id,
                workshop_id=data["workshop_id"],
                evaluation_date=data["evaluation_date"],
                score_language=data["score_language"],
                score_motor=data["score_motor"],
                score_social=data["score_social"],
                score_cognitive=data["score_cognitive"],
                observations=data.get("observations"),
            )
            db.session.add(eval_)
            db.session.commit()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(eval_.to_dict()), 201


@evaluaciones_bp.route("/evaluations/<int:eval_id>", methods=["GET"])
@require_auth()
def get_evaluation(eval_id):
    """
    Detalle completo de una evaluación.
    ---
    tags: [Evaluaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: eval_id
        required: true
        type: integer
    responses:
      200:
        description: Evaluación completa con puntajes y observaciones.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    eval_ = Evaluation.query.get(eval_id)
    if not eval_:
        return jsonify({"error": "Evaluación no encontrada"}), 404

    if current_role == "parent":
        from apps.ninos.models import Child
        child = Child.query.get(eval_.child_id)
        if not child or child.parent_id != current_id:
            return jsonify({"error": "Acceso denegado"}), 403
    elif current_role == "teacher" and eval_.teacher_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    return jsonify(eval_.to_dict()), 200


@evaluaciones_bp.route("/evaluations/<int:eval_id>", methods=["PATCH"])
@require_role("teacher", "admin")
def update_evaluation_endpoint(eval_id):
    """
    Edita puntajes u observaciones de una evaluación.
    ---
    tags: [Evaluaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: eval_id
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            evaluation_date: {type: string, format: date}
            score_language: {type: integer, minimum: 1, maximum: 10}
            score_motor: {type: integer, minimum: 1, maximum: 10}
            score_social: {type: integer, minimum: 1, maximum: 10}
            score_cognitive: {type: integer, minimum: 1, maximum: 10}
            observations: {type: string}
    responses:
      200:
        description: Evaluación actualizada.
    """
    eval_ = Evaluation.query.get(eval_id)
    if not eval_:
        return jsonify({"error": "Evaluación no encontrada"}), 404

    current_role = get_current_role()
    current_id = get_current_user_id()
    if current_role == "teacher" and eval_.teacher_id != current_id:
        return jsonify({"error": "Solo puedes editar tus propias evaluaciones"}), 403

    schema = UpdateEvaluationSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    updated = update_evaluation(eval_, data)
    return jsonify(updated.to_dict()), 200


@evaluaciones_bp.route("/evaluations/<int:eval_id>", methods=["DELETE"])
@require_role("admin")
def delete_evaluation(eval_id):
    """
    Elimina una evaluación (solo admin, acción irreversible).
    ---
    tags: [Evaluaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: eval_id
        required: true
        type: integer
    responses:
      200:
        description: Evaluación eliminada.
    """
    eval_ = Evaluation.query.get(eval_id)
    if not eval_:
        return jsonify({"error": "Evaluación no encontrada"}), 404
    db.session.delete(eval_)
    db.session.commit()
    return jsonify({"message": "Evaluación eliminada correctamente"}), 200


@evaluaciones_bp.route("/evaluations/", methods=["GET"])
@require_role("admin", "teacher", "secretary")
def list_evaluations():
    """
    Lista evaluaciones con filtros.
    ---
    tags: [Evaluaciones]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: workshop_id
        type: integer
      - in: query
        name: child_id
        type: integer
      - in: query
        name: page
        type: integer
    responses:
      200:
        description: Evaluaciones filtradas.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    q = Evaluation.query
    if current_role == "teacher":
        q = q.filter(Evaluation.teacher_id == current_id)

    workshop_id = request.args.get("workshop_id")
    child_id = request.args.get("child_id")
    if workshop_id:
        q = q.filter(Evaluation.workshop_id == int(workshop_id))
    if child_id:
        q = q.filter(Evaluation.child_id == int(child_id))

    paginated = q.order_by(Evaluation.evaluation_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "evaluations": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200
