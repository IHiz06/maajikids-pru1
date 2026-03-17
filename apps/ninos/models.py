from datetime import datetime, date
from core.extensions import db


class Child(db.Model):
    __tablename__ = "children"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)  # 'M' | 'F' | 'otro'
    photo_url = db.Column(db.String(500), nullable=True)
    # AES-256 Fernet encrypted fields (stored as cipher text in DB)
    medical_info = db.Column(db.Text, nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    emergency_contact = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    parent = db.relationship("User", back_populates="children")
    enrollments = db.relationship("Enrollment", back_populates="child", lazy="dynamic")
    evaluations = db.relationship("Evaluation", back_populates="child", lazy="dynamic")
    ai_recommendations = db.relationship("AIRecommendation", back_populates="child", lazy="dynamic")
    payments = db.relationship("Payment", back_populates="child", lazy="dynamic")

    @property
    def age_years(self) -> int:
        today = date.today()
        dob = self.date_of_birth
        return (today.year - dob.year) - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def age_months(self) -> int:
        today = date.today()
        dob = self.date_of_birth
        months = (today.year - dob.year) * 12 + (today.month - dob.month)
        if today.day < dob.day:
            months -= 1
        return max(0, months)

    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "parent_id": self.parent_id,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age_years": self.age_years,
            "age_months": self.age_months,
            "gender": self.gender,
            "photo_url": self.photo_url,
            "emergency_contact": self.emergency_contact,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            # Decryption is done at schema/service level
            data["medical_info"] = self.medical_info
            data["allergies"] = self.allergies
        return data
