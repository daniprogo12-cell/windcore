import random
from datetime import datetime

import policies
import requests

PARKER = {
    "Anholt": ["A-01"],
}

API_KEY = "Admin12345"
HEADERS = {"X-API-Key": API_KEY}

# Simpel live state til fysik-simulering
moelle_state = {}
slukkede_moeller = set()


def initialize_turbine(m_id: str) -> None:
    """
    Opretter start-state for en turbine, hvis den ikke findes endnu.
    """
    if m_id not in moelle_state:
        moelle_state[m_id] = {
            "temp": 25.0,
            "rpm": 0.0,
            "kw": 0.0,
        }


def simulate_physics(state: dict, is_stopped: bool) -> None:
    """
    Simpel fysik-model for turbineadfaerd.
    """
    if is_stopped:
        state["rpm"] *= 0.7
        state["temp"] -= 0.8
        if state["temp"] < 22.0:
            state["temp"] = 22.0
    else:
        target_rpm = random.uniform(120, 150)
        state["rpm"] += (target_rpm - state["rpm"]) * 0.2
        state["temp"] += 1.2

    state["kw"] = round(state["rpm"] * 6.0, 2)


def koer_simulering_tick() -> None:
    """
    Koerer et simulerings-tick og sender ra data til API'et.
    API'et haandterer historik, predictive maintenance og SQL.
    """
    nu = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    for park_navn, moeller in PARKER.items():
        for m_id in moeller:
            initialize_turbine(m_id)

        for m_id in moeller:
            state = moelle_state[m_id]
            current_status = (
                policies.STATUS_STOPPED if m_id in slukkede_moeller else policies.STATUS_RUNNING
            )

            simulate_physics(state, is_stopped=(m_id in slukkede_moeller))

            payload = {
                "id": m_id,
                "park": park_navn,
                "rpm": round(state["rpm"], 2),
                "temp": round(state["temp"], 2),
                "status": current_status,
                "kw": round(state["kw"], 2),
                "timestamp": nu,
            }

            try:
                response = requests.post(
                    "http://127.0.0.1:5000/api/update",
                    json=payload,
                    headers=HEADERS,
                    timeout=5.0,
                )
                response.raise_for_status()

                result = response.json()
                recommended_action = str(result.get("recommended_action", "RUN")).upper()

                if recommended_action == "STOP":
                    slukkede_moeller.add(m_id)
                elif recommended_action == "RESTART":
                    slukkede_moeller.discard(m_id)

                print(
                    f"[OK] {m_id} | {park_navn} | temp={payload['temp']} | "
                    f"rpm={payload['rpm']} | kw={payload['kw']} | action={recommended_action}"
                )

            except Exception as exc:
                print(f"[FEJL] POST til API for {m_id}: {exc}")
