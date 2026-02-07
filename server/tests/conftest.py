import os
import sys
from pathlib import Path

import pytest
from sqlmodel import SQLModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 테스트는 외부 ff-postgres 없이 로컬 sqlite로 격리 실행
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("DB_ECHO", "false")


@pytest.fixture(autouse=True)
def reset_database() -> None:
    from src.core.db.connection import engine
    from src.feature.judge import model as judge_model  # noqa: F401
    from src.feature.user import model as user_model  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
