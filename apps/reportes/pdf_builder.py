"""
PDF builder for MaajiKids reports using ReportLab.
Generates: evaluation reports, payment history, enrollments, AI recommendations.
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─── Brand colors ─────────────────────────────────────────────────────────────
PINK       = colors.HexColor("#E91E8C")
TEAL       = colors.HexColor("#00BCD4")
DARK_GRAY  = colors.HexColor("#424242")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY   = colors.HexColor("#9E9E9E")
WHITE      = colors.white

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png")


# ─── Styles ───────────────────────────────────────────────────────────────────

def _get_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "MaajiTitle", parent=base["Normal"],
            fontSize=20, textColor=PINK, fontName="Helvetica-Bold",
            spaceAfter=4, alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "MaajiSubtitle", parent=base["Normal"],
            fontSize=12, textColor=TEAL, fontName="Helvetica-Bold",
            spaceAfter=2, alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "MaajiBody", parent=base["Normal"],
            fontSize=9, textColor=DARK_GRAY, fontName="Helvetica",
            spaceAfter=4, leading=13,
        ),
        "label": ParagraphStyle(
            "MaajiLabel", parent=base["Normal"],
            fontSize=8, textColor=MID_GRAY, fontName="Helvetica-Bold",
            spaceAfter=1,
        ),
        "section": ParagraphStyle(
            "MaajiSection", parent=base["Normal"],
            fontSize=11, textColor=WHITE, fontName="Helvetica-Bold",
            spaceAfter=6, spaceBefore=10, alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "MaajiSmall", parent=base["Normal"],
            fontSize=7.5, textColor=MID_GRAY, fontName="Helvetica",
        ),
        "center": ParagraphStyle(
            "MaajiCenter", parent=base["Normal"],
            fontSize=9, textColor=DARK_GRAY, fontName="Helvetica",
            alignment=TA_CENTER,
        ),
        "score_good": ParagraphStyle(
            "ScoreGood", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#2E7D32"),
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "score_mid": ParagraphStyle(
            "ScoreMid", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#F57F17"),
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "score_low": ParagraphStyle(
            "ScoreLow", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#C62828"),
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
    }
    return styles


def _score_style(score: int, styles: dict) -> ParagraphStyle:
    if score >= 7:
        return styles["score_good"]
    elif score >= 5:
        return styles["score_mid"]
    return styles["score_low"]


# ─── Header / Footer builders ─────────────────────────────────────────────────

def _build_header(styles, report_title: str, report_date: str = None) -> list:
    elements = []
    report_date = report_date or datetime.now().strftime("%d/%m/%Y %H:%M")

    # Logo + title row
    logo_exists = os.path.exists(LOGO_PATH)
    if logo_exists:
        try:
            logo = RLImage(LOGO_PATH, width=2.8 * cm, height=2.8 * cm)
        except Exception:
            logo = None
    else:
        logo = None

    header_data = [[
        logo if logo else Paragraph("MaajiKids", styles["title"]),
        Paragraph(
            f"<b>Centro de Estimulación y Psicoprofilaxis</b><br/>"
            f"<font color='#9E9E9E' size='8'>Av. Principal 123 | contacto@maajikids.com</font>",
            styles["body"]
        ),
        Paragraph(
            f"<font color='#9E9E9E' size='7'>Generado el:<br/></font>"
            f"<b>{report_date}</b>",
            ParagraphStyle("right", parent=getSampleStyleSheet()["Normal"],
                           fontSize=8, alignment=TA_RIGHT, textColor=DARK_GRAY)
        ),
    ]]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 5 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("ROUNDEDCORNERS", [4]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))

    # Report title banner
    title_table = Table([[Paragraph(report_title.upper(), styles["section"])]],
                        colWidths=[18 * cm])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PINK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [4]),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 0.4 * cm))
    return elements


def _build_footer_note(styles) -> list:
    return [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=TEAL),
        Paragraph(
            "MaajiKids — Centro de Estimulación y Psicoprofilaxis | Documento generado automáticamente",
            styles["small"],
        ),
    ]


def _section_banner(text: str, styles: dict) -> list:
    banner = Table([[Paragraph(text, styles["section"])]], colWidths=[18 * cm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [3]),
    ]))
    return [banner, Spacer(1, 0.2 * cm)]


def _info_table(rows: list, styles: dict) -> Table:
    """Two-column label/value info table."""
    data = [[Paragraph(label, styles["label"]), Paragraph(str(value), styles["body"])]
            for label, value in rows]
    t = Table(data, colWidths=[5 * cm, 13 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ─── REPORT 1: Evaluation + Recommendations ──────────────────────────────────

def build_evaluation_pdf(evaluation, recommendation=None) -> bytes:
    """Full evaluation report for a child, optionally with AI recommendations."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _get_styles()
    elements = []

    # Header
    elements += _build_header(styles, "Reporte de Evaluación")

    child = evaluation.child
    teacher = evaluation.teacher
    workshop = evaluation.workshop

    # Child info
    elements += _section_banner("Información del Niño/a", styles)
    elements.append(_info_table([
        ("Nombre completo:", child.full_name if child else "—"),
        ("Edad:", f"{child.age_years} años ({child.age_months} meses)" if child else "—"),
        ("Género:", {"M": "Masculino", "F": "Femenino", "otro": "Otro"}.get(child.gender, "—") if child else "—"),
        ("Padre/Madre:", f"{child.parent.first_name} {child.parent.last_name}" if child and child.parent else "—"),
    ], styles))
    elements.append(Spacer(1, 0.3 * cm))

    # Evaluation info
    elements += _section_banner("Datos de la Evaluación", styles)
    elements.append(_info_table([
        ("Taller:", workshop.title if workshop else "—"),
        ("Profesor:", f"{teacher.first_name} {teacher.last_name}" if teacher else "—"),
        ("Fecha:", evaluation.evaluation_date.strftime("%d/%m/%Y") if evaluation.evaluation_date else "—"),
    ], styles))
    elements.append(Spacer(1, 0.3 * cm))

    # Scores table
    elements += _section_banner("Puntajes por Dominio (Escala 1-10)", styles)
    domains = [
        ("🗣️ Lenguaje", evaluation.score_language),
        ("🏃 Motor", evaluation.score_motor),
        ("🤝 Socio-emocional", evaluation.score_social),
        ("🧠 Cognitivo", evaluation.score_cognitive),
    ]
    score_data = [["Dominio", "Puntaje", "Nivel"]]
    for domain_name, score in domains:
        level = "Bueno ✓" if score >= 7 else "Regular ⚠" if score >= 5 else "Necesita apoyo ✗"
        score_data.append([
            Paragraph(domain_name, styles["body"]),
            Paragraph(str(score), _score_style(score, styles)),
            Paragraph(level, _score_style(score, styles)),
        ])

    score_table = Table(score_data, colWidths=[8 * cm, 4 * cm, 6 * cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 0.3 * cm))

    # Observations
    if evaluation.observations:
        elements += _section_banner("Observaciones del Profesor", styles)
        elements.append(Paragraph(evaluation.observations, styles["body"]))
        elements.append(Spacer(1, 0.3 * cm))

    # AI Recommendations
    if recommendation and recommendation.is_visible_to_parent:
        elements += _section_banner("Recomendaciones IA — Actividades para Casa", styles)
        elements.append(Paragraph(
            f"<i>{recommendation.summary}</i>", styles["body"]
        ))
        elements.append(Spacer(1, 0.2 * cm))

        if recommendation.activities:
            area_colors = {
                "lenguaje": colors.HexColor("#E3F2FD"),
                "motor": colors.HexColor("#E8F5E9"),
                "social": colors.HexColor("#FFF3E0"),
                "cognitivo": colors.HexColor("#F3E5F5"),
            }
            area_labels = {
                "lenguaje": "🗣️ Lenguaje",
                "motor": "🏃 Motor",
                "social": "🤝 Social",
                "cognitivo": "🧠 Cognitivo",
            }
            for act in recommendation.activities:
                area = act.get("area", "").lower()
                bg = area_colors.get(area, LIGHT_GRAY)
                act_data = [[
                    Paragraph(f"<b>{area_labels.get(area, area.capitalize())}</b> — {act.get('title', '')}", styles["subtitle"]),
                ], [
                    Paragraph(act.get("description", ""), styles["body"]),
                ]]
                act_table = Table(act_data, colWidths=[18 * cm])
                act_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), bg),
                    ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                    ("BOX", (0, 0), (-1, -1), 0.5, TEAL),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ]))
                elements.append(KeepTogether(act_table))
                elements.append(Spacer(1, 0.15 * cm))

    elements += _build_footer_note(styles)
    doc.build(elements)
    return buffer.getvalue()


# ─── REPORT 2: Payment History ────────────────────────────────────────────────

def build_payments_pdf(payments: list, title: str = "Reporte de Pagos") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _get_styles()
    elements = _build_header(styles, title)

    status_colors = {
        "approved":  colors.HexColor("#1B5E20"),
        "pending":   colors.HexColor("#E65100"),
        "rejected":  colors.HexColor("#B71C1C"),
        "cancelled": colors.HexColor("#616161"),
    }
    status_labels = {
        "approved":  "Aprobado ✓",
        "pending":   "Pendiente ⏳",
        "rejected":  "Rechazado ✗",
        "cancelled": "Cancelado",
    }

    # Summary stats
    total = len(payments)
    approved = sum(1 for p in payments if p.status.value == "approved")
    total_amount = sum(float(p.amount) for p in payments if p.status.value == "approved")

    elements += _section_banner("Resumen", styles)
    summary_data = [
        ["Total de registros", "Pagos aprobados", "Monto total recaudado"],
        [str(total), str(approved), f"S/. {total_amount:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[6 * cm, 6 * cm, 6 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GRAY),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 13),
        ("TEXTCOLOR", (2, 1), (2, 1), PINK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4 * cm))

    # Payments table
    elements += _section_banner("Detalle de Pagos", styles)
    headers = ["#", "Padre/Madre", "Niño", "Taller", "Monto", "Estado", "Fecha"]
    table_data = [headers]
    for i, p in enumerate(payments, 1):
        status_val = p.status.value
        status_text = status_labels.get(status_val, status_val)
        table_data.append([
            str(i),
            p.parent.first_name[:12] if p.parent else "—",
            p.child.full_name[:14] if p.child else "—",
            (p.workshop.title[:16] + "…") if p.workshop and len(p.workshop.title) > 16 else (p.workshop.title if p.workshop else "—"),
            f"S/. {float(p.amount):.2f}",
            status_text,
            p.paid_at.strftime("%d/%m/%Y") if p.paid_at else (p.created_at.strftime("%d/%m/%Y") if p.created_at else "—"),
        ])

    col_w = [0.8*cm, 3.2*cm, 3.2*cm, 3.5*cm, 2.2*cm, 2.8*cm, 2.3*cm]
    pay_table = Table(table_data, colWidths=col_w, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PINK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    # Color-code status column
    for i, p in enumerate(payments, 1):
        sc = status_colors.get(p.status.value, DARK_GRAY)
        style_cmds.append(("TEXTCOLOR", (5, i), (5, i), sc))
        style_cmds.append(("FONTNAME", (5, i), (5, i), "Helvetica-Bold"))

    pay_table.setStyle(TableStyle(style_cmds))
    elements.append(pay_table)
    elements += _build_footer_note(styles)
    doc.build(elements)
    return buffer.getvalue()


# ─── REPORT 3: Enrollments ────────────────────────────────────────────────────

def build_enrollments_pdf(enrollments: list, workshop_title: str = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _get_styles()
    title = f"Inscripciones — {workshop_title}" if workshop_title else "Reporte de Inscripciones"
    elements = _build_header(styles, title)

    active = sum(1 for e in enrollments if e.status.value == "active")
    elements += _section_banner(f"Total: {len(enrollments)} inscripciones | Activas: {active}", styles)

    headers = ["#", "Niño/a", "Edad", "Taller", "Estado", "Fecha Inscripción", "Padre/Madre"]
    table_data = [headers]
    for i, e in enumerate(enrollments, 1):
        child = e.child
        table_data.append([
            str(i),
            child.full_name if child else "—",
            f"{child.age_years}a" if child else "—",
            (e.workshop.title[:18] + "…") if e.workshop and len(e.workshop.title) > 18 else (e.workshop.title if e.workshop else "—"),
            e.status.value.capitalize(),
            e.enrolled_at.strftime("%d/%m/%Y") if e.enrolled_at else "—",
            f"{child.parent.first_name} {child.parent.last_name}" if child and child.parent else "—",
        ])

    col_w = [0.8*cm, 3.5*cm, 1.2*cm, 3.5*cm, 2*cm, 2.8*cm, 4.2*cm]
    t = Table(table_data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements += _build_footer_note(styles)
    doc.build(elements)
    return buffer.getvalue()


# ─── REPORT 4: Child full report (evaluations + recs) ─────────────────────────

def build_child_full_report_pdf(child, evaluations: list, recommendations: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _get_styles()
    elements = _build_header(styles, f"Expediente Completo — {child.full_name}")

    # Child info
    elements += _section_banner("Datos del Niño/a", styles)
    elements.append(_info_table([
        ("Nombre:", child.full_name),
        ("Fecha nacimiento:", child.date_of_birth.strftime("%d/%m/%Y") if child.date_of_birth else "—"),
        ("Edad:", f"{child.age_years} años ({child.age_months} meses)"),
        ("Género:", {"M": "Masculino", "F": "Femenino", "otro": "Otro"}.get(child.gender, "—")),
        ("Contacto emergencia:", child.emergency_contact or "—"),
        ("Padre/Madre:", f"{child.parent.first_name} {child.parent.last_name}" if child.parent else "—"),
    ], styles))
    elements.append(Spacer(1, 0.4 * cm))

    # Evaluations
    elements += _section_banner(f"Historial de Evaluaciones ({len(evaluations)})", styles)
    for eval_ in evaluations:
        eval_rows = [
            [Paragraph(f"Fecha: {eval_.evaluation_date.strftime('%d/%m/%Y')} | Taller: {eval_.workshop.title if eval_.workshop else '—'} | Profesor: {eval_.teacher.first_name + ' ' + eval_.teacher.last_name if eval_.teacher else '—'}", styles["label"])],
        ]
        score_row = [["Lenguaje", "Motor", "Social", "Cognitivo"],
                     [f"{eval_.score_language}/10", f"{eval_.score_motor}/10",
                      f"{eval_.score_social}/10", f"{eval_.score_cognitive}/10"]]
        st = Table(score_row, colWidths=[4.5*cm]*4)
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(KeepTogether([
            Table(eval_rows, colWidths=[18*cm]),
            st,
            Spacer(1, 0.15*cm),
        ]))
    elements.append(Spacer(1, 0.3*cm))

    # Recommendations summary
    if recommendations:
        elements += _section_banner(f"Recomendaciones IA ({len(recommendations)})", styles)
        for rec in recommendations:
            elements.append(Paragraph(
                f"<b>Generado:</b> {rec.generated_at.strftime('%d/%m/%Y')} — {rec.summary or ''}",
                styles["body"],
            ))
            if rec.activities:
                for act in rec.activities[:3]:
                    elements.append(Paragraph(
                        f"• <b>{act.get('title', '')}</b> ({act.get('area', '')}): {act.get('description', '')[:120]}…",
                        styles["small"],
                    ))
            elements.append(Spacer(1, 0.15*cm))

    elements += _build_footer_note(styles)
    doc.build(elements)
    return buffer.getvalue()
