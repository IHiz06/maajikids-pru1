from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from core.extensions import db
from core.security import require_role, require_auth, get_current_user_id, get_current_role
from apps.ia.models import AIRecommendation, ChatSession, ChatMessage
from apps.ia.schemas import GenerateRecommendationSchema, ChatSchema, VisibilitySchema
from apps.ia.services import generate_recommendation, regenerate_recommendation, chat_with_maaji

ia_bp = Blueprint("ia", __name__)


# ─── RECOMENDACIONES ──────────────────────────────────────────────────────────

@ia_bp.route("/ia/recommendations/generate", methods=["POST"])
@require_role("teacher", "admin")
def generate_recommendation_endpoint():
    """
    Dispara la IA (Gemini 2.5 Flash) para analizar una evaluación y generar recomendaciones.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [evaluation_id]
          properties:
            evaluation_id:
              type: integer
              description: ID de la evaluación a analizar.
    responses:
      201:
        description: Recomendación generada exitosamente.
      400:
        description: Ya existe una recomendación o error al llamar a Gemini.
      404:
        description: Evaluación no encontrada.
    """
    schema = GenerateRecommendationSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    current_role = get_current_role()
    current_id = get_current_user_id()

    # Teacher: can only generate for their own evaluations
    if current_role == "teacher":
        from apps.evaluaciones.models import Evaluation
        eval_ = Evaluation.query.get(data["evaluation_id"])
        if not eval_:
            return jsonify({"error": "Evaluación no encontrada"}), 404
        if eval_.teacher_id != current_id:
            return jsonify({"error": "Solo puedes generar recomendaciones para tus propias evaluaciones"}), 403

    try:
        recommendation = generate_recommendation(
            evaluation_id=data["evaluation_id"],
            generated_by=current_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(recommendation.to_dict()), 201


@ia_bp.route("/ia/recommendations/regenerate", methods=["POST"])
@require_role("teacher", "admin")
def regenerate_recommendation_endpoint():
    """
    Elimina la recomendación existente y genera una nueva con Gemini 2.5 Flash.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [evaluation_id]
          properties:
            evaluation_id: {type: integer}
    responses:
      201:
        description: Recomendación regenerada.
    """
    schema = GenerateRecommendationSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    current_role = get_current_role()
    current_id = get_current_user_id()

    if current_role == "teacher":
        from apps.evaluaciones.models import Evaluation
        eval_ = Evaluation.query.get(data["evaluation_id"])
        if not eval_:
            return jsonify({"error": "Evaluación no encontrada"}), 404
        if eval_.teacher_id != current_id:
            return jsonify({"error": "Acceso denegado"}), 403

    try:
        recommendation = regenerate_recommendation(
            evaluation_id=data["evaluation_id"],
            generated_by=current_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(recommendation.to_dict()), 201


@ia_bp.route("/ia/recommendations/<int:rec_id>", methods=["GET"])
@require_auth()
def get_recommendation(rec_id):
    """
    Detalle de una recomendación IA: resumen y lista de actividades por dominio.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: rec_id
        required: true
        type: integer
    responses:
      200:
        description: Recomendación con summary y activities agrupadas por área.
      403:
        description: Acceso denegado.
      404:
        description: Recomendación no encontrada.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    rec = AIRecommendation.query.get(rec_id)
    if not rec:
        return jsonify({"error": "Recomendación no encontrada"}), 404

    if current_role == "parent":
        from apps.ninos.models import Child
        child = Child.query.get(rec.child_id)
        if not child or child.parent_id != current_id:
            return jsonify({"error": "Acceso denegado"}), 403
        if not rec.is_visible_to_parent:
            return jsonify({"error": "Esta recomendación no está disponible"}), 403

    return jsonify(rec.to_dict()), 200


@ia_bp.route("/ia/recommendations/child/<int:child_id>", methods=["GET"])
@require_auth()
def recommendations_by_child(child_id):
    """
    Todas las recomendaciones IA de un niño, ordenadas por fecha desc.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    responses:
      200:
        description: Lista de recomendaciones del niño.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()

    from apps.ninos.models import Child
    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404

    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    q = AIRecommendation.query.filter_by(child_id=child_id)
    if current_role == "parent":
        q = q.filter_by(is_visible_to_parent=True)

    recs = q.order_by(AIRecommendation.generated_at.desc()).all()
    return jsonify({
        "child_id": child_id,
        "child_name": child.full_name,
        "recommendations": [r.to_dict() for r in recs],
        "total": len(recs),
    }), 200


@ia_bp.route("/ia/recommendations/<int:rec_id>/visibility", methods=["PATCH"])
@require_role("admin")
def toggle_visibility(rec_id):
    """
    Oculta o muestra una recomendación a los padres.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: rec_id
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [is_visible_to_parent]
          properties:
            is_visible_to_parent: {type: boolean}
    responses:
      200:
        description: Visibilidad actualizada.
    """
    rec = AIRecommendation.query.get(rec_id)
    if not rec:
        return jsonify({"error": "Recomendación no encontrada"}), 404

    schema = VisibilitySchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    rec.is_visible_to_parent = data["is_visible_to_parent"]
    db.session.commit()
    return jsonify({
        "message": f"Visibilidad actualizada: {'visible' if rec.is_visible_to_parent else 'oculta'}",
        "recommendation": rec.to_dict(),
    }), 200


@ia_bp.route("/ia/recommendations/", methods=["GET"])
@require_role("admin", "teacher")
def list_recommendations():
    """
    Lista todas las recomendaciones. Admin ve todas, Teacher solo las de sus talleres.
    ---
    tags: [IA - Recomendaciones]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: is_visible
        type: boolean
      - in: query
        name: page
        type: integer
    responses:
      200:
        description: Lista paginada.
    """
    current_role = get_current_role()
    current_id = get_current_user_id()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    is_visible = request.args.get("is_visible")

    q = AIRecommendation.query

    if current_role == "teacher":
        from apps.evaluaciones.models import Evaluation
        from apps.talleres.models import Workshop
        teacher_evals = db.session.query(Evaluation.id).join(Workshop).filter(
            Workshop.teacher_id == current_id
        )
        q = q.filter(AIRecommendation.evaluation_id.in_(teacher_evals))

    if is_visible is not None:
        q = q.filter(AIRecommendation.is_visible_to_parent == (is_visible.lower() == "true"))

    paginated = q.order_by(AIRecommendation.generated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "recommendations": [r.to_dict() for r in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


# ─── CHAT MAAJI ───────────────────────────────────────────────────────────────

@ia_bp.route("/ia/chat", methods=["POST"])
@require_role("parent")
def chat():
    """
    Envía un mensaje al asistente conversacional Maaji (Gemini 2.5 Flash).
    Mantiene historial multi-turno por sesión.
    ---
    tags: [IA - Chat Maaji]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [message]
          properties:
            message:
              type: string
              description: Mensaje del padre al asistente.
              maxLength: 2000
            session_id:
              type: integer
              description: ID de sesión existente (omitir para crear nueva sesión).
    responses:
      200:
        description: Respuesta del asistente Maaji.
      400:
        description: Error al comunicarse con Gemini.
    """
    schema = ChatSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "Datos inválidos", "details": e.messages}), 400

    parent_id = get_current_user_id()
    try:
        result = chat_with_maaji(
            parent_id=parent_id,
            message=data["message"],
            session_id=data.get("session_id"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result), 200


@ia_bp.route("/ia/sessions/", methods=["GET"])
@require_role("parent")
def list_sessions():
    """
    Lista sesiones de chat del padre autenticado, ordenadas por más reciente.
    ---
    tags: [IA - Chat Maaji]
    security: [{Bearer: []}]
    responses:
      200:
        description: Lista de sesiones de chat.
    """
    parent_id = get_current_user_id()
    sessions = (
        ChatSession.query
        .filter_by(parent_id=parent_id)
        .order_by(ChatSession.last_message_at.desc())
        .all()
    )
    return jsonify({
        "sessions": [s.to_dict() for s in sessions],
        "total": len(sessions),
    }), 200


@ia_bp.route("/ia/sessions/<int:session_id>/messages", methods=["GET"])
@require_role("parent")
def session_messages(session_id):
    """
    Historial de mensajes de una sesión de chat.
    ---
    tags: [IA - Chat Maaji]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: session_id
        required: true
        type: integer
    responses:
      200:
        description: Mensajes de la sesión.
      403:
        description: La sesión no pertenece a este padre.
      404:
        description: Sesión no encontrada.
    """
    parent_id = get_current_user_id()
    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({"error": "Sesión no encontrada"}), 404
    if session.parent_id != parent_id:
        return jsonify({"error": "Acceso denegado"}), 403

    messages = (
        ChatMessage.query
        .filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return jsonify({
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
        "total": len(messages),
    }), 200


@ia_bp.route("/ia/sessions/<int:session_id>", methods=["DELETE"])
@require_role("parent")
def delete_session(session_id):
    """
    Elimina una sesión de chat y todos sus mensajes.
    ---
    tags: [IA - Chat Maaji]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: session_id
        required: true
        type: integer
    responses:
      200:
        description: Sesión eliminada.
    """
    parent_id = get_current_user_id()
    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({"error": "Sesión no encontrada"}), 404
    if session.parent_id != parent_id:
        return jsonify({"error": "Acceso denegado"}), 403

    db.session.delete(session)  # cascade deletes messages
    db.session.commit()
    return jsonify({"message": "Sesión eliminada correctamente"}), 200
