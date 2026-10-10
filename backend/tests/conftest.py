import pytest
from rest_framework.test import APIClient

from .factories import StudentFactory


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def student(db):
    return StudentFactory()


@pytest.fixture
def student_api(student):
    client = APIClient()
    client.force_authenticate(student)
    return client


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
