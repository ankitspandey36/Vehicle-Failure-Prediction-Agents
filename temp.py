"""
Streaming Vehicle Monitor with Rule-Based Detection + AI Analysis

Continuously monitors vehicle sensor data:
1. Reads packets from JSON file (simulates real-time stream)
2. Applies rule-based anomaly detection (temp2.py)
3. When anomaly detected, calls AI agents for deep analysis
4. Maintains 5-minute rolling buffer for context

Configuration:
- Set ENABLE_AI_ANALYSIS=True to call AI agents
- Set ENABLE_AI_ANALYSIS=False for testing without API keys
"""
import time
import json
import asyncio
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any

from temp2 import ruleGate, load_manufacturing_database

# AI agent imports - only loaded if ENABLE_AI_ANALYSIS=True
try:
    from agents_final import route_query
    from utils import VehicleDataManager
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️  AI agent modules not available. Install requirements.txt to enable AI analysis.")

# ============================ CONFIGURATION ============================

FILE_NAME = "xuv400_fullschema_full.json"
BUFFER_SIZE_SECONDS = 5 * 60  # 5 minutes rolling buffer
HIGH_IGNITION_SLEEP_SEC = 1  # 1 second when driving
LOW_IGNITION_SLEEP_SEC = 45 * 60  # 45 minutes when parked
ENABLE_AI_ANALYSIS = False  # Set to True after installing requirements.txt
user = True  # Global flag to control execution

# =======================================================================


def get_initial_ignition_status() -> int:
    """Get initial ignition status (1=on, 0=off)"""
    return 1


def convert_decimal(obj: Any) -> Any:
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def normalize_packet(packet: Dict) -> Dict:
    """Normalize packet by converting Decimal to float"""
    return json.loads(json.dumps(packet, default=convert_decimal))


async def send_buffer_to_llm(
    buffer: deque,
    second_index: int,
    packet: Dict,
    data_manager=None
) -> None:
    """Send buffer to AI agents for analysis when anomaly detected"""
    payload = {
        "event_time_utc": datetime.utcnow().isoformat(),
        "failure_second_index": second_index,
        "buffer_size": len(buffer),
    }

    print("\n" + "=" * 80)
    print("🚨 ANOMALY DETECTED")
    print("=" * 80)
    print(f"Timestamp: {payload['event_time_utc']}")
    print(f"Failure at second: {second_index}")
    print(f"Buffer size: {len(buffer)} packets")
    
    if ENABLE_AI_ANALYSIS and AI_AVAILABLE:
        try:
            # Extract key metrics from last packet
            battery_v = packet['battery_sensors']['battery_pack_voltage_v']
            battery_a = packet['battery_sensors']['battery_pack_current_a']
            motor_rpm = packet['motor_inverter_sensors']['motor_rpm']
            battery_temp = packet['battery_sensors']['battery_temperature_avg_c']
            inverter_temp = packet['motor_inverter_sensors']['inverter_temperature_c']
            cell_delta = (
                packet['battery_sensors']['battery_cell_max_voltage_v'] -
                packet['battery_sensors']['battery_cell_min_voltage_v']
            )
            
            # Create a diagnostic query
            query = (
                f"URGENT: Vehicle anomaly detected at T+{second_index}s. "
                f"Analyze the situation and provide immediate guidance. "
                f"Last packet data: "
                f"Battery: {battery_v}V, {battery_a}A, temp {battery_temp}°C. "
                f"Motor: {motor_rpm} RPM. "
                f"Inverter temp: {inverter_temp}°C. "
                f"Cell voltage delta: {cell_delta:.3f}V. "
                f"Provide: 1) Root cause, 2) Severity (Critical/Warning/Info), "
                f"3) Immediate actions, 4) Risk assessment."
            )
            
            print("\nCalling AI Diagnostic Agent...")
            result = await route_query(
                query=query,
                vehicle_id="XUV400_Stream",
                data_manager=data_manager
            )
            
            print(f"\n{'=' * 80}")
            print(f"AI AGENT: {result['agent']}")
            print(f"{'=' * 80}")
            print(result['response'])
            print(f"{'=' * 80}\n")
            
        except Exception as e:
            print(f"❌ Error calling AI agents: {e}")
            print("Falling back to summary...")
            print_anomaly_summary(packet, second_index)
    else:
        print_anomaly_summary(packet, second_index)
    
    print("=" * 80 + "\n")


def print_anomaly_summary(packet: Dict, second_index: int) -> None:
    """Print summary when AI is not available"""
    print("\n[Anomaly Summary - No AI Analysis]")
    print(f"Packet #{second_index} triggered rule violation")
    print(f"  Battery Voltage: {packet['battery_sensors']['battery_pack_voltage_v']}V")
    print(f"  Battery Current: {packet['battery_sensors']['battery_pack_current_a']}A")
    print(f"  Cell Delta: {packet['battery_sensors']['battery_cell_max_voltage_v'] - packet['battery_sensors']['battery_cell_min_voltage_v']:.3f}V")
    print(f"  Motor RPM: {packet['motor_inverter_sensors']['motor_rpm']}")
    print(f"  Battery Temp: {packet['battery_sensors']['battery_temperature_avg_c']}°C")
    print(f"  Inverter Temp: {packet['motor_inverter_sensors']['inverter_temperature_c']}°C")
    print(f"\n💡 To enable AI analysis: Set ENABLE_AI_ANALYSIS=True and install requirements.txt")


def load_packets(file_name: str) -> List[Dict]:
    """Load vehicle data packets from JSON file"""
    with open(file_name, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of packets")

    return data


async def stream_and_process() -> None:
    """Main streaming loop with rule-based detection"""
    if not user:
        return

    packets = load_packets(FILE_NAME)
    total_packets = len(packets)
    
    print(f"{'=' * 80}")
    print("🚗 VEHICLE STREAMING MONITOR - Rule-Based Detection")
    if AI_AVAILABLE:
        print("(AI analysis ready - set ENABLE_AI_ANALYSIS=True to enable)")
    else:
        print("(AI analysis unavailable - install requirements.txt)")
    print(f"{'=' * 80}")
    print(f"Loaded {total_packets} packets from {FILE_NAME}")

    MD = load_manufacturing_database()
    print("✓ Manufacturing database loaded")
    
    # Initialize data manager for AI agents if available
    data_manager = None
    if AI_AVAILABLE:
        try:
            data_manager = VehicleDataManager(db_path="dataset/newData.json")
            print("✓ AI agent system initialized")
        except:
            print("⚠️  Could not initialize AI agent system")
    print(f"AI Analysis: {'ENABLED' if ENABLE_AI_ANALYSIS else 'DISABLED'}")

    ignition_status = get_initial_ignition_status()
    print(f"✓ Initial ignition status: {ignition_status}")
    print(f"{'=' * 80}\n")

    buffer = deque(maxlen=BUFFER_SIZE_SECONDS)

    idx = 0
    second_counter = 0

    try:
        while user:
            packet = normalize_packet(packets[idx])
            idx = (idx + 1) % total_packets
            second_counter += 1

            ignition_status = packet.get(
                "operational_context", {}
            ).get("ignition_status", ignition_status)

            buffer.append(packet)

            try:
                rule_ok = ruleGate(packet, MD)
            except Exception as e:
                print(f"⚠️  RuleGate error: {e}")
                rule_ok = True

            status = "✓" if rule_ok else "⚠️ "
            print(
                f"[T+{second_counter}s] {status} "
                f"Ignition={ignition_status} | "
                f"RuleOK={rule_ok} | "
                f"BufferSize={len(buffer)}"
            )

            if not rule_ok:
                await send_buffer_to_llm(buffer, second_counter, packet, data_manager)

            time.sleep(
                HIGH_IGNITION_SLEEP_SEC
                if ignition_status == 1
                else LOW_IGNITION_SLEEP_SEC
            )
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user (Ctrl+C)")
        print(f"Total packets processed: {second_counter}")
        print(f"{'=' * 80}")


if __name__ == "__main__":
    print("Starting Vehicle Streaming Monitor...")
    print("Press Ctrl+C to stop\n")
    asyncio.run(stream_and_process())
