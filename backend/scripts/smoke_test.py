import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure backend folder is on sys.path so `app` package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def run_backend_smoke_test():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200, f"Root endpoint failed: {resp.status_code} {resp.text}"
    print("Backend root endpoint OK:", resp.json())


if __name__ == "__main__":
    run_backend_smoke_test()
