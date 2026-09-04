from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15} if IS_SQLITE else {},
    pool_pre_ping=True,
)


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        """WAL + espera al cerrojo: sin esto los escaneos (escritura continua)
        bloquean las lecturas de la API y la UI se queda cargando."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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

            # Índices de las claves ajenas más consultadas (contadores del
            # dashboard e histórico de escaneos).
            for name, ddl in (
                ("ix_cards_gateway_id", "CREATE INDEX IF NOT EXISTS ix_cards_gateway_id ON cards(gateway_id)"),
                ("ix_gateways_plant_id", "CREATE INDEX IF NOT EXISTS ix_gateways_plant_id ON gateways(plant_id)"),
                ("ix_alarms_plant_status", "CREATE INDEX IF NOT EXISTS ix_alarms_plant_status ON alarms(plant_id, status)"),
                ("ix_scans_gateway_created", "CREATE INDEX IF NOT EXISTS ix_scans_gateway_created ON scans(gateway_id, created_at)"),
            ):
                try:
                    conn.execute(text(ddl))
                except Exception as exc:
                    print(f"[MIGRATION] No se pudo crear {name}: {exc}")
            conn.commit()

            conn.close()
    except Exception as e:
        print(f"[MIGRATION] Error en migraciones: {e}")
