from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.core.config import settings

database_url = settings.resolved_database_url
connect_args: dict[str, object] = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    database_url,
    echo=settings.db_echo,
    connect_args=connect_args,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
