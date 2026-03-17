from core.extensions import db
from apps.evaluaciones.models import Evaluation
from apps.talleres.models import Workshop
from apps.ninos.models import Child
from apps.pagos.models import Enrollment, EnrollmentStatus


def validate_teacher_access(teacher_id: int, child_id: int, workshop_id: int):
    """Check teacher can evaluate this child in this workshop."""
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        raise ValueError("Taller no encontrado")
    if workshop.teacher_id != teacher_id:
        raise ValueError("Solo puedes evaluar niños en tus talleres asignados")
    child = Child.query.get(child_id)
    if not child:
        raise ValueError("Niño no encontrado")
    # Child must be enrolled in this workshop
    enrolled = Enrollment.query.filter_by(
        child_id=child_id,
        workshop_id=workshop_id,
        status=EnrollmentStatus.active,
    ).first()
    if not enrolled:
        raise ValueError("El niño no está inscrito en este taller")


def create_evaluation(data: dict, teacher_id: int) -> Evaluation:
    validate_teacher_access(teacher_id, data["child_id"], data["workshop_id"])
    eval_ = Evaluation(
        child_id=data["child_id"],
        teacher_id=teacher_id,
        workshop_id=data["workshop_id"],
        evaluation_date=data["evaluation_date"],
        score_language=data["score_language"],
        score_motor=data["score_motor"],
        score_social=data["score_social"],
        score_cognitive=data["score_cognitive"],
        observations=data.get("observations"),
    )
    db.session.add(eval_)
    db.session.commit()
    return eval_


def update_evaluation(evaluation: Evaluation, data: dict) -> Evaluation:
    if "evaluation_date" in data:
        evaluation.evaluation_date = data["evaluation_date"]
    if "score_language" in data:
        evaluation.score_language = data["score_language"]
    if "score_motor" in data:
        evaluation.score_motor = data["score_motor"]
    if "score_social" in data:
        evaluation.score_social = data["score_social"]
    if "score_cognitive" in data:
        evaluation.score_cognitive = data["score_cognitive"]
    if "observations" in data:
        evaluation.observations = data["observations"]
    db.session.commit()
    return evaluation
