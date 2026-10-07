from flask import Flask, request, jsonify, send_from_directory
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# In-memory hospital appointment data
appointments = [
    {
        "id": 1,
        "patient": "Rahul",
        "doctor": "Dr. Sharma",
        "date": "2026-10-10",
        "time": "10:00"
    }
]

# Prometheus metrics
REQUEST_COUNT = Counter(
    "hospital_app_requests_total",
    "Total number of requests received by the hospital application"
)


@app.before_request
def count_request():
    REQUEST_COUNT.inc()


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


@app.route("/items", methods=["GET"])
def get_items():
    return jsonify(appointments)


@app.route("/items", methods=["POST"])
def add_item():
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON data is required"}), 400

    required_fields = ["patient", "doctor", "date", "time"]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"{field} is required"
            }), 400

    new_appointment = {
        "id": len(appointments) + 1,
        "patient": data["patient"],
        "doctor": data["doctor"],
        "date": data["date"],
        "time": data["time"]
    }

    appointments.append(new_appointment)

    return jsonify(new_appointment), 201


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {
        "Content-Type": CONTENT_TYPE_LATEST
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
