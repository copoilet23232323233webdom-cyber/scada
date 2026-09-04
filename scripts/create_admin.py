import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, init_db
from app.models.user import User
from app.core.security import get_password_hash
import asyncio

async def create_admin():
    await init_db()
    db = SessionLocal()
    
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Usuario admin ya existe")
        db.close()
        return
    
    admin = User(
        username="admin",
        email="admin@webdom.es",
        hashed_password=get_password_hash("admin123"),
        full_name="Administrador",
        role="admin",
        is_active=True
    )
    
    db.add(admin)
    db.commit()
    db.close()
    
    print("Usuario administrador creado:")
    print("  Usuario: admin")
    print("  ContraseÃ±a: admin123")
    print("IMPORTANTE: Cambia la contraseÃ±a despues del primer login")

if __name__ == "__main__":
    asyncio.run(create_admin())
