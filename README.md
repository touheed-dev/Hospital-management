# Hospital-management

Hospital Appointment Management System with DevOps integration, automated CI testing via GitHub Actions, Docker containerization, and Prometheus metrics monitoring.

## Features
- **Flask REST API**: Endpoints for appointment scheduling and management.
- **Frontend UI**: Interactive web dashboard for booking and tracking appointments.
- **Metrics & Monitoring**: Prometheus metrics integration (`/metrics`).
- **CI/CD**: GitHub Actions workflow for automated test execution.
- **Containerization**: Dockerfile and Docker Compose setup.

## Getting Started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)

### Local Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Run tests:
   ```bash
   pytest
   ```

### Running with Docker Compose
```bash
docker-compose up --build
```
