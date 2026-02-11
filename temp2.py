"""
Rule-Based Anomaly Detection Engine for Vehicle Monitoring

This module provides fast, hardcoded rule checks for critical vehicle anomalies.
Used by temp.py streaming monitor to trigger AI agent analysis only when needed.

6 Critical Detection Rules:
1. Battery Cell Imbalance - Voltage delta under load
2. Thermal Stress - High RPM + temperature + heating rate
3. Electrical Stress - Low voltage with high current draw
4. Signal Inconsistency - GPS/wheel speed mismatches
5. Thermal Aging - Cycle count + elevated temperature
6. Environmental Load - Hot weather + heavy load + high current

Returns:
    True  = Vehicle healthy, continue monitoring
    False = Anomaly detected, trigger AI analysis
"""
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
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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