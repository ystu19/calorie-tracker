from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.normalization import normalize_food_name

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'calorie_tracker.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_database(target_engine: Engine = engine) -> None:
    """Apply small, idempotent SQLite migrations for existing installations."""
    inspector = inspect(target_engine)
    record_columns = {column["name"] for column in inspector.get_columns("food_records")}
    record_additions = {
        "protein": "REAL NOT NULL DEFAULT 0",
        "fat": "REAL NOT NULL DEFAULT 0",
        "carbs": "REAL NOT NULL DEFAULT 0",
        "quantity": "REAL NOT NULL DEFAULT 0",
        "unit": "VARCHAR(10) NOT NULL DEFAULT 'g'",
        "food_id": "INTEGER",
        "nutrition_source": "VARCHAR(20) NOT NULL DEFAULT 'manual'",
        "alcohol_abv": "REAL NOT NULL DEFAULT 0",
    }
    food_columns = {column["name"] for column in inspector.get_columns("foods")}
    food_additions = {
        "base_amount": "REAL NOT NULL DEFAULT 100",
        "unit": "VARCHAR(10) NOT NULL DEFAULT 'g'",
        "category": "VARCHAR(20) NOT NULL DEFAULT '综合'",
        "nutrition_source": "VARCHAR(20) NOT NULL DEFAULT 'manual'",
        "estimated": "BOOLEAN NOT NULL DEFAULT 0",
        "normalized_name": "VARCHAR(100) NOT NULL DEFAULT ''",
        "alcohol_abv": "REAL NOT NULL DEFAULT 0",
    }
    has_goals = inspector.has_table("daily_goals")
    goal_columns = {column["name"] for column in inspector.get_columns("daily_goals")} if has_goals else set()
    goal_additions = {
        "weight_kg": "REAL",
        "carbs_per_kg": "REAL NOT NULL DEFAULT 2.5",
        "protein_per_kg": "REAL NOT NULL DEFAULT 1.2",
        "fat_per_kg": "REAL NOT NULL DEFAULT 0.8",
        "calories_goal": "REAL NOT NULL DEFAULT 1540",
        "carbs_goal": "REAL NOT NULL DEFAULT 175",
        "protein_goal": "REAL NOT NULL DEFAULT 84",
        "fat_goal": "REAL NOT NULL DEFAULT 56",
    }
    with target_engine.begin() as connection:
        for name, definition in record_additions.items():
            if name not in record_columns:
                connection.execute(text(f"ALTER TABLE food_records ADD COLUMN {name} {definition}"))
        for name, definition in food_additions.items():
            if name not in food_columns:
                connection.execute(text(f"ALTER TABLE foods ADD COLUMN {name} {definition}"))
        for name, definition in goal_additions.items():
            if has_goals and name not in goal_columns:
                connection.execute(text(f"ALTER TABLE daily_goals ADD COLUMN {name} {definition}"))
        connection.execute(text("UPDATE food_records SET quantity = weight WHERE quantity = 0"))
        connection.execute(text("UPDATE food_records SET unit = 'g' WHERE unit IS NULL OR unit = ''"))
        connection.execute(text("UPDATE food_records SET nutrition_source = 'manual' WHERE nutrition_source IS NULL OR nutrition_source = ''"))
        connection.execute(text("UPDATE foods SET base_amount = 100 WHERE base_amount IS NULL OR base_amount <= 0"))
        connection.execute(text("UPDATE foods SET unit = 'g' WHERE unit IS NULL OR unit = ''"))
        connection.execute(text("UPDATE foods SET nutrition_source = 'manual' WHERE nutrition_source IS NULL OR nutrition_source = ''"))
        rows = connection.execute(text("SELECT id, name, normalized_name FROM foods")).all()
        for food_id, name, stored_name in rows:
            normalized = normalize_food_name(str(name))
            if stored_name != normalized:
                connection.execute(text("UPDATE foods SET normalized_name=:name WHERE id=:id"), {"name": normalized, "id": food_id})
        if has_goals:
            connection.execute(text("UPDATE daily_goals SET calories_goal=calories, carbs_goal=carbs, protein_goal=protein, fat_goal=fat WHERE weight_kg IS NULL"))


def init_db(target_engine: Engine = engine) -> None:
    # Import models before create_all so SQLAlchemy knows every table.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=target_engine)
    migrate_database(target_engine)
