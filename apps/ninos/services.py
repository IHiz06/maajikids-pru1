from core.extensions import db
from core.security import encrypt_field, decrypt_field, upload_image_to_cloudinary, delete_image_from_cloudinary
from apps.ninos.models import Child


def create_child(data: dict, parent_id: int, image_file=None) -> Child:
    child = Child(
        parent_id=parent_id,
        full_name=data["full_name"].strip(),
        date_of_birth=data["date_of_birth"],
        gender=data["gender"],
        emergency_contact=data.get("emergency_contact", ""),
    )
    # Encrypt sensitive fields
    if data.get("medical_info"):
        child.medical_info = encrypt_field(data["medical_info"])
    if data.get("allergies"):
        child.allergies = encrypt_field(data["allergies"])

    if image_file:
        try:
            url = upload_image_to_cloudinary(image_file, folder="maajikids/ninos")
            child.photo_url = url
        except Exception as e:
            raise ValueError(f"Error al subir foto: {str(e)}")

    db.session.add(child)
    db.session.commit()
    return child


def update_child(child: Child, data: dict, image_file=None) -> Child:
    if "full_name" in data:
        child.full_name = data["full_name"].strip()
    if "date_of_birth" in data:
        child.date_of_birth = data["date_of_birth"]
    if "gender" in data:
        child.gender = data["gender"]
    if "emergency_contact" in data:
        child.emergency_contact = data["emergency_contact"]
    if "medical_info" in data:
        child.medical_info = encrypt_field(data["medical_info"]) if data["medical_info"] else None
    if "allergies" in data:
        child.allergies = encrypt_field(data["allergies"]) if data["allergies"] else None
    if "is_active" in data:
        child.is_active = data["is_active"]

    if image_file:
        old_url = child.photo_url
        try:
            url = upload_image_to_cloudinary(image_file, folder="maajikids/ninos")
            child.photo_url = url
            if old_url:
                delete_image_from_cloudinary(old_url)
        except Exception as e:
            raise ValueError(f"Error al subir foto: {str(e)}")

    db.session.commit()
    return child


def decrypt_child_sensitive(child: Child) -> dict:
    """Returns child dict with decrypted medical fields."""
    data = child.to_dict()
    data["medical_info"] = decrypt_field(child.medical_info) if child.medical_info else None
    data["allergies"] = decrypt_field(child.allergies) if child.allergies else None
    return data
