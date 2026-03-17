from datetime import datetime
import enum
from core.extensions import db


class RoleEnum(enum.Enum):
    admin = "admin"
    teacher = "teacher"
    secretary = "secretary"
    parent = "parent"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.parent)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    children = db.relationship("Child", back_populates="parent", lazy="dynamic")
    workshops_teaching = db.relationship("Workshop", back_populates="teacher", lazy="dynamic")
    payments = db.relationship("Payment", back_populates="parent", lazy="dynamic")
    evaluations_given = db.relationship("Evaluation", back_populates="teacher", lazy="dynamic")
    contact_messages_sent = db.relationship(
        "ContactMessage", foreign_keys="ContactMessage.sender_id", back_populates="sender", lazy="dynamic"
    )
    contact_messages_replied = db.relationship(
        "ContactMessage", foreign_keys="ContactMessage.replied_by_id", back_populates="replied_by", lazy="dynamic"
    )
    chat_sessions = db.relationship("ChatSession", back_populates="parent", lazy="dynamic")
    ai_recommendations_generated = db.relationship("AIRecommendation", back_populates="generated_by_user", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role.value,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class TokenBlacklist(db.Model):
    __tablename__ = "token_blacklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
