import threading
import time

import policies
import simulation_service
from api_routes import app


def simulator_loop() -> None:
    """
    Kører simulatoren i baggrunden.
    Simulatoren sender rå data til API'et.
    """
    print("⏳ Venter på at API starter...")
    time.sleep(25)

    print("=====================================================")
    print("🚀 WINDCORE SIMULATOR")
    print(f"📡 Sender data hvert {policies.SIMULATION_INTERVAL} sekund")
    print("🧠 Predictive maintenance kører i API-laget")
    print("=====================================================")

    while True:
        try:
            simulation_service.koer_simulering_tick()
        except Exception as exc:
            print(f"❌ FEJL i simulator-loop: {exc}")
            time.sleep(3)

        time.sleep(policies.SIMULATION_INTERVAL)


if __name__ == "__main__":
    sim_thread = threading.Thread(target=simulator_loop, daemon=True)
    sim_thread.start()

    print("🌐 Dashboard klar på: http://127.0.0.1:5000")
    print("🚀 Tryk Ctrl+C for at stoppe systemet")

    try:
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 WindCore lukker ned...")