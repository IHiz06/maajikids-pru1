from datetime import datetime
from core.extensions import db


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    # Can be NULL if sent by non-authenticated visitor
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    sender_name = db.Column(db.String(200), nullable=False)
    sender_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20), default="unread", nullable=False
    )  # 'unread' | 'read' | 'replied'

    # Reply fields (admin/secretary reply from the web system)
    reply_body = db.Column(db.Text, nullable=True)
    replied_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="contact_messages_sent")
    replied_by = db.relationship("User", foreign_keys=[replied_by_id], back_populates="contact_messages_replied")

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "reply_body": self.reply_body,
            "replied_by_id": self.replied_by_id,
            "replied_by_name": (
                f"{self.replied_by.first_name} {self.replied_by.last_name}"
                if self.replied_by else None
            ),
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
