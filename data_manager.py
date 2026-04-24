from datetime import datetime

import pyodbc

CONN_STR = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:hiphopgruppe18.database.windows.net,1433;"
    "Database=free-sql-db-5285113;"
    "Uid=CloudSA687a4c06;"
    "Pwd=Admin12345;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=30;"
)


def get_connection():
    """
    Opretter og returnerer en SQL-forbindelse.
    """
    return pyodbc.connect(CONN_STR)


def parse_timestamp(raw_value):
    """
    Parser timestamp robust og bevarer mikrosekunder, hvis de findes.
    """
    ts_str = str(raw_value or "").replace("T", " ")
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        try:
            return datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.now()


def gem_data(data_liste):
    """
    Gemmer berigede data i SQL.
    Rejser exceptions videre, saa API'et kan rapportere fejl korrekt.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        for d in data_liste:
            cursor.execute(
                """
                INSERT INTO TurbineData (
                    TurbineId,
                    Park,
                    RPM,
                    Temp,
                    Status,
                    Alarm,
                    Timestamp,
                    kW,
                    AvgTemp,
                    AvgKW,
                    HealthStatus,
                    TimeToFailure
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                d.get("id"),
                d.get("park"),
                d.get("rpm", 0.0),
                d.get("temp", 0.0),
                d.get("status", "STOPPED"),
                d.get("alarm", 0),
                parse_timestamp(d.get("timestamp")),
                d.get("kw", 0.0),
                d.get("avg_temp", 0.0),
                d.get("avg_kw", 0.0),
                d.get("health_status", "HEALTHY"),
                d.get("time_to_failure", 999.0),
            )

        conn.commit()
        print(f"[OK] Data gemt i SQL ({len(data_liste)} raekker)")
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_latest_order_expression(cursor):
    """
    Vaelger den mest stabile sortering for seneste raekke pr. turbine.
    Foretraekker Id DESC, hvis kolonnen findes. Ellers bruges Timestamp DESC.
    """
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'TurbineData'
        """
    )
    column_names = {row.COLUMN_NAME.lower() for row in cursor.fetchall()}

    if "id" in column_names:
        return "Id DESC"
    if "timestamp" in column_names:
        return "Timestamp DESC"

    raise RuntimeError("Kunne ikke finde en gyldig sorteringskolonne i TurbineData")


def hent_data():
    """
    Henter seneste raekke pr. turbine fra SQL og mapper kolonnenavne til frontend.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        latest_order = get_latest_order_expression(cursor)

        query = f"""
            WITH LatestData AS (
                SELECT
                    TurbineId,
                    Park,
                    RPM,
                    Temp,
                    Status,
                    Alarm,
                    Timestamp,
                    kW,
                    AvgTemp,
                    AvgKW,
                    HealthStatus,
                    TimeToFailure,
                    ROW_NUMBER() OVER (
                        PARTITION BY TurbineId
                        ORDER BY {latest_order}
                    ) AS rn
                FROM TurbineData
            )
            SELECT
                TurbineId,
                Park,
                RPM,
                Temp,
                Status,
                Alarm,
                Timestamp,
                kW,
                AvgTemp,
                AvgKW,
                HealthStatus,
                TimeToFailure
            FROM LatestData
            WHERE rn = 1
            ORDER BY Park, TurbineId
        """
        cursor.execute(query)

        rows = cursor.fetchall()
        result = []

        for row in rows:
            timestamp_value = row.Timestamp
            if isinstance(timestamp_value, datetime):
                timestamp_value = timestamp_value.strftime("%Y-%m-%d %H:%M:%S")

            result.append(
                {
                    "id": row.TurbineId,
                    "park": row.Park,
                    "rpm": float(row.RPM),
                    "temp": float(row.Temp),
                    "status": row.Status,
                    "alarm": int(row.Alarm),
                    "timestamp": timestamp_value,
                    "kw": float(row.kW),
                    "avg_temp": float(row.AvgTemp),
                    "avg_kw": float(row.AvgKW),
                    "health_status": row.HealthStatus,
                    "time_to_failure": float(row.TimeToFailure),
                }
            )

        return result
    finally:
        if conn:
            conn.close()
