import json
import os
from typing import Dict, Any

# ---------------------------------------------------------------------
# Manufacturing Database Loader
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "Manufacturing_Database.json")


def load_manufacturing_database() -> Dict[str, Any]:
    """
    Load manufacturing database from JSON.
    Loaded once and injected into ruleGate.
    """
    # Use absolute path to handle any working directory
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] Manufacturing_Database.json not found at {DB_PATH}")
        # Return a default empty dict to allow continued operation
        return {}
    
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load manufacturing database: {e}")
        return {}


# ---------------------------------------------------------------------
# Rule Gate
# ---------------------------------------------------------------------

def ruleGate(packet: Dict[str, Any], MD: Dict[str, Any]) -> bool:
    """
    Runtime-safe rule gate.

    Returns:
        True  -> packet is healthy
        False -> anomaly detected
    """

    # ---------------- Battery imbalance under load ----------------
    cell_delta = (
        packet["battery_sensors"]["battery_cell_max_voltage_v"]
        - packet["battery_sensors"]["battery_cell_min_voltage_v"]
    )

    if cell_delta > 0.08 and packet["battery_sensors"]["battery_pack_current_a"] > 120:
        return False

    # ---------------- Thermal stress coupling ----------------
    if (
        packet["motor_inverter_sensors"]["motor_rpm"] > 7600
        and packet["motor_inverter_sensors"]["inverter_temperature_c"] > 56
        and packet["rate_of_change"]["battery_temp_rise_rate_c_per_min"] > 0.48
    ):
        return False

    # ---------------- Sustained electrical stress ----------------
    if (
        packet["battery_sensors"]["battery_pack_voltage_v"] < 370
        and packet["battery_sensors"]["battery_pack_current_a"] > 125
    ):
        return False

    # ---------------- Signal consistency degradation ----------------
    if (
        packet["signal_consistency"]["gps_vs_wheel_speed_delta"] > 2.2
        and packet["signal_consistency"]["wheel_speed_variance_ratio"] > 1.06
    ):
        return False

    # ---------------- Thermal aging awareness ----------------
    if (
        packet["component_aging"]["thermal_cycle_count"] > 950
        and packet["battery_sensors"]["battery_temperature_avg_c"] > 33.5
    ):
        return False

    # ---------------- Environmental + load interaction ----------------
    if (
        packet["environmental_sensors"]["ambient_air_temperature_c"] > 30
        and packet["operational_context"]["vehicle_load_estimated_kg"] > 220
        and packet["battery_sensors"]["battery_pack_current_a"] > 122
    ):
        return False

    return True
