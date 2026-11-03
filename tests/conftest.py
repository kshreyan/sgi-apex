import pytest

from sgi_apex.data import synthetic
from sgi_apex.entities import registry


@pytest.fixture(scope="session")
def programmes():
    return registry.load_programmes()


@pytest.fixture(scope="session")
def silver(programmes):
    raw = synthetic.generate(programmes)
    return raw.merge(programmes[["programme_id", "entity_id", "campus", "sanctioned_intake"]], on="programme_id")
