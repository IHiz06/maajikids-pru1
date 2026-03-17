from core.extensions import db
from apps.talleres.models import Workshop
from apps.usuarios.models import User, RoleEnum
from core.security import upload_image_to_cloudinary, delete_image_from_cloudinary


def get_all_workshops(only_active=True, teacher_id=None):
    q = Workshop.query
    if only_active:
        q = q.filter(Workshop.is_active == True)
    if teacher_id:
        q = q.filter(Workshop.teacher_id == teacher_id)
    return q.order_by(Workshop.created_at.desc()).all()


def create_workshop(data: dict, image_file=None) -> Workshop:
    if data.get("teacher_id"):
        teacher = User.query.get(data["teacher_id"])
        if not teacher or teacher.role != RoleEnum.teacher:
            raise ValueError("El teacher_id no corresponde a un profesor válido")

    workshop = Workshop(
        title=data["title"].strip(),
        description=data.get("description", ""),
        teacher_id=data.get("teacher_id"),
        schedule=data.get("schedule", ""),
        max_capacity=int(data["max_capacity"]),
        price=float(data["price"]),
        is_active=data.get("is_active", True),
    )
    if image_file:
        try:
            url = upload_image_to_cloudinary(image_file, folder="maajikids/talleres")
            workshop.image_url = url
        except Exception as e:
            raise ValueError(f"Error al subir imagen: {str(e)}")

    db.session.add(workshop)
    db.session.commit()
    return workshop


def update_workshop(workshop: Workshop, data: dict, image_file=None) -> Workshop:
    if "title" in data:
        workshop.title = data["title"].strip()
    if "description" in data:
        workshop.description = data["description"]
    if "teacher_id" in data:
        if data["teacher_id"]:
            teacher = User.query.get(data["teacher_id"])
            if not teacher or teacher.role != RoleEnum.teacher:
                raise ValueError("El teacher_id no corresponde a un profesor válido")
        workshop.teacher_id = data["teacher_id"]
    if "schedule" in data:
        workshop.schedule = data["schedule"]
    if "max_capacity" in data:
        new_cap = int(data["max_capacity"])
        if new_cap < workshop.current_enrolled:
            raise ValueError("El nuevo cupo no puede ser menor a los inscritos actuales")
        workshop.max_capacity = new_cap
    if "price" in data:
        workshop.price = float(data["price"])
    if "is_active" in data:
        workshop.is_active = data["is_active"]

    if image_file:
        old_url = workshop.image_url
        try:
            url = upload_image_to_cloudinary(image_file, folder="maajikids/talleres")
            workshop.image_url = url
            if old_url:
                delete_image_from_cloudinary(old_url)
        except Exception as e:
            raise ValueError(f"Error al subir imagen: {str(e)}")

    db.session.commit()
    return workshop


def deactivate_workshop(workshop: Workshop) -> Workshop:
    workshop.is_active = False
    db.session.commit()
    return workshop
