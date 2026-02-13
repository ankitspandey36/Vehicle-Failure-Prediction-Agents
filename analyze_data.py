#!/usr/bin/env python
"""
Analyze packet data to understand value ranges and why anomalies aren't being detected
"""

import json
import os
from pathlib import Path
from fetch import load_packets, normalize_packet

os.chdir(Path(__file__).parent)

# Load data
packets = load_packets("dataset/newData.json")
print(f"Loaded {len(packets)} packets\n")

# Sample analysis
if packets:
    packet = normalize_packet(packets[0])
    
    print("=" * 80)
    print("SAMPLE PACKET VALUES (Packet 0)")
    print("=" * 80)
    
    print("\n📊 Battery Sensors:")
    if "battery_sensors" in packet:
        bs = packet["battery_sensors"]
        print(f"  battery_pack_voltage_v: {bs.get('battery_pack_voltage_v', 'N/A')}")
        print(f"  battery_pack_current_a: {bs.get('battery_pack_current_a', 'N/A')}")
        print(f"  battery_temperature_avg_c: {bs.get('battery_temperature_avg_c', 'N/A')}")
        print(f"  battery_cell_max_voltage_v: {bs.get('battery_cell_max_voltage_v', 'N/A')}")
        print(f"  battery_cell_min_voltage_v: {bs.get('battery_cell_min_voltage_v', 'N/A')}")

    print("\n⚙️  Motor/Inverter:")
    if "motor_inverter_sensors" in packet:
        ms = packet["motor_inverter_sensors"]
        print(f"  motor_rpm: {ms.get('motor_rpm', 'N/A')}")
        print(f"  inverter_temperature_c: {ms.get('inverter_temperature_c', 'N/A')}")

    print("\n📈 Rate of Change:")
    if "rate_of_change" in packet:
        rc = packet["rate_of_change"]
        print(f"  battery_temp_rise_rate_c_per_min: {rc.get('battery_temp_rise_rate_c_per_min', 'N/A')}")

    print("\n🌡️  Environmental:")
    if "environmental_sensors" in packet:
        es = packet["environmental_sensors"]
        print(f"  ambient_air_temperature_c: {es.get('ambient_air_temperature_c', 'N/A')}")

    print("\n📦 Operational Context:")
    if "operational_context" in packet:
        oc = packet["operational_context"]
        print(f"  vehicle_load_estimated_kg: {oc.get('vehicle_load_estimated_kg', 'N/A')}")

    print("\n🔗 Signal Consistency:")
    if "signal_consistency" in packet:
        sc = packet["signal_consistency"]
        print(f"  gps_vs_wheel_speed_delta: {sc.get('gps_vs_wheel_speed_delta', 'N/A')}")
        print(f"  wheel_speed_variance_ratio: {sc.get('wheel_speed_variance_ratio', 'N/A')}")

    print("\n⏰ Component Aging:")
    if "component_aging" in packet:
        ca = packet["component_aging"]
        print(f"  thermal_cycle_count: {ca.get('thermal_cycle_count', 'N/A')}")

    print("\n" + "=" * 80)
    print("ANALYZING RULE THRESHOLDS")
    print("=" * 80)
    
    # Check each rule condition
    bs = packet.get("battery_sensors", {})
    cell_delta = bs.get("battery_cell_max_voltage_v", 0) - bs.get("battery_cell_min_voltage_v", 0)
    current = bs.get("battery_pack_current_a", 0)
    
    print(f"\n1. Battery Imbalance Rule:")
    print(f"   Cell delta: {cell_delta:.4f} (threshold: > 0.08)")
    print(f"   Current: {current:.1f}A (threshold: > 120)")
    print(f"   Triggers: {cell_delta > 0.08 and current > 120} ({'❌ BOTH conditions not met' if not (cell_delta > 0.08 and current > 120) else '✅ ANOMALY'})")
    
    # Analyze all packets for min/max values
    print("\n" + "=" * 80)
    print("VALUE RANGES ACROSS ALL PACKETS")
    print("=" * 80)
    
    values = {
        "cell_delta": [],
        "current": [],
        "voltage": [],
        "rpm": [],
        "inverter_temp": [],
        "battery_temp": [],
        "ambient_temp": [],
        "load": [],
        "gps_delta": [],
        "thermal_cycles": []
    }
    
    for packet in packets:
        packet = normalize_packet(packet)
        bs = packet.get("battery_sensors", {})
        ms = packet.get("motor_inverter_sensors", {})
        es = packet.get("environmental_sensors", {})
        oc = packet.get("operational_context", {})
        sc = packet.get("signal_consistency", {})
        ca = packet.get("component_aging", {})
        rc = packet.get("rate_of_change", {})
        
        values["cell_delta"].append(bs.get("battery_cell_max_voltage_v", 0) - bs.get("battery_cell_min_voltage_v", 0))
        values["current"].append(bs.get("battery_pack_current_a", 0))
        values["voltage"].append(bs.get("battery_pack_voltage_v", 0))
        values["rpm"].append(ms.get("motor_rpm", 0))
        values["inverter_temp"].append(ms.get("inverter_temperature_c", 0))
        values["battery_temp"].append(bs.get("battery_temperature_avg_c", 0))
        values["ambient_temp"].append(es.get("ambient_air_temperature_c", 0))
        values["load"].append(oc.get("vehicle_load_estimated_kg", 0))
        values["gps_delta"].append(sc.get("gps_vs_wheel_speed_delta", 0))
        values["thermal_cycles"].append(ca.get("thermal_cycle_count", 0))
    
    print("\nMetric Ranges (Min → Max):")
    print(f"  Cell Delta: {min(values['cell_delta']):.4f} → {max(values['cell_delta']):.4f}")
    print(f"  Current (A): {min(values['current']):.1f} → {max(values['current']):.1f}")
    print(f"  Voltage (V): {min(values['voltage']):.1f} → {max(values['voltage']):.1f}")
    print(f"  Motor RPM: {min(values['rpm']):.0f} → {max(values['rpm']):.0f}")
    print(f"  Inverter Temp (°C): {min(values['inverter_temp']):.1f} → {max(values['inverter_temp']):.1f}")
    print(f"  Battery Temp (°C): {min(values['battery_temp']):.1f} → {max(values['battery_temp']):.1f}")
    print(f"  Ambient Temp (°C): {min(values['ambient_temp']):.1f} → {max(values['ambient_temp']):.1f}")
    print(f"  Load (kg): {min(values['load']):.1f} → {max(values['load']):.1f}")
    print(f"  GPS Delta: {min(values['gps_delta']):.2f} → {max(values['gps_delta']):.2f}")
    print(f"  Thermal Cycles: {min(values['thermal_cycles']):.0f} → {max(values['thermal_cycles']):.0f}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("\nThe newData.json appears to have 'healthy' data (no anomalies).")
    print("Try one of these:")
    print("  1. Use oldData.json instead (may have more realistic anomalies)")
    print("  2. Adjust rule thresholds to be less strict")
    print("  3. Add synthetic anomaly injection for testing")
