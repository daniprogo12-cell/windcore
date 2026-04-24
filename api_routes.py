from collections import deque
from functools import wraps

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

import data_manager
import policies
import predictive_maintenance as pm

app = Flask(__name__, template_folder="templates")
CORS(app)

API_KEY = "Admin12345"

# Live buffer i API-laget
history_buffer = {}


def require_api_key(func):
    """
    Beskytter interne update-routes med API-key.
    """
    @wraps(func)
    def decorated(*args, **kwargs):
        if request.headers.get("X-API-Key") != API_KEY:
            return jsonify({"error": "Ugyldig API-nøgle"}), 401
        return func(*args, **kwargs)
    return decorated


def get_turbine_history(turbine_id: str):
    """
    Returnerer eller opretter historik-buffer for en turbine.
    """
    if turbine_id not in history_buffer:
        history_buffer[turbine_id] = deque(maxlen=policies.HISTORY_WINDOW)
    return history_buffer[turbine_id]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/status", methods=["GET"])
def get_status():
    """
    Dashboard læser kun SQL via dette endpoint.
    """
    try:
        data = data_manager.hent_data()
        return jsonify(data), 200
    except Exception as exc:
        print(f"❌ FEJL i /api/status: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/update", methods=["POST"])
@require_api_key
def update_data():
    """
    Modtager rå data fra simulatoren.
    API'et holder de sidste 15 målinger, kører PM og gemmer resultatet i SQL.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Ingen data modtaget"}), 400

        turbine_id = data.get("id")
        park = data.get("park")
        rpm = float(data.get("rpm", 0.0))
        temp = float(data.get("temp", 0.0))
        status = data.get("status", policies.STATUS_RUNNING)
        kw = float(data.get("kw", 0.0))
        timestamp = data.get("timestamp")

        if not turbine_id or not park:
            return jsonify({"error": "Mangler id eller park"}), 400

        # Opdater historik for turbine
        turbine_history = get_turbine_history(turbine_id)
        turbine_history.append({"temp": temp, "kw": kw})

        avg_temp = sum(item["temp"] for item in turbine_history) / len(turbine_history)
        avg_kw = sum(item["kw"] for item in turbine_history) / len(turbine_history)

        # Park-total beregnet ud fra seneste måling i hver turbine-buffer
        park_power_total = 0.0
        for hist_id, hist in history_buffer.items():
            if hist and data.get("park"):
                # Vi bruger kun turbiner med samme park fra seneste payload-navn,
                # hvis ID-navngivning senere udvides, bør park->turbine map ligge separat.
                pass

        # Simpel park-total fra alle seneste buffere
        for hist in history_buffer.values():
            if hist:
                park_power_total += hist[-1]["kw"]

        pm_result = pm.analyze_health(
            history_deque=turbine_history,
            current_status=status,
            park_power_total=park_power_total,
        )

        enriched_record = {
            "id": turbine_id,
            "park": park,
            "rpm": rpm,
            "temp": temp,
            "status": status,
            "alarm": 1 if pm_result["health_status"] == "CRITICAL" else 0,
            "timestamp": timestamp,
            "kw": kw,
            "avg_temp": round(avg_temp, 2),
            "avg_kw": round(avg_kw, 2),
            "health_status": pm_result["health_status"],
            "time_to_failure": pm_result["time_to_failure"],
        }

        data_manager.gem_data([enriched_record])

        return jsonify(
            {
                "status": "success",
                "health_status": pm_result["health_status"],
                "time_to_failure": pm_result["time_to_failure"],
                "recommended_action": pm_result["recommended_action"],
                "history_size": len(turbine_history),
            }
        ), 201

    except Exception as exc:
        print(f"❌ FEJL i /api/update: {exc}")
        return jsonify({"error": str(exc)}), 500