from app import app


def test_health():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"OK"


def test_get_items():
    client = app.test_client()

    response = client.get("/items")

    assert response.status_code == 200
    assert response.is_json


def test_home_page():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Hospital Appointment Booking" in response.data


def test_add_appointment():
    client = app.test_client()

    response = client.post("/items", json={
        "patient": "Anita",
        "doctor": "Dr. Mehta",
        "date": "2026-10-12",
        "time": "11:30"
    })

    assert response.status_code == 201
    assert response.get_json()["patient"] == "Anita"


def test_add_appointment_missing_field():
    client = app.test_client()

    response = client.post("/items", json={"patient": "X"})

    assert response.status_code == 400


def test_add_appointment_appears_in_list():
    client = app.test_client()

    client.post("/items", json={
        "patient": "Vikram",
        "doctor": "Dr. Rao",
        "date": "2026-10-15",
        "time": "09:00"
    })
    response = client.get("/items")

    assert "Vikram" in [item["patient"] for item in response.get_json()]
