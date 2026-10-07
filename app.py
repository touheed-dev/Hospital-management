"""MediBook - hospital appointment booking API.

State lives in memory, so run a single worker process (see the Dockerfile).
"""
import os
import threading
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, request, send_from_directory
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

app = Flask(__name__)

Appointment = dict[str, Any]

DOCTORS: tuple[dict[str, str], ...] = (
    {"name": "Dr. Sharma", "specialty": "Cardiology"},
    {"name": "Dr. Mehta", "specialty": "General Medicine"},
    {"name": "Dr. Kulkarni", "specialty": "Pediatrics"},
    {"name": "Dr. Rao", "specialty": "Orthopedics"},
)
DOCTOR_NAMES = frozenset(doctor["name"] for doctor in DOCTORS)

STATUSES = ("scheduled", "completed", "cancelled")
REQUIRED_FIELDS = ("patient", "doctor", "date", "time")
MAX_PATIENT_NAME_LENGTH = 80
FIRST_SLOT = time(8, 0)
LAST_SLOT = time(17, 30)
SLOT_MINUTES = 15
TRACKED_METHODS = frozenset({"GET", "POST", "PATCH", "DELETE", "PUT", "HEAD", "OPTIONS"})
UNTRACKED_PATHS = frozenset({"/health", "/metrics"})


def _now() -> datetime:
    """Current clinic time (naive). Set CLINIC_TZ, e.g. Asia/Kolkata, when the host runs in UTC."""
    zone = os.environ.get("CLINIC_TZ")
    return datetime.now(ZoneInfo(zone)).replace(tzinfo=None) if zone else datetime.now()

# ---------- In-memory store ----------
_lock = threading.Lock()
_appointments: list[Appointment] = []
_next_id = 1


def _seed() -> list[Appointment]:
    return [{
        "id": 1,
        "patient": "Rahul",
        "doctor": "Dr. Sharma",
        "date": (_now().date() + timedelta(days=3)).isoformat(),
        "time": "10:00",
        "status": "scheduled",
    }]


def reset_state() -> None:
    """Restore the store to its seeded state (used by the test-suite)."""
    global _appointments, _next_id
    with _lock:
        _appointments = _seed()
        _next_id = 2


reset_state()

# ---------- Prometheus metrics ----------
REQUEST_COUNT = Counter(
    "hospital_app_requests_total",
    "Total number of requests received by the hospital application",
    ["method", "endpoint", "status"],
)
BOOKED_COUNT = Counter(
    "hospital_appointments_booked",
    "Total number of appointments booked since the service started",
)
ACTIVE_APPOINTMENTS = Gauge(
    "hospital_appointments_active",
    "Number of appointments that are currently scheduled",
)


def _count_active() -> int:
    with _lock:
        return sum(1 for item in _appointments if item["status"] == "scheduled")


ACTIVE_APPOINTMENTS.set_function(_count_active)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@app.after_request
def add_headers_and_count(response: Response) -> Response:
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.path not in UNTRACKED_PATHS:
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        method = request.method if request.method in TRACKED_METHODS else "OTHER"
        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
    return response


# ---------- Helpers ----------
def error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def _is_slot_taken(
    doctor: str, day: str, slot: str, ignore_id: int | None = None
) -> bool:
    return any(
        item["doctor"] == doctor
        and item["date"] == day
        and item["time"] == slot
        and item["status"] != "cancelled"
        and item["id"] != ignore_id
        for item in _appointments
    )


def _parse_booking(data: dict[str, Any]) -> tuple[Appointment | None, str | None]:
    """Validate and normalise a booking payload. Returns (fields, error)."""
    for field in REQUIRED_FIELDS:
        if field not in data:
            return None, f"{field} is required"

    patient = data["patient"]
    if not isinstance(patient, str) or not patient.strip():
        return None, "patient must be a non-empty name"
    patient = patient.strip()
    if len(patient) > MAX_PATIENT_NAME_LENGTH:
        return None, f"patient must be at most {MAX_PATIENT_NAME_LENGTH} characters"

    doctor = data["doctor"]
    if not isinstance(doctor, str) or doctor not in DOCTOR_NAMES:
        return None, "doctor is not available"

    try:
        day = datetime.strptime(str(data["date"]), "%Y-%m-%d").date()
    except ValueError:
        return None, "date must be a valid date in YYYY-MM-DD format"

    try:
        slot = datetime.strptime(str(data["time"]), "%H:%M").time()
    except ValueError:
        return None, "time must be a valid time in HH:MM format"
    if not FIRST_SLOT <= slot <= LAST_SLOT:
        return None, "time must be within clinic hours (08:00 - 17:30)"

    if slot.minute % SLOT_MINUTES:
        return None, f"time must be on a {SLOT_MINUTES}-minute slot (e.g. 10:00, 10:15)"

    if datetime.combine(day, slot) < _now():
        return None, "appointment cannot be in the past"

    return {
        "patient": patient,
        "doctor": doctor,
        "date": day.isoformat(),
        "time": slot.strftime("%H:%M"),
    }, None


SLOT_TAKEN_MESSAGE = "That doctor already has an appointment in this time slot"


# ---------- Routes ----------
@app.route("/")
def home() -> Response:
    return send_from_directory("static", "index.html")


@app.route("/doctors", methods=["GET"])
def get_doctors() -> Response:
    return jsonify(DOCTORS)


@app.route("/items", methods=["GET"])
def get_items() -> Response:
    doctor = request.args.get("doctor")
    status = request.args.get("status")
    with _lock:
        items = [
            dict(item)
            for item in _appointments
            if (not doctor or item["doctor"] == doctor)
            and (not status or item["status"] == status)
        ]
    return jsonify(items)


@app.route("/items", methods=["POST"])
def add_item() -> Response | tuple[Response, int]:
    global _next_id
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return error("JSON data is required", 400)

    fields, problem = _parse_booking(data)
    if problem or fields is None:
        return error(problem or "Invalid booking", 400)

    with _lock:
        if _is_slot_taken(fields["doctor"], fields["date"], fields["time"]):
            return error(SLOT_TAKEN_MESSAGE, 409)
        new_appointment = {"id": _next_id, **fields, "status": "scheduled"}
        _next_id += 1
        _appointments.append(new_appointment)

    BOOKED_COUNT.inc()
    return jsonify(new_appointment), 201


@app.route("/items/<int:item_id>", methods=["PATCH"])
def update_item(item_id: int) -> Response | tuple[Response, int]:
    data = request.get_json(silent=True)
    status = data.get("status") if isinstance(data, dict) else None
    if status not in STATUSES:
        return error(f"status must be one of: {', '.join(STATUSES)}", 400)

    with _lock:
        index = next(
            (i for i, item in enumerate(_appointments) if item["id"] == item_id), None
        )
        if index is None:
            return error("Appointment not found", 404)
        current = _appointments[index]
        reopening = current["status"] == "cancelled" and status != "cancelled"
        if reopening and _is_slot_taken(
            current["doctor"], current["date"], current["time"], ignore_id=item_id
        ):
            return error(SLOT_TAKEN_MESSAGE, 409)
        updated = {**current, "status": status}
        _appointments[index] = updated

    return jsonify(updated)


@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id: int) -> Response | tuple[str, int]:
    with _lock:
        remaining = [item for item in _appointments if item["id"] != item_id]
        if len(remaining) == len(_appointments):
            return error("Appointment not found", 404)
        _appointments[:] = remaining
    return "", 204


@app.route("/health", methods=["GET"])
def health() -> tuple[str, int]:
    return "OK", 200


@app.route("/metrics")
def metrics() -> tuple[bytes, int, dict[str, str]]:
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---------- JSON error pages ----------
@app.errorhandler(404)
def not_found(_: Exception) -> tuple[Response, int]:
    return error("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_: Exception) -> tuple[Response, int]:
    return error("Method not allowed", 405)


@app.errorhandler(500)
def server_error(_: Exception) -> tuple[Response, int]:
    return error("Internal server error", 500)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),  # noqa: S104 - container needs all interfaces
        port=int(os.environ.get("PORT", "5000")),
    )
