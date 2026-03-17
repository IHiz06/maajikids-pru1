from datetime import datetime
from core.extensions import db


class AIRecommendation(db.Model):
    __tablename__ = "ai_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(
        db.Integer, db.ForeignKey("evaluations.id"), unique=True, nullable=False
    )
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False)
    generated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    activities = db.Column(db.JSON, nullable=True)  # [{area, title, description}]
    raw_response = db.Column(db.Text, nullable=True)
    is_visible_to_parent = db.Column(db.Boolean, default=True, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    evaluation = db.relationship("Evaluation", back_populates="ai_recommendation")
    child = db.relationship("Child", back_populates="ai_recommendations")
    generated_by_user = db.relationship("User", back_populates="ai_recommendations_generated")

    def to_dict(self):
        return {
            "id": self.id,
            "evaluation_id": self.evaluation_id,
            "child_id": self.child_id,
            "child_name": self.child.full_name if self.child else None,
            "generated_by": self.generated_by,
            "generated_by_name": (
                f"{self.generated_by_user.first_name} {self.generated_by_user.last_name}"
                if self.generated_by_user else None
            ),
            "summary": self.summary,
            "activities": self.activities,
            "is_visible_to_parent": self.is_visible_to_parent,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    parent = db.relationship("User", back_populates="chat_sessions")
    messages = db.relationship(
        "ChatMessage", back_populates="session", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = db.relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
