from datetime import datetime, date
from core.extensions import db


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    workshop_id = db.Column(db.Integer, db.ForeignKey("workshops.id"), nullable=False)
    evaluation_date = db.Column(db.Date, nullable=False, default=date.today)
    score_language = db.Column(db.Integer, nullable=False)  # 1-10
    score_motor = db.Column(db.Integer, nullable=False)     # 1-10
    score_social = db.Column(db.Integer, nullable=False)    # 1-10
    score_cognitive = db.Column(db.Integer, nullable=False) # 1-10
    observations = db.Column(db.Text, nullable=True)
    ai_generated = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    child = db.relationship("Child", back_populates="evaluations")
    teacher = db.relationship("User", back_populates="evaluations_given")
    workshop = db.relationship("Workshop", back_populates="evaluations")
    ai_recommendation = db.relationship("AIRecommendation", back_populates="evaluation", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "child_id": self.child_id,
            "child_name": self.child.full_name if self.child else None,
            "teacher_id": self.teacher_id,
            "teacher_name": (
                f"{self.teacher.first_name} {self.teacher.last_name}" if self.teacher else None
            ),
            "workshop_id": self.workshop_id,
            "workshop_title": self.workshop.title if self.workshop else None,
            "evaluation_date": self.evaluation_date.isoformat() if self.evaluation_date else None,
            "scores": {
                "language": self.score_language,
                "motor": self.score_motor,
                "social": self.score_social,
                "cognitive": self.score_cognitive,
            },
            "observations": self.observations,
            "ai_generated": self.ai_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
