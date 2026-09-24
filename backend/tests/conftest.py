import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


# A coordinate inside the Madurai city core.
CORE = {"latitude": 9.9252, "longitude": 78.1198}
# A coordinate inside the Bhopal city core (near the Upper Lake).
BHOPAL_CORE = {"latitude": 23.2599, "longitude": 77.4126}
# A coordinate inside the Kovilpatti city core.
KOVILPATTI_CORE = {"latitude": 9.1744, "longitude": 77.8683}
# A coordinate well outside every prototype AOI (Chennai).
OUTSIDE = {"latitude": 13.08, "longitude": 80.27}
