"""Seed the default District360 Super Admin account.

Run from the backend directory:

    python scripts/seed_admin.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app  # noqa: E402
from app.extensions import bcrypt, db  # noqa: E402
from app.models.district import District  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402


DISTRICT_DATA = {
    "name": "Nagapattinam",
    "slug": "nagapattinam",
    "region": "Tamil Nadu",
    "status": "active",
}

ROLE_DATA = {
    "name": "SuperAdmin",
    "description": "System Administrator",
    "is_system": True,
}

USER_DATA = {
    "full_name": "Super Admin",
    "email": "admin@district360.com",
    "phone": "9999999999",
    "password": "Admin123",
    "status": "active",
    "email_verified": True,
    "phone_verified": True,
}


def seed_admin() -> None:
    """Create or update the default district, role, and admin user."""
    district = District.query.filter_by(slug=DISTRICT_DATA["slug"]).first()
    if district is None:
        district = District(**DISTRICT_DATA)
        db.session.add(district)
        db.session.flush()
    else:
        district.name = DISTRICT_DATA["name"]
        district.region = DISTRICT_DATA["region"]
        district.status = DISTRICT_DATA["status"]

    role = Role.query.filter_by(
        district_id=district.id,
        name=ROLE_DATA["name"],
    ).first()
    if role is None:
        role = Role(district_id=district.id, **ROLE_DATA)
        db.session.add(role)
        db.session.flush()
    else:
        role.description = ROLE_DATA["description"]
        role.is_system = ROLE_DATA["is_system"]

    email = USER_DATA["email"].lower().strip()
    user = User.query.filter_by(district_id=district.id, email=email).first()
    password_hash = bcrypt.generate_password_hash(USER_DATA["password"]).decode("utf-8")

    if user is None:
        user = User(
            district_id=district.id,
            full_name=USER_DATA["full_name"],
            email=email,
            phone=USER_DATA["phone"],
            password_hash=password_hash,
            auth_provider="local",
            status=USER_DATA["status"],
            email_verified=USER_DATA["email_verified"],
            phone_verified=USER_DATA["phone_verified"],
        )
        db.session.add(user)
        db.session.flush()
    else:
        user.full_name = USER_DATA["full_name"]
        user.phone = USER_DATA["phone"]
        user.password_hash = password_hash
        user.auth_provider = "local"
        user.status = USER_DATA["status"]
        user.email_verified = USER_DATA["email_verified"]
        user.phone_verified = USER_DATA["phone_verified"]

    if role not in user.roles:
        user.roles.append(role)

    db.session.commit()
    print("Admin user created successfully")


def main() -> None:
    config_name = os.getenv("FLASK_ENV", "development")
    app = create_app(config_name)
    with app.app_context():
        seed_admin()


if __name__ == "__main__":
    main()
