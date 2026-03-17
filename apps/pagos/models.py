from datetime import datetime
import enum
from core.extensions import db


class PaymentStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class EnrollmentStatus(enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    workshop_id = db.Column(db.Integer, db.ForeignKey("workshops.id"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(10), default="PEN", nullable=False)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    mp_preference_id = db.Column(db.String(255), nullable=True)
    mp_payment_id = db.Column(db.String(255), nullable=True)
    mp_status_detail = db.Column(db.String(100), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    parent = db.relationship("User", back_populates="payments")
    workshop = db.relationship("Workshop", back_populates="payments")
    child = db.relationship("Child", back_populates="payments")
    enrollment = db.relationship("Enrollment", back_populates="payment", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "parent_name": f"{self.parent.first_name} {self.parent.last_name}" if self.parent else None,
            "workshop_id": self.workshop_id,
            "workshop_title": self.workshop.title if self.workshop else None,
            "child_id": self.child_id,
            "child_name": self.child.full_name if self.child else None,
            "amount": float(self.amount) if self.amount else 0,
            "currency": self.currency,
            "status": self.status.value,
            "mp_preference_id": self.mp_preference_id,
            "mp_payment_id": self.mp_payment_id,
            "mp_status_detail": self.mp_status_detail,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False)
    workshop_id = db.Column(db.Integer, db.ForeignKey("workshops.id"), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.Enum(EnrollmentStatus), default=EnrollmentStatus.active, nullable=False)

    # Relationships
    child = db.relationship("Child", back_populates="enrollments")
    workshop = db.relationship("Workshop", back_populates="enrollments")
    payment = db.relationship("Payment", back_populates="enrollment")

    __table_args__ = (
        db.UniqueConstraint("child_id", "workshop_id", name="uq_child_workshop"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "child_id": self.child_id,
            "child_name": self.child.full_name if self.child else None,
            "workshop_id": self.workshop_id,
            "workshop_title": self.workshop.title if self.workshop else None,
            "payment_id": self.payment_id,
            "enrolled_at": self.enrolled_at.isoformat() if self.enrolled_at else None,
            "status": self.status.value,
        }
