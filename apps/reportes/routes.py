from flask import Blueprint, request, jsonify, make_response
from core.security import require_role, get_current_user_id, get_current_role
from core.extensions import db

reportes_bp = Blueprint("reportes", __name__)


def _pdf_response(pdf_bytes: bytes, filename: str):
    """Wrap bytes as a PDF download response."""
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    response.headers["Content-Length"] = len(pdf_bytes)
    return response


# ─── Reporte 1: Evaluación individual + recomendaciones ──────────────────────

@reportes_bp.route("/reports/evaluation/<int:eval_id>", methods=["GET"])
@require_role("admin", "teacher", "parent")
def report_evaluation(eval_id):
    """
    PDF de una evaluación individual con recomendaciones IA (si existen).
    Logo de MaajiKids incluido.
    ---
    tags: [Reportes PDF]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: eval_id
        required: true
        type: integer
    produces: [application/pdf]
    responses:
      200:
        description: PDF del reporte de evaluación.
      403:
        description: Sin permisos.
      404:
        description: Evaluación no encontrada.
    """
    from apps.evaluaciones.models import Evaluation
    from apps.ia.models import AIRecommendation
    from apps.ninos.models import Child

    current_role = get_current_role()
    current_id = get_current_user_id()

    eval_ = Evaluation.query.get(eval_id)
    if not eval_:
        return jsonify({"error": "Evaluación no encontrada"}), 404

    # Access control
    if current_role == "parent":
        child = Child.query.get(eval_.child_id)
        if not child or child.parent_id != current_id:
            return jsonify({"error": "Acceso denegado"}), 403
    elif current_role == "teacher" and eval_.teacher_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403

    recommendation = AIRecommendation.query.filter_by(evaluation_id=eval_id).first()

    from apps.reportes.pdf_builder import build_evaluation_pdf
    pdf_bytes = build_evaluation_pdf(eval_, recommendation)
    filename = f"evaluacion_{eval_id}_{eval_.child.full_name.replace(' ', '_')}.pdf"
    return _pdf_response(pdf_bytes, filename)


# ─── Reporte 2: Historial de pagos ───────────────────────────────────────────

@reportes_bp.route("/reports/payments", methods=["GET"])
@require_role("admin", "secretary")
def report_payments():
    """
    PDF con historial completo de pagos del sistema (con filtros).
    ---
    tags: [Reportes PDF]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: status
        type: string
        enum: [pending, approved, rejected, cancelled]
      - in: query
        name: parent_id
        type: integer
    produces: [application/pdf]
    responses:
      200:
        description: PDF con historial de pagos.
    """
    from apps.pagos.models import Payment, PaymentStatus

    q = Payment.query
    status_filter = request.args.get("status")
    parent_id = request.args.get("parent_id")

    if status_filter:
        try:
            q = q.filter(Payment.status == PaymentStatus[status_filter])
        except KeyError:
            return jsonify({"error": "Estado inválido"}), 400
    if parent_id:
        q = q.filter(Payment.parent_id == int(parent_id))

    payments = q.order_by(Payment.created_at.desc()).all()
    if not payments:
        return jsonify({"error": "No hay pagos para generar el reporte"}), 404

    from apps.reportes.pdf_builder import build_payments_pdf
    pdf_bytes = build_payments_pdf(payments, title="Reporte de Pagos — MaajiKids")
    return _pdf_response(pdf_bytes, "reporte_pagos.pdf")


# ─── Reporte 3: Inscripciones ────────────────────────────────────────────────

@reportes_bp.route("/reports/enrollments", methods=["GET"])
@require_role("admin", "secretary")
def report_enrollments():
    """
    PDF con listado de inscripciones, con filtro opcional por taller.
    ---
    tags: [Reportes PDF]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: workshop_id
        type: integer
      - in: query
        name: status
        type: string
        enum: [active, completed, cancelled]
    produces: [application/pdf]
    responses:
      200:
        description: PDF de inscripciones.
    """
    from apps.pagos.models import Enrollment, EnrollmentStatus
    from apps.talleres.models import Workshop

    q = Enrollment.query
    workshop_id = request.args.get("workshop_id")
    status_filter = request.args.get("status")
    workshop_title = None

    if workshop_id:
        q = q.filter(Enrollment.workshop_id == int(workshop_id))
        ws = Workshop.query.get(int(workshop_id))
        workshop_title = ws.title if ws else None
    if status_filter:
        try:
            q = q.filter(Enrollment.status == EnrollmentStatus[status_filter])
        except KeyError:
            return jsonify({"error": "Estado inválido"}), 400

    enrollments = q.order_by(Enrollment.enrolled_at.desc()).all()
    if not enrollments:
        return jsonify({"error": "No hay inscripciones para el reporte"}), 404

    from apps.reportes.pdf_builder import build_enrollments_pdf
    pdf_bytes = build_enrollments_pdf(enrollments, workshop_title=workshop_title)
    return _pdf_response(pdf_bytes, "reporte_inscripciones.pdf")


# ─── Reporte 4: Expediente completo de niño ──────────────────────────────────

@reportes_bp.route("/reports/child/<int:child_id>", methods=["GET"])
@require_role("admin", "teacher", "parent")
def report_child(child_id):
    """
    PDF con expediente completo del niño: datos, todas las evaluaciones y recomendaciones IA.
    ---
    tags: [Reportes PDF]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: child_id
        required: true
        type: integer
    produces: [application/pdf]
    responses:
      200:
        description: PDF expediente del niño.
    """
    from apps.ninos.models import Child
    from apps.evaluaciones.models import Evaluation
    from apps.ia.models import AIRecommendation

    current_role = get_current_role()
    current_id = get_current_user_id()

    child = Child.query.get(child_id)
    if not child:
        return jsonify({"error": "Niño no encontrado"}), 404

    if current_role == "parent" and child.parent_id != current_id:
        return jsonify({"error": "Acceso denegado"}), 403
    if current_role == "teacher":
        from apps.talleres.models import Workshop
        from apps.pagos.models import Enrollment, EnrollmentStatus
        teacher_ws = [w.id for w in Workshop.query.filter_by(teacher_id=current_id).all()]
        enrolled = Enrollment.query.filter(
            Enrollment.child_id == child_id,
            Enrollment.workshop_id.in_(teacher_ws)
        ).first()
        if not enrolled:
            return jsonify({"error": "Este niño no está en tus talleres"}), 403

    evaluations = (
        Evaluation.query.filter_by(child_id=child_id)
        .order_by(Evaluation.evaluation_date.desc()).all()
    )
    recs_q = AIRecommendation.query.filter_by(child_id=child_id)
    if current_role == "parent":
        recs_q = recs_q.filter_by(is_visible_to_parent=True)
    recommendations = recs_q.order_by(AIRecommendation.generated_at.desc()).all()

    from apps.reportes.pdf_builder import build_child_full_report_pdf
    pdf_bytes = build_child_full_report_pdf(child, evaluations, recommendations)
    filename = f"expediente_{child.full_name.replace(' ', '_')}.pdf"
    return _pdf_response(pdf_bytes, filename)


# ─── Reporte 5: Dashboard estadístico ────────────────────────────────────────

@reportes_bp.route("/reports/dashboard", methods=["GET"])
@require_role("admin")
def report_dashboard():
    """
    PDF resumen general del centro: usuarios, talleres, inscripciones y pagos.
    ---
    tags: [Reportes PDF]
    security: [{Bearer: []}]
    produces: [application/pdf]
    responses:
      200:
        description: PDF resumen del centro.
    """
    from apps.reportes.pdf_builder import (
        build_payments_pdf, _build_header, _build_footer_note,
        _section_banner, _info_table, PINK, TEAL, LIGHT_GRAY, WHITE, DARK_GRAY,
    )
    from apps.usuarios.models import User, RoleEnum
    from apps.talleres.models import Workshop
    from apps.pagos.models import Payment, Enrollment, PaymentStatus, EnrollmentStatus
    from apps.ninos.models import Child
    from apps.evaluaciones.models import Evaluation
    from apps.ia.models import AIRecommendation
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from apps.reportes.pdf_builder import _get_styles

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = _get_styles()
    elements = _build_header(styles, "Resumen General del Centro")

    # Stats
    total_parents = User.query.filter_by(role=RoleEnum.parent, is_active=True).count()
    total_teachers = User.query.filter_by(role=RoleEnum.teacher, is_active=True).count()
    total_children = Child.query.filter_by(is_active=True).count()
    total_workshops = Workshop.query.filter_by(is_active=True).count()
    total_active_enrollments = Enrollment.query.filter_by(status=EnrollmentStatus.active).count()
    total_approved_payments = Payment.query.filter_by(status=PaymentStatus.approved).count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(
        status=PaymentStatus.approved).scalar() or 0
    total_evaluations = Evaluation.query.count()
    total_ai_recs = AIRecommendation.query.count()

    elements += _section_banner("Estadísticas Generales", styles)

    stat_data = [
        ["👨‍👩‍👧 Padres activos", "👩‍🏫 Profesores", "👶 Niños registrados", "🏫 Talleres activos"],
        [str(total_parents), str(total_teachers), str(total_children), str(total_workshops)],
        ["📋 Inscripciones activas", "✅ Pagos aprobados", "💰 Ingresos totales", "🤖 Recomendaciones IA"],
        [str(total_active_enrollments), str(total_approved_payments), f"S/. {float(total_revenue):,.2f}", str(total_ai_recs)],
    ]

    st = Table(stat_data, colWidths=[4.5*cm]*4)
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("BACKGROUND", (0, 2), (-1, 2), PINK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("TEXTCOLOR", (0, 2), (-1, 2), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 2), (-1, 2), 8),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("FONTSIZE", (0, 3), (-1, 3), 18),
        ("TEXTCOLOR", (0, 1), (-1, 1), TEAL),
        ("TEXTCOLOR", (0, 3), (-1, 3), PINK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GRAY),
        ("BACKGROUND", (0, 3), (-1, 3), LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(st)
    elements.append(Spacer(1, 0.4*cm))

    # Active workshops table
    elements += _section_banner("Talleres Activos", styles)
    workshops = Workshop.query.filter_by(is_active=True).all()
    ws_data = [["Taller", "Profesor", "Cupo", "Inscritos", "Precio"]]
    for w in workshops:
        ws_data.append([
            w.title[:28],
            f"{w.teacher.first_name} {w.teacher.last_name}" if w.teacher else "—",
            str(w.max_capacity),
            str(w.current_enrolled),
            f"S/. {float(w.price):.2f}",
        ])
    ws_table = Table(ws_data, colWidths=[6*cm, 4*cm, 2*cm, 2.5*cm, 3.5*cm], repeatRows=1)
    ws_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(ws_table)
    elements += _build_footer_note(styles)
    doc.build(elements)
    return _pdf_response(buffer.getvalue(), "dashboard_maajikids.pdf")
