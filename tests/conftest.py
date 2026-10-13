import os

import pytest

os.environ.setdefault("HOARDER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URI", "sqlite://")


@pytest.fixture
def empty_db():
    from hoarderpod.episodes import Episode, Session

    with Session() as session:
        session.query(Episode).delete()
        session.commit()
