from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    from app.models import plant, gateway, card, alarm, user, scan
    Base.metadata.create_all(bind=engine)

    # Migraciones para columnas nuevas en SQLite
    try:
        with engine.connect() as conn:
            # Añadir columna lora_ok a cards si no existe
            result = conn.execute(text("SELECT COUNT(*) AS cnt FROM pragma_table_info('cards') WHERE name='lora_ok'")).fetchone()
            if result and result[0] == 0:
                conn.execute(text("ALTER TABLE cards ADD COLUMN lora_ok BOOLEAN DEFAULT 0"))
                conn.commit()
                print("[MIGRATION] Añadida columna lora_ok a cards")
            
            # Añadir columna id_start/id_end a gateways si no existen
            result = conn.execute(text("SELECT COUNT(*) AS cnt FROM pragma_table_info('gateways') WHERE name='id_start'")).fetchone()
            if result and result[0] == 0:
                conn.execute(text("ALTER TABLE gateways ADD COLUMN id_start INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE gateways ADD COLUMN id_end INTEGER DEFAULT 32"))
                conn.commit()
                print("[MIGRATION] Añadidas columnas id_start/id_end a gateways")

            # Añadir columna voltage a cards si no existe
            result = conn.execute(text("SELECT COUNT(*) AS cnt FROM pragma_table_info('cards') WHERE name='voltage'")).fetchone()
            if result and result[0] == 0:
                conn.execute(text("ALTER TABLE cards ADD COLUMN voltage FLOAT"))
                conn.commit()
                print("[MIGRATION] Añadida columna voltage a cards")

            # Añadir columna vpn_status a plants si no existe
            result = conn.execute(text("SELECT COUNT(*) AS cnt FROM pragma_table_info('plants') WHERE name='vpn_status'")).fetchone()
            if result and result[0] == 0:
                conn.execute(text("ALTER TABLE plants ADD COLUMN vpn_status VARCHAR DEFAULT 'disconnected'"))
                conn.commit()
                print("[MIGRATION] Añadida columna vpn_status a plants")

            conn.close()
    except Exception as e:
        print(f"[MIGRATION] Error en migraciones: {e}")
