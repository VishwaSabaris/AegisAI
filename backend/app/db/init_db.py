from backend.app.core.database import Base, engine
from backend.app.db.models import IncidentRecord


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


if __name__ == "__main__":
    init_db()
