import time
import json
import asyncio
from collections import deque
from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

from predefined_Rules import ruleGate, load_manufacturing_database

# ============================ CONFIGURATION ============================

FILE_NAME = "xuv400_fullschema_full.json"
BUFFER_SIZE_SECONDS = 5 * 60
HIGH_IGNITION_SLEEP_SEC = 1
LOW_IGNITION_SLEEP_SEC = 45 * 60
user = True

# =====================================================================


def get_initial_ignition_status() -> int:
    return 1


def convert_decimal(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def normalize_packet(packet: Dict) -> Dict:
    return json.loads(json.dumps(packet, default=convert_decimal))


async def send_buffer_to_llm(buffer: deque, second_index: int, data_manager: Optional[Any] = None) -> Dict[str, Any]:
    """
    Analyze buffer anomaly using agents when predefined rules fail.
    
    Args:
        buffer: Deque of packet data
        second_index: Time index when anomaly was detected
        data_manager: VehicleDataManager instance (optional)
    
    Returns:
        Analysis results from agents
    """
    payload = {
        "event_time_utc": datetime.now(UTC).isoformat(),
        "failure_second_index": second_index,
        "buffer_size": len(buffer),
        "data": list(buffer)
    }
    
    print(f"\n[ANOMALY DETECTED at T+{second_index}s] Activating LLM analysis...")
    print(f"Buffer contains {len(buffer)} packets for analysis")
    
    try:
        # Import agents here to avoid circular imports
        from agents_final import diagnostic_agent, VehicleContext
        from utils import VehicleDataManager
        
        # Use default data manager if not provided
        if data_manager is None:
            data_manager = VehicleDataManager(db_path="dataset/newData.json")
        
        # Create context for agent
        context = VehicleContext(
            vehicle_id="default",
            data_manager=data_manager,
            processed_packets=list(buffer),
            anomalies={"detected_at_second": second_index},
            analysis_info=f"Anomaly detected in buffer containing {len(buffer)} packets"
        )
        
        # Call diagnostic agent with buffer data
        analysis_prompt = f"""
ANOMALY ANALYSIS REQUIRED
Detection Time: {second_index}s
Buffer Size: {len(buffer)} packets

Analyze this vehicle telemetry buffer for anomalies and issues:
1. Identify what systems are failing
2. Determine severity level (critical/major/minor)
3. Suggest corrective actions
4. Provide root cause analysis

Buffer data: {json.dumps(payload, indent=2)}
"""
        
        print("[LLM] Calling Diagnostic Agent for analysis...")
        result = await diagnostic_agent.run(
            analysis_prompt,
            deps=context
        )
        
        analysis_output = {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "anomaly_detected_at": second_index,
            "buffer_size": len(buffer),
            "agent": "diagnostic",
            "analysis": result.data
        }
        
        print(f"[LLM] Analysis complete:")
        print(f"Result: {result.data[:200]}...\n")
        
        return analysis_output
        
    except ImportError as e:
        print(f"[LLM] WARNING: Could not import agents: {e}")
        print("[LLM] Returning raw buffer for manual analysis")
        return {
            "status": "agent_unavailable",
            "timestamp": datetime.now(UTC).isoformat(),
            "anomaly_detected_at": second_index,
            "buffer_size": len(buffer),
            "raw_payload": payload
        }
    except Exception as e:
        print(f"[LLM] ERROR during analysis: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "anomaly_detected_at": second_index,
            "error": str(e),
            "buffer_size": len(buffer)
        }


def load_packets(file_name: str) -> List[Dict]:
    with open(file_name, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of packets")

    return data


def load_and_process_all_packets(file_path: str = "dataset/newData.json", enable_llm_analysis: bool = True) -> Tuple[List[Dict], Dict]:
    """
    Load all packets from newData.json and process them through predefined rules.
    When anomalies are detected, invoke LLM analysis.
    
    Args:
        file_path: Path to data file
        enable_llm_analysis: Whether to call agents for anomalies (default: True)
    
    Returns:
        Tuple of (processed_packets_list, anomalies_detected)
        - processed_packets_list: List of all packets with rule status
        - anomalies_detected: Dict with anomaly indices and analysis results
    """
    try:
        print(f"[FETCH] Loading packets from {file_path}...")
        packets = load_packets(file_path)
        print(f"[FETCH] Loaded {len(packets)} packets successfully")
        
        # Load manufacturing database
        MD = load_manufacturing_database()
        print(f"[FETCH] Manufacturing database loaded")
        
        # Initialize data manager for agent context
        try:
            from utils import VehicleDataManager
            data_manager = VehicleDataManager(db_path=file_path)
        except Exception as e:
            print(f"[FETCH] Could not initialize data manager: {e}")
            data_manager = None
        
        # Process all packets through rules
        processed_packets = []
        anomalies_detected = {}
        anomaly_buffer = deque(maxlen=BUFFER_SIZE_SECONDS)
        
        for idx, packet in enumerate(packets):
            normalized = normalize_packet(packet)
            
            # Apply predefined rules
            try:
                rule_ok = ruleGate(normalized, MD)
            except Exception as e:
                print(f"[FETCH] RuleGate error at packet {idx}: {e}")
                rule_ok = True  # Default to healthy on error
            
            # Add rule result to packet
            normalized["_rule_result"] = rule_ok
            normalized["_packet_index"] = idx
            
            processed_packets.append(normalized)
            
            # Maintain rolling buffer
            anomaly_buffer.append(normalized)
            
            # Track anomalies and call LLM analysis
            if not rule_ok:
                print(f"\n[FETCH] Anomaly detected at packet {idx}")
                
                # Call LLM for analysis if enabled
                analysis_result = None
                if enable_llm_analysis:
                    try:
                        # Run async function to call agents
                        analysis_result = asyncio.run(
                            send_buffer_to_llm(
                                anomaly_buffer, 
                                idx,
                                data_manager
                            )
                        )
                    except Exception as e:
                        print(f"[FETCH] Error calling LLM: {e}")
                        analysis_result = {"status": "failed", "error": str(e)}
                
                anomalies_detected[idx] = {
                    "timestamp": normalized.get("vehicle", {}).get("timestamp_utc", "N/A"),
                    "packet_index": idx,
                    "llm_analysis": analysis_result if enable_llm_analysis else None
                }
            
            # Progress indicator
            if (idx + 1) % 2000 == 0:
                print(f"[FETCH] Processed {idx + 1}/{len(packets)} packets - {len(anomalies_detected)} anomalies")
        
        total_anomalies = len(anomalies_detected)
        print(f"\n[FETCH] Processing complete: {len(processed_packets)} packets, {total_anomalies} anomalies detected")
        if total_anomalies > 0:
            print(f"[FETCH] Anomaly indices: {list(anomalies_detected.keys())[:10]}...")
        
        return processed_packets, anomalies_detected
        
    except FileNotFoundError:
        print(f"[FETCH] ERROR: File {file_path} not found")
        return [], {}
    except Exception as e:
        print(f"[FETCH] ERROR: {e}")
        return [], {}


def stream_and_process() -> None:
    if not user:
        return

    packets = load_packets(FILE_NAME)
    total_packets = len(packets)
    print(f"Loaded {total_packets} packets")

    MD = load_manufacturing_database()

    ignition_status = get_initial_ignition_status()
    print(f"Initial ignition status from API: {ignition_status}")

    buffer = deque(maxlen=BUFFER_SIZE_SECONDS)

    idx = 0
    second_counter = 0

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
            print(f"RuleGate error: {e}")
            rule_ok = True

        print(
            f"[T+{second_counter}s] "
            f"Ignition={ignition_status} | "
            f"RuleOK={rule_ok} | "
            f"BufferSize={len(buffer)}"
        )

        if not rule_ok:
            # Call async LLM analysis using asyncio.run
            try:
                asyncio.run(send_buffer_to_llm(buffer, second_counter))
            except Exception as e:
                print(f"Error calling LLM analysis: {e}")

        time.sleep(
            HIGH_IGNITION_SLEEP_SEC
            if ignition_status == 1
            else LOW_IGNITION_SLEEP_SEC
        )


if __name__ == "__main__":
    stream_and_process()
