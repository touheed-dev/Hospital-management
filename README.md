<p align="center">
  <img src="static/img/logo.svg" alt="MediBook" width="320">
</p>

<p align="center">
  Hospital appointment booking with a Flask API, a designed dashboard, and a full DevOps toolchain:<br>
  GitHub Actions CI, Docker, Prometheus metrics and Grafana.
</p>

## Features

- **Booking dashboard**: overview tiles (scheduled, next up, busiest doctor, status breakdown), doctor picker, search, status and doctor filters.
- **Appointment lifecycle**: book, complete, cancel, reopen and delete (with a two-step delete confirmation).
- **Safe by default**: server-side validation, no double-booking of a doctor's slot (`409`), no booking in the past, clinic hours enforced (08:00 - 17:30).
- **Light and dark themes**: follows the OS preference, with a manual toggle that is remembered.
- **Observability**: Prometheus metrics at `/metrics`, health check at `/health`, live API status in the UI.
- **DevOps**: CI with coverage gate, non-root Docker image with a healthcheck, Compose stack with Prometheus and a pre-wired Grafana datasource.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/items` | List appointments. Optional `?doctor=` and `?status=` filters |
| `POST` | `/items` | Book an appointment: `patient`, `doctor`, `date` (YYYY-MM-DD), `time` (HH:MM) |
| `PATCH` | `/items/<id>` | Change status: `scheduled`, `completed` or `cancelled` |
| `DELETE` | `/items/<id>` | Delete an appointment |
| `GET` | `/doctors` | Doctors and their specialties |
| `GET` | `/health` | Liveness probe |
| `GET` | `/metrics` | Prometheus metrics |

Errors are always JSON: `{"error": "..."}`.

> Appointments are stored **in memory** and reset when the service restarts. The Docker image runs a single
> gunicorn worker (scaled with threads) so all requests see the same data.

### Metrics

| Metric | Type | Meaning |
|--------|------|---------|
| `hospital_app_requests_total{method,endpoint,status}` | counter | HTTP requests by route and status code |
| `hospital_appointments_booked_total` | counter | Appointments booked since start |
| `hospital_appointments_active` | gauge | Appointments currently scheduled |

## Getting started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)

### Run locally
```bash
python -m venv venv
# Windows: venv\Scripts\activate    |    Linux/macOS: source venv/bin/activate
pip install -r requirements-dev.txt
python app.py
```
Open <http://localhost:5000>. Set `PORT` / `HOST` to change the bind address.

### Run the tests
```bash
pytest --cov=app --cov-report=term-missing
```

### Run the full stack with Docker Compose
```bash
docker-compose up --build
```

| Service | URL |
|---------|-----|
| App | <http://localhost:5000> |
| Prometheus | <http://localhost:9090> |
| Grafana | <http://localhost:3000> (default login `admin` / `admin`; Prometheus is already configured as a datasource) |

## Project layout

```
app.py                      Flask API, validation, metrics
test_app.py                 pytest suite
static/
  index.html                Page shell
  css/style.css             Theme (design tokens, light + dark)
  js/api.js                 API client
  js/app.js                 UI logic and rendering
  js/theme-init.js          Applies the saved theme before first paint
  img/                      Logo, logo mark, favicon
grafana/provisioning/       Grafana datasource config
prometheus.yml              Scrape config
Dockerfile                  Non-root image + healthcheck + gunicorn
.github/workflows/ci.yml    Tests (80% coverage gate) and Docker build
```

## Brand

The MediBook mark is a calendar tile with coral binder rings, a medical cross, and a coral "booked" pulse at its centre.
Palette: deep teal `#0A3D3A`, teal `#0F8F82`, coral `#E8502F`, warm paper `#F5EFE3`. Type: Fraunces (display) and DM Sans (UI).
