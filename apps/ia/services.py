import json
from datetime import datetime
from flask import current_app
import google.generativeai as genai

from core.extensions import db
from apps.ia.models import AIRecommendation, ChatSession, ChatMessage
from apps.evaluaciones.models import Evaluation
from apps.ninos.models import Child
from apps.talleres.models import Workshop


def _configure_gemini():
    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
    return genai.GenerativeModel("gemini-2.5-flash")


# ─────────────────────────────────────────────
#  FUNCIÓN 1: Generación de recomendaciones IA
# ─────────────────────────────────────────────

def generate_recommendation(evaluation_id: int, generated_by: int) -> AIRecommendation:
    """Call Gemini to analyze evaluation and generate recommendations."""
    eval_ = Evaluation.query.get(evaluation_id)
    if not eval_:
        raise ValueError("Evaluación no encontrada")

    # Check not already generated
    existing = AIRecommendation.query.filter_by(evaluation_id=evaluation_id).first()
    if existing:
        raise ValueError("Ya existe una recomendación para esta evaluación. Usa regenerar.")

    child = Child.query.get(eval_.child_id)
    workshop = Workshop.query.get(eval_.workshop_id)

    # Build prompt
    prompt = f"""Eres un especialista en estimulación temprana y desarrollo infantil.

Analiza la siguiente evaluación de desarrollo de un niño y genera recomendaciones
específicas y prácticas para que los padres puedan apoyar el desarrollo en casa.

DATOS DEL NIÑO:
- Nombre: {child.full_name}
- Edad: {child.age_years} años ({child.age_months} meses)
- Taller: {workshop.title if workshop else 'No especificado'}

EVALUACIÓN DEL PROFESOR (escala 1-10):
- Lenguaje: {eval_.score_language}/10
- Motor: {eval_.score_motor}/10
- Social: {eval_.score_social}/10
- Cognitivo: {eval_.score_cognitive}/10

OBSERVACIONES DEL PROFESOR:
{eval_.observations or 'Sin observaciones adicionales.'}

INSTRUCCIONES:
1. Identifica los 2 dominios con puntaje más bajo (por debajo de 6).
2. Para cada dominio deficiente, sugiere 2-3 actividades prácticas y sencillas.
3. Si todos los puntajes son buenos (>=7), sugiere actividades de enriquecimiento.
4. Las actividades deben poder realizarse en casa sin materiales especializados.
5. El lenguaje debe ser claro, cálido y accesible para los padres (sin tecnicismos).

Responde ÚNICAMENTE en formato JSON con esta estructura exacta:
{{
  "summary": "Texto breve de 2-3 oraciones explicando el estado del niño...",
  "activities": [
    {{
      "area": "lenguaje",
      "title": "Nombre de la actividad",
      "description": "Descripción detallada para los padres..."
    }}
  ]
}}"""

    try:
        model = _configure_gemini()
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        raw_response = response.text

        parsed = json.loads(raw_response)
        summary = parsed.get("summary", "")
        activities = parsed.get("activities", [])

    except json.JSONDecodeError as e:
        # Save raw for audit, return error
        raise ValueError(f"Error al parsear respuesta de Gemini: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error al llamar a Gemini: {str(e)}")

    recommendation = AIRecommendation(
        evaluation_id=evaluation_id,
        child_id=eval_.child_id,
        generated_by=generated_by,
        summary=summary,
        activities=activities,
        raw_response=raw_response,
        is_visible_to_parent=True,
    )
    db.session.add(recommendation)

    eval_.ai_generated = True
    db.session.commit()

    return recommendation


def regenerate_recommendation(evaluation_id: int, generated_by: int) -> AIRecommendation:
    """Delete existing and regenerate."""
    existing = AIRecommendation.query.filter_by(evaluation_id=evaluation_id).first()
    if existing:
        db.session.delete(existing)
        eval_ = Evaluation.query.get(evaluation_id)
        if eval_:
            eval_.ai_generated = False
        db.session.commit()
    return generate_recommendation(evaluation_id, generated_by)


# ─────────────────────────────────────────────
#  FUNCIÓN 2: Chat Maaji (conversacional)
# ─────────────────────────────────────────────

_MAAJI_SYSTEM_PROMPT = """Eres 'Maaji', el asistente virtual del Centro MaajiKids. 
Eres amable, empático y especializado en desarrollo infantil temprano.
Tu objetivo es ayudar a los padres de familia a elegir el taller más adecuado
para su hijo/hija y a navegar el sistema de inscripciones.
Responde siempre en español, de forma clara y sin tecnicismos.
Si el padre quiere inscribir a su hijo, indícale que puede hacerlo desde la
sección 'Talleres' de la intranet.
NO tienes acceso a notas, evaluaciones, recomendaciones, datos médicos
ni información de pagos.
Sé conciso, cálido y útil. No inventes información que no tengas."""


def _build_maaji_context(parent_id: int) -> str:
    """Get active workshops and parent's children for context."""
    workshops = Workshop.query.filter_by(is_active=True).all()
    children = Child.query.filter_by(parent_id=parent_id, is_active=True).all()

    ctx_workshops = "\n".join([
        f"- {w.title} | Horario: {w.schedule} | Precio: S/.{w.price} | "
        f"Cupos disponibles: {w.available_spots}/{w.max_capacity}"
        for w in workshops
    ]) or "Sin talleres activos actualmente."

    ctx_children = "\n".join([
        f"- {c.full_name}, {c.age_years} años ({c.age_months} meses)"
        for c in children
    ]) or "Sin hijos registrados."

    return f"""
TALLERES ACTIVOS EN MAAJIKIDS:
{ctx_workshops}

HIJOS/AS DEL PADRE EN EL SISTEMA:
{ctx_children}
"""


def chat_with_maaji(parent_id: int, message: str, session_id: int = None) -> dict:
    """Send a message to Maaji assistant with full session history."""
    # Get or create session
    if session_id:
        session = ChatSession.query.filter_by(id=session_id, parent_id=parent_id).first()
        if not session:
            raise ValueError("Sesión no encontrada o no pertenece a este usuario")
    else:
        session = ChatSession(parent_id=parent_id)
        db.session.add(session)
        db.session.flush()

    # Get history
    history = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at).all()

    # Build Gemini conversation
    context = _build_maaji_context(parent_id)
    system_with_context = _MAAJI_SYSTEM_PROMPT + "\n\n" + context

    # Build history for Gemini multi-turn
    gemini_history = []
    for msg in history:
        role = "user" if msg.role == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg.content]})

    try:
        model = _configure_gemini()
        chat = model.start_chat(history=gemini_history)
        full_message = f"[Contexto del sistema]:\n{system_with_context}\n\n[Mensaje del padre]: {message}"
        if not gemini_history:
            response = chat.send_message(full_message)
        else:
            response = chat.send_message(message)
        assistant_reply = response.text
    except Exception as e:
        raise ValueError(f"Error al comunicarse con Maaji: {str(e)}")

    # Save messages
    user_msg = ChatMessage(session_id=session.id, role="user", content=message)
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=assistant_reply)
    db.session.add(user_msg)
    db.session.add(assistant_msg)

    # Update session timestamp
    session.last_message_at = datetime.utcnow()
    db.session.commit()

    return {
        "session_id": session.id,
        "reply": assistant_reply,
        "user_message": message,
    }
