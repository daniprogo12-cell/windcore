import policies


def analyze_health(history_deque, current_status, park_power_total=0.0):
    """
    Analyserer turbine-sundhed på baggrund af de seneste live-målinger.

    Returnerer:
    - health_status
    - time_to_failure
    - recommended_action
    """
    if len(history_deque) < 3:
        return {
            "health_status": "INITIALIZING",
            "time_to_failure": 999.0,
            "recommended_action": "RUN",
        }

    current_temp = history_deque[-1]["temp"]
    first_temp = history_deque[0]["temp"]

    # Temperaturtrend over de seneste målinger
    avg_rise = (current_temp - first_temp) / max(len(history_deque) - 1, 1)

    # TTF beregnes kun hvis temperaturen er stigende
    if avg_rise > 0:
        ttf = (policies.CRITICAL_AVG_TEMP - current_temp) / avg_rise
    else:
        ttf = 999.0

    # Kritisk stop
    if current_temp >= policies.MAX_TEMP_ALLOWED:
        return {
            "health_status": "CRITICAL",
            "time_to_failure": 0.0,
            "recommended_action": "STOP",
        }

    # Advarsel ved park-overload eller hurtig fejl-prognose
    if park_power_total > policies.MAX_PARK_POWER_KW or ttf < 5:
        return {
            "health_status": "WARNING",
            "time_to_failure": round(max(0.0, ttf), 1),
            "recommended_action": "STOP",
        }

    # Hvis turbine er stoppet, vurder genstart
    if current_status == policies.STATUS_STOPPED:
        if current_temp <= policies.SAFE_RESTART_TEMP:
            return {
                "health_status": "RESTARTING",
                "time_to_failure": 999.0,
                "recommended_action": "RESTART",
            }

        return {
            "health_status": "COOLING",
            "time_to_failure": round(max(0.0, ttf), 1),
            "recommended_action": "STOP",
        }

    return {
        "health_status": "HEALTHY",
        "time_to_failure": round(max(0.0, ttf), 1),
        "recommended_action": "RUN",
    }