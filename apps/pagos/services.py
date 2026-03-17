import hmac
import hashlib
import json
from datetime import datetime
from flask import current_app
from core.extensions import db
from apps.pagos.models import Payment, Enrollment, PaymentStatus, EnrollmentStatus
from apps.talleres.models import Workshop
from apps.ninos.models import Child
from apps.usuarios.models import User


def create_mp_preference(parent_id: int, workshop_id: int, child_id: int) -> dict:
    """Generate MercadoPago preference and return init_point URL."""
    import mercadopago

    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        raise ValueError("Taller no encontrado")
    if not workshop.is_active:
        raise ValueError("El taller no está activo")
    if workshop.is_full:
        raise ValueError("El taller no tiene cupos disponibles")

    child = Child.query.get(child_id)
    if not child:
        raise ValueError("Niño no encontrado")
    if child.parent_id != parent_id:
        raise ValueError("El niño no pertenece a este padre")

    # Check not already enrolled
    existing_enrollment = Enrollment.query.filter_by(
        child_id=child_id, workshop_id=workshop_id
    ).filter(Enrollment.status != EnrollmentStatus.cancelled).first()
    if existing_enrollment:
        raise ValueError("El niño ya está inscrito en este taller")

    # Create pending payment
    payment = Payment(
        parent_id=parent_id,
        workshop_id=workshop_id,
        child_id=child_id,
        amount=workshop.price,
        currency="PEN",
        status=PaymentStatus.pending,
    )
    db.session.add(payment)
    db.session.flush()  # Get ID before commit

    # Build MP preference
    sdk = mercadopago.SDK(current_app.config["MP_ACCESS_TOKEN"])
    preference_data = {
        "items": [
            {
                "id": str(workshop.id),
                "title": f"Inscripción: {workshop.title}",
                "description": f"Niño/a: {child.full_name}",
                "quantity": 1,
                "currency_id": "PEN",
                "unit_price": float(workshop.price),
            }
        ],
        "payer": {
            "email": User.query.get(parent_id).email,
        },
        "external_reference": str(payment.id),
        "back_urls": {
            "success": current_app.config["MP_SUCCESS_URL"],
            "failure": current_app.config["MP_FAILURE_URL"],
            "pending": current_app.config["MP_PENDING_URL"],
        },
        "auto_return": "approved",
        "notification_url": f"{current_app.config.get('APP_BASE_URL', '')}/api/v1/payments/webhook",
    }

    mp_response = sdk.preference().create(preference_data)
    if mp_response["status"] not in (200, 201):
        db.session.rollback()
        raise ValueError(f"Error al crear preferencia en MercadoPago: {mp_response}")

    preference = mp_response["response"]
    payment.mp_preference_id = preference["id"]
    db.session.commit()

    return {
        "payment_id": payment.id,
        "mp_preference_id": preference["id"],
        "init_point": preference["init_point"],
        "sandbox_init_point": preference.get("sandbox_init_point"),
        "amount": float(workshop.price),
        "currency": "PEN",
        "workshop": workshop.title,
        "child": child.full_name,
    }


def process_webhook(payload: dict, signature: str = None) -> bool:
    """
    Process MercadoPago webhook notification.
    Returns True if enrollment was activated.
    """
    import mercadopago

    action = payload.get("action", "")
    if action not in ("payment.created", "payment.updated"):
        return False

    mp_payment_id = str(payload.get("data", {}).get("id", ""))
    if not mp_payment_id:
        return False

    # Get payment detail from MP
    sdk = mercadopago.SDK(current_app.config["MP_ACCESS_TOKEN"])
    mp_detail = sdk.payment().get(mp_payment_id)
    if mp_detail["status"] != 200:
        return False

    mp_payment = mp_detail["response"]
    external_ref = mp_payment.get("external_reference", "")
    mp_status = mp_payment.get("status", "")
    mp_status_detail = mp_payment.get("status_detail", "")

    try:
        payment_id = int(external_ref)
    except (ValueError, TypeError):
        return False

    payment = Payment.query.get(payment_id)
    if not payment:
        return False

    payment.mp_payment_id = mp_payment_id
    payment.mp_status_detail = mp_status_detail

    if mp_status == "approved":
        payment.status = PaymentStatus.approved
        payment.paid_at = datetime.utcnow()
        _activate_enrollment(payment)
    elif mp_status in ("rejected", "cancelled"):
        payment.status = PaymentStatus[mp_status]
    else:
        payment.status = PaymentStatus.pending

    db.session.commit()
    return mp_status == "approved"


def _activate_enrollment(payment: Payment):
    """Create enrollment and increment workshop counter atomically."""
    workshop = Workshop.query.get(payment.workshop_id)
    if not workshop:
        return
    if workshop.is_full:
        payment.status = PaymentStatus.rejected
        payment.mp_status_detail = "no_capacity"
        return

    # Upsert enrollment
    enrollment = Enrollment.query.filter_by(
        child_id=payment.child_id,
        workshop_id=payment.workshop_id,
    ).first()

    if enrollment:
        enrollment.status = EnrollmentStatus.active
        enrollment.payment_id = payment.id
    else:
        enrollment = Enrollment(
            child_id=payment.child_id,
            workshop_id=payment.workshop_id,
            payment_id=payment.id,
            status=EnrollmentStatus.active,
        )
        db.session.add(enrollment)

    workshop.current_enrolled = min(workshop.current_enrolled + 1, workshop.max_capacity)
