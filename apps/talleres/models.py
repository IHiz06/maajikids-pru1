from datetime import datetime
from core.extensions import db


class Workshop(db.Model):
    __tablename__ = "workshops"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    schedule = db.Column(db.String(200), nullable=True)
    max_capacity = db.Column(db.Integer, nullable=False, default=10)
    current_enrolled = db.Column(db.Integer, default=0, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    teacher = db.relationship("User", back_populates="workshops_teaching")
    enrollments = db.relationship("Enrollment", back_populates="workshop", lazy="dynamic")
    evaluations = db.relationship("Evaluation", back_populates="workshop", lazy="dynamic")
    payments = db.relationship("Payment", back_populates="workshop", lazy="dynamic")

    @property
    def available_spots(self):
        return max(0, self.max_capacity - self.current_enrolled)

    @property
    def is_full(self):
        return self.current_enrolled >= self.max_capacity

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "teacher_id": self.teacher_id,
            "teacher_name": (
                f"{self.teacher.first_name} {self.teacher.last_name}" if self.teacher else None
            ),
            "schedule": self.schedule,
            "max_capacity": self.max_capacity,
            "current_enrolled": self.current_enrolled,
            "available_spots": self.available_spots,
            "price": float(self.price) if self.price else 0,
            "image_url": self.image_url,
            "is_active": self.is_active,
            "is_full": self.is_full,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
