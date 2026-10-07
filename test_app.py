from datetime import date, timedelta

import pytest

from app import app, reset_state


def days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def booking(**overrides):
    payload = {
        "patient": "Anita Desai",
        "doctor": "Dr. Mehta",
        "date": days_from_now(5),
        "time": "11:30",
    }
    return {**payload, **overrides}


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()


@pytest.fixture
def client():
    return app.test_client()


# ---------- Basics ----------

def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"OK"


def test_home_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Hospital Appointment Booking" in response.data


def test_static_assets_are_served(client):
    for path in ("/static/css/style.css", "/static/js/app.js", "/static/img/logo.svg"):
        assert client.get(path).status_code == 200, path


def test_security_headers_present(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


# ---------- Listing ----------

def test_get_items_returns_seeded_appointment(client):
    response = client.get("/items")

    assert response.status_code == 200
    assert response.is_json
    assert len(response.get_json()) == 1


def test_doctors_endpoint_lists_specialties(client):
    response = client.get("/doctors")

    doctors = response.get_json()
    assert response.status_code == 200
    assert "Dr. Sharma" in [doctor["name"] for doctor in doctors]
    assert all(doctor["specialty"] for doctor in doctors)


def test_list_can_be_filtered_by_doctor(client):
    client.post("/items", json=booking(doctor="Dr. Rao"))

    response = client.get("/items?doctor=Dr. Rao")

    assert [item["doctor"] for item in response.get_json()] == ["Dr. Rao"]


# ---------- Booking ----------

def test_add_appointment(client):
    response = client.post("/items", json=booking())

    body = response.get_json()
    assert response.status_code == 201
    assert body["patient"] == "Anita Desai"
    assert body["status"] == "scheduled"


def test_add_appointment_appears_in_list(client):
    client.post("/items", json=booking(patient="Vikram"))

    patients = [item["patient"] for item in client.get("/items").get_json()]

    assert "Vikram" in patients


def test_patient_name_is_trimmed(client):
    response = client.post("/items", json=booking(patient="  Meera  "))

    assert response.get_json()["patient"] == "Meera"


def test_add_appointment_missing_field(client):
    response = client.post("/items", json={"patient": "X"})

    assert response.status_code == 400


def test_add_appointment_without_json_body(client):
    response = client.post("/items", data="not json")

    assert response.status_code == 400


@pytest.mark.parametrize("overrides", [
    {"patient": "   "},
    {"patient": "x" * 81},
    {"patient": 42},
    {"doctor": "Dr. Nobody"},
    {"doctor": []},
    {"time": "10:07"},
    {"date": "12/10/2030"},
    {"date": "2030-02-31"},
    {"time": "25:99"},
    {"time": "07:30"},
    {"time": "18:30"},
])
def test_invalid_fields_are_rejected(client, overrides):
    response = client.post("/items", json=booking(**overrides))

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_past_dates_are_rejected(client):
    response = client.post("/items", json=booking(date=days_from_now(-1)))

    assert response.status_code == 400
    assert "past" in response.get_json()["error"]


def test_double_booking_same_doctor_and_slot_is_rejected(client):
    client.post("/items", json=booking())

    response = client.post("/items", json=booking(patient="Someone Else"))

    assert response.status_code == 409


def test_same_slot_with_different_doctor_is_allowed(client):
    client.post("/items", json=booking())

    response = client.post("/items", json=booking(doctor="Dr. Rao"))

    assert response.status_code == 201


def test_cancelled_slot_can_be_rebooked(client):
    first = client.post("/items", json=booking()).get_json()
    client.patch(f"/items/{first['id']}", json={"status": "cancelled"})

    response = client.post("/items", json=booking(patient="Rebooker"))

    assert response.status_code == 201


def test_ids_are_never_reused_after_delete(client):
    first = client.post("/items", json=booking()).get_json()
    client.delete(f"/items/{first['id']}")

    second = client.post("/items", json=booking(time="12:00")).get_json()

    assert second["id"] > first["id"]


# ---------- Update / delete ----------

def test_status_can_be_updated(client):
    created = client.post("/items", json=booking()).get_json()

    response = client.patch(f"/items/{created['id']}", json={"status": "completed"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"


def test_invalid_status_is_rejected(client):
    created = client.post("/items", json=booking()).get_json()

    response = client.patch(f"/items/{created['id']}", json={"status": "exploded"})

    assert response.status_code == 400


def test_patch_unknown_appointment_returns_404(client):
    response = client.patch("/items/9999", json={"status": "completed"})

    assert response.status_code == 404


def test_reopening_a_cancelled_appointment_conflicts_with_a_new_booking(client):
    first = client.post("/items", json=booking()).get_json()
    client.patch(f"/items/{first['id']}", json={"status": "cancelled"})
    client.post("/items", json=booking(patient="Rebooker"))

    response = client.patch(f"/items/{first['id']}", json={"status": "scheduled"})

    assert response.status_code == 409


def test_delete_removes_appointment(client):
    created = client.post("/items", json=booking()).get_json()

    response = client.delete(f"/items/{created['id']}")

    assert response.status_code == 204
    assert created["id"] not in [item["id"] for item in client.get("/items").get_json()]


def test_delete_unknown_appointment_returns_404(client):
    assert client.delete("/items/9999").status_code == 404


def test_wrong_method_returns_json_405(client):
    response = client.put("/items")

    assert response.status_code == 405
    assert response.get_json()["error"]


def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.get_json()["error"]


def test_internal_server_error_returns_json_500(client, monkeypatch):
    from app import app
    def boom():
        raise RuntimeError("simulated explosion")
    monkeypatch.setitem(app.view_functions, "health", boom)
    response = client.get("/health")
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}



# ---------- Metrics ----------

def test_health_and_metrics_requests_are_not_counted(client):
    client.get("/health")

    body = client.get("/metrics").get_data(as_text=True)

    assert 'endpoint="/health"' not in body


def test_metrics_expose_request_and_booking_counters(client):
    client.post("/items", json=booking())

    body = client.get("/metrics").get_data(as_text=True)

    assert "hospital_app_requests_total" in body
    assert "hospital_appointments_booked_total" in body
    assert "hospital_appointments_active" in body
