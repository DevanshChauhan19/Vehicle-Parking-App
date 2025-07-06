from app import app, db
from werkzeug.security import generate_password_hash
from models import User

admin_email = "admin@example.com"
admin_password = "admin123"

with app.app_context():
    db.create_all()

    existing_admin = User.query.filter_by(email=admin_email).first()
    if not existing_admin:
        admin = User(
            name="Admin",
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            is_admin=True,
            address="Default Admin Address",
            pincode=123456
        )
        db.session.add(admin)

    db.session.commit()
