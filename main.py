"""
FastAPI application for vehicle analysis and maintenance system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime
import threading
import asyncio
from collections import deque

from agents_final import route_query, get_comprehensive_analysis
from utils import VehicleDataManager, AnalysisLogger
from fetch import load_packets, convert_decimal, normalize_packet
from predefined_Rules import ruleGate, load_manufacturing_database

# Data source: newData.json (rich telemetry)
# Use absolute path to handle any working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.getenv("DATASET_PATH", os.path.join(SCRIPT_DIR, "dataset", "newData.json"))

# Initialize FastAPI app
app = FastAPI(
    title="Vehicle Analysis & Maintenance System",
    description="AI-powered vehicle diagnostics, maintenance, and performance analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
data_manager = VehicleDataManager(db_path=DATASET_PATH)
logger = AnalysisLogger()

# Create logs directory
LOGS_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# ============================================================================
# Anomaly Storage (In-memory, Serverless-safe)
# ============================================================================

def print_anomaly_to_terminal(anomaly_idx: int, analysis: dict):
    """Print anomaly analysis to terminal for confirmation"""
    print("\n" + "="*80)
    print("ANOMALY ANALYSIS REPORT")
    print(f"Anomaly ID: {anomaly_idx}")
    print(f"Timestamp: {analysis.get('timestamp')}")
    print(f"Agent Used: {analysis.get('agent')}")
    print("="*80)
    print(f"Analysis:\n{analysis.get('response', 'N/A')}")
    print("="*80 + "\n")

# ============================================================================
# Global Data Buffer - Continuous Streaming Mode
# ============================================================================
processed_packets = []
anomalies_detected = {}
rolling_buffer = deque(maxlen=300)  # Last 5 minutes of data (1 packet/sec)
current_packet_index = 0
stream_active = False
data_load_status = "pending"
data_load_message = ""
latest_analysis = None


def load_data_stream():
    """Load packets once for streaming"""
    global processed_packets, data_load_status, data_load_message
    
    try:
        print("[MAIN] Loading packet data for streaming...")
        print(f"[MAIN] Looking for data at: {DATASET_PATH}")
        
        # Check if file exists
        if not os.path.exists(DATASET_PATH):
            print(f"[MAIN] ERROR: File not found at {DATASET_PATH}")
            data_load_status = "failed"
            data_load_message = f"File not found: {DATASET_PATH}"
            return False
        
        processed_packets = load_packets(DATASET_PATH)
        print(f"[MAIN] Loaded {len(processed_packets)} packets for streaming")
        data_load_status = "streaming"
        data_load_message = f"Streaming {len(processed_packets)} packets at 1 packet/sec"
        return True
    except FileNotFoundError:
        print(f"[MAIN] ERROR: File {DATASET_PATH} not found")
        data_load_status = "failed"
        data_load_message = f"File not found: {DATASET_PATH}"
        return False
    except Exception as e:
        print(f"[MAIN] ERROR loading packets: {e}")
        data_load_status = "error"
        data_load_message = str(e)
        return False


def packet_stream_worker():
    """
    Background worker that continuously processes packets like real-time data.
    Processes 1 packet per second, checks rules, and triggers analysis on anomalies.
    """
    global processed_packets, anomalies_detected, rolling_buffer, current_packet_index, stream_active, latest_analysis
    
    if not processed_packets:
        print("[STREAM] ERROR: No packets loaded")
        return
    
    stream_active = True
    print(f"\n[STREAM] Starting continuous packet stream... Processing {len(processed_packets)} packets")
    print(f"[STREAM] 1 packet = 1 second simulation\n")
    
    # Load manufacturing database
    MD = load_manufacturing_database()
    
    # Create event loop ONCE at the start of the thread (not in the loop)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    packet_counter = 0
    anomaly_counter = 0
    
    try:
        while stream_active:
            # Get packet cyclically
            idx = current_packet_index % len(processed_packets)
            packet = normalize_packet(processed_packets[idx])
            current_packet_index += 1
            packet_counter += 1
            
            # Add to rolling buffer
            rolling_buffer.append(packet)
            
            # Check predefined rules
            try:
                rule_ok = ruleGate(packet, MD)
            except Exception as e:
                print(f"[STREAM] RuleGate error: {e}")
                rule_ok = True
            
            # Print status
            status_str = "[OK] HEALTHY" if rule_ok else "[!] ANOMALY"
            print(f"[Stream #{packet_counter}] {status_str} | Buffer: {len(rolling_buffer)}")
            
            # If anomaly detected, trigger agent analysis
            if not rule_ok:
                anomaly_counter += 1
                print(f"\n>>> ANOMALY #{anomaly_counter} DETECTED at packet {idx} - Calling agents for analysis...\n")
                
                # Call async analysis using the persistent event loop
                try:
                    # Call agents with current buffer
                    analysis_context = {
                        "processed_packets": list(rolling_buffer),
                        "anomalies_detected": anomalies_detected,
                        "total_packets": len(processed_packets),
                        "total_anomalies": anomaly_counter
                    }
                    
                    result = loop.run_until_complete(
                        route_query(
                            query=f"Analyze this anomaly detected at packet {idx}. Check all systems for issues.",
                            vehicle_id="default",
                            data_manager=data_manager,
                            analysis_context=analysis_context
                        )
                    )
                    
                    latest_analysis = {
                        "timestamp": datetime.now().isoformat(),
                        "packet_index": idx,
                        "agent": result.get("agent"),
                        "response": result.get("response"),
                        "buffer_size": len(rolling_buffer)
                    }
                    
                    # Store anomaly with analysis
                    anomalies_detected[idx] = {
                        "timestamp": packet.get("vehicle", {}).get("timestamp_utc", "N/A"),
                        "packet_index": idx,
                        "analysis": latest_analysis
                    }
                    
                    # Print to terminal (Serverless-safe, no file I/O)
                    print_anomaly_to_terminal(idx, latest_analysis)
                    
                    # Print summary
                    response_preview = result.get('response', '')[:150]
                    print(f">>> Analysis complete: {response_preview}...\n")
                    
                except Exception as e:
                    print(f">>> ERROR during analysis: {e}\n")
                    latest_analysis = {
                        "timestamp": datetime.now().isoformat(),
                        "packet_index": idx,
                        "error": str(e)
                    }
            
            # Sleep 1 second per packet (simulating real-time)
            import time
            time.sleep(1)
    
    finally:
        # Close the event loop when done
        if loop and not loop.is_closed():
            loop.close()
            print("[STREAM] Event loop closed")


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for vehicle query"""
    vehicle_id: str = Field(..., description="Vehicle identifier (e.g., VH001)")
    query: str = Field(..., description="User's question about the vehicle")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vehicle_id": "default",
                "query": "Is my car healthy? Give me a detailed diagnostic report."
            }
        }


class AnalysisResponse(BaseModel):
    """Response model for vehicle analysis"""
    vehicle_id: str
    agent_used: str
    response: str
    timestamp: str


class ComprehensiveAnalysisRequest(BaseModel):
    """Request model for comprehensive analysis"""
    vehicle_id: str = Field(..., description="Vehicle identifier (e.g., default for newData)")


class VehicleListResponse(BaseModel):
    """Response model for vehicle list"""
    vehicles: list[str]
    total: int


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Vehicle Analysis & Maintenance System API",
        "version": "1.0.0",
        "dataset": DATASET_PATH,
        "mode": "continuous-streaming",
        "status": data_load_status,
        "message": data_load_message,
        "stream_active": stream_active,
        "packets_processed": current_packet_index,
        "anomalies_detected": len(anomalies_detected),
        "latest_analysis": latest_analysis,
        "logs_directory": LOGS_DIR,
        "note": "Data streams continuously. Anomaly analyses saved to logs/",
        "endpoints": {
            "POST /query": "Ask about vehicle based on streaming data",
            "POST /analyze": "Get comprehensive analysis",
            "GET /health": "API health check",
            "GET /buffer-stats": "Get current buffer statistics",
            "GET /anomalies": "Get all detected anomalies",
            "GET /analysis/{anomaly_id}": "Get full analysis report for specific anomaly",
            "GET /anomalies-summary": "Get summary of all anomalies"
        }
    }


@app.get("/buffer-stats")
async def buffer_statistics():
    """Get current streaming buffer statistics"""
    return {
        "stream_active": stream_active,
        "packets_loaded": len(processed_packets),
        "packets_processed": current_packet_index,
        "rolling_buffer_size": len(rolling_buffer),
        "anomalies_detected": len(anomalies_detected),
        "anomaly_indices": list(anomalies_detected.keys())[:20],
        "latest_analysis": latest_analysis,
        "note": "Data streams continuously at 1 packet/sec with real-time rule checking"
    }



@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "stream_active": stream_active,
        "packets_loaded": len(processed_packets),
        "packets_processed": current_packet_index,
        "buffer_size": len(rolling_buffer),
        "anomalies_detected": len(anomalies_detected),
        "latest_analysis_time": latest_analysis.get("timestamp") if latest_analysis else None
    }


@app.get("/vehicles", response_model=VehicleListResponse)
async def list_vehicles():
    """
    Get list of all available vehicles.
    
    Returns list of vehicle IDs that can be queried.
    """
    vehicle_ids = data_manager.get_vehicle_ids()
    return {
        "vehicles": vehicle_ids,
        "total": len(vehicle_ids)
    }


@app.get("/vehicle/{vehicle_id}")
async def get_vehicle_data(vehicle_id: str):
    """
    Get complete data for a specific vehicle.
    
    Args:
        vehicle_id: Vehicle identifier (e.g., VH001)
    
    Returns vehicle data including type and all sensor readings.
    """
    vehicle_data = data_manager.get_vehicle_data(vehicle_id)
    
    if not vehicle_data:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {vehicle_id} not found. Use /vehicles to see available vehicles."
        )
    
    return vehicle_data


@app.post("/query", response_model=AnalysisResponse)
async def query_vehicle(request: QueryRequest):
    """
    Ask a question about vehicle based on streaming data.
    
    Uses the live rolling buffer from continuous packet stream.
    Rules are checked every 1 second, and anomalies trigger agent analysis automatically.
    
    The master agent will automatically route your query to the appropriate specialist:
    - Diagnostic Agent: For health checks, error codes, issues
    - Maintenance Agent: For service recommendations, maintenance schedules
    - Performance Agent: For efficiency, performance metrics
    
    Example queries:
    - "Is my car healthy?"
    - "What maintenance does my car need?"
    - "How's my fuel efficiency?"
    - "What was the latest anomaly detected?"
    """
    # Verify streaming is active
    if not stream_active or not processed_packets:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active. Check /health for status."
        )
    
    # Verify vehicle exists
    vehicle_data = data_manager.get_vehicle_data(request.vehicle_id)
    if not vehicle_data:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {request.vehicle_id} not found. Use /vehicles to see available vehicles."
        )
    
    try:
        # Prepare context with live rolling buffer
        analysis_context = {
            "processed_packets": list(rolling_buffer),  # Current rolling buffer
            "anomalies_detected": anomalies_detected,
            "total_packets": current_packet_index,
            "total_anomalies": len(anomalies_detected),
            "latest_analysis": latest_analysis
        }
        
        # Route query to appropriate agent
        result = await route_query(
            query=request.query,
            vehicle_id=request.vehicle_id,
            data_manager=data_manager,
            analysis_context=analysis_context
        )
        
        # Log the analysis
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": request.vehicle_id,
            "query": request.query,
            "agent": result["agent"],
            "response": result["response"],
            "packets_in_buffer": len(rolling_buffer),
            "anomalies_detected": len(anomalies_detected)
        }
        logger.save_analysis(log_entry)
        
        return {
            "vehicle_id": request.vehicle_id,
            "agent_used": result["agent"],
            "response": result["response"],
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.post("/analyze")
async def comprehensive_analysis(request: ComprehensiveAnalysisRequest):
    """
    Get comprehensive analysis of current vehicle state.
    
    Uses data from the live rolling buffer.
    Runs all diagnostic, maintenance, and performance agents.
    """
    # Verify streaming is active
    if not stream_active or not processed_packets:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active. Check /health for status."
        )
    
    # Verify vehicle exists
    vehicle_data = data_manager.get_vehicle_data(request.vehicle_id)
    if not vehicle_data:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {request.vehicle_id} not found. Use /vehicles to see available vehicles."
        )
    
    try:
        # Prepare context with live rolling buffer
        analysis_context = {
            "processed_packets": list(rolling_buffer),
            "anomalies_detected": anomalies_detected,
            "total_packets": current_packet_index,
            "total_anomalies": len(anomalies_detected)
        }
        
        # Get comprehensive analysis
        result = await get_comprehensive_analysis(
            vehicle_id=request.vehicle_id,
            data_manager=data_manager,
            analysis_context=analysis_context
        )
        
        # Log the analysis
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": request.vehicle_id,
            "type": "comprehensive_analysis",
            "result": result,
            "packets_in_buffer": len(rolling_buffer),
            "anomalies_detected": len(anomalies_detected)
        }
        logger.save_analysis(log_entry)
        
        return {
            "vehicle_id": request.vehicle_id,
            "timestamp": datetime.now().isoformat(),
            "analysis": result,
            "packets_in_buffer": len(rolling_buffer),
            "anomalies_detected": len(anomalies_detected)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error performing analysis: {str(e)}"
        )


@app.get("/anomalies")
async def get_anomalies():
    """Get all detected anomalies with their analysis"""
    if not stream_active:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active."
        )
    
    anomaly_list = []
    for idx, anomaly_data in list(anomalies_detected.items())[:50]:  # Last 50 anomalies
        anomaly_list.append({
            "packet_index": idx,
            "timestamp": anomaly_data.get("timestamp"),
            "analysis": anomaly_data.get("analysis")
        })
    
    return {
        "total_anomalies": len(anomalies_detected),
        "recent_anomalies": anomaly_list,
        "latest_analysis": latest_analysis,
        "logs_directory": LOGS_DIR
    }


@app.get("/analysis/{anomaly_id}")
async def get_analysis_report(anomaly_id: int):
    """Get full analysis report for a specific anomaly"""
    log_file = os.path.join(LOGS_DIR, f"anomaly_{anomaly_id}_analysis.txt")
    
    if not os.path.exists(log_file):
        raise HTTPException(
            status_code=404,
            detail=f"Analysis report for anomaly {anomaly_id} not found"
        )
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "anomaly_id": anomaly_id,
            "report": content,
            "timestamp": datetime.fromtimestamp(os.path.getmtime(log_file)).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading analysis report: {str(e)}"
        )


@app.post("/api/save-anomaly")
async def save_anomaly(anomaly_data: dict):
    """Save anomaly analysis to database (for future integration)
    
    For now, prints to terminal. Later, this will save to Database.
    Serverless-safe - no file I/O.
    
    Args:
        anomaly_data: Dictionary containing anomaly details
    """
    print("\n" + "="*80)
    print("[API] ANOMALY SAVE REQUEST")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Data: {anomaly_data}")
    print("="*80 + "\n")
    
    return {
        "status": "saved",
        "message": "Anomaly printed to terminal (ready for DB integration)",
        "timestamp": datetime.now().isoformat(),
        "data": anomaly_data
    }


@app.get("/anomalies-summary")
async def get_anomalies_summary():
    """Get summary of all detected anomalies (In-memory)"""
    if not anomalies_detected:
        return {
            "total_anomalies": 0,
            "message": "No anomalies detected yet"
        }
    
    summary_data = []
    for idx, data in sorted(anomalies_detected.items()):
        summary_data.append({
            "anomaly_number": len(summary_data) + 1,
            "packet_index": idx,
            "timestamp": data.get('timestamp'),
            "agent": data.get('analysis', {}).get('agent'),
            "response_preview": data.get('analysis', {}).get('response', 'N/A')[:200]
        })
    
    return {
        "total_anomalies": len(anomalies_detected),
        "anomalies": summary_data,
        "generated_at": datetime.now().isoformat()
    }


@app.get("/history/{vehicle_id}")
async def get_vehicle_history(vehicle_id: str, limit: int = 10):
    """
    Get analysis history for a specific vehicle.
    
    Args:
        vehicle_id: Vehicle identifier
        limit: Number of recent entries to return (default: 10)
    
    Returns historical analysis data for the vehicle.
    """
    history = logger.get_vehicle_history(vehicle_id, limit)
    
    return {
        "vehicle_id": vehicle_id,
        "total_entries": len(history),
        "history": history
    }


# ============================================================================
# Run the application
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize streaming on application startup"""
    print("\n" + "="*70)
    print("INITIALIZING VEHICLE ANALYSIS SYSTEM - STREAMING MODE")
    print("="*70)
    
    # Load packets from file
    if load_data_stream():
        # Start background streaming worker
        stream_thread = threading.Thread(target=packet_stream_worker, daemon=True)
        stream_thread.start()
        print("="*70 + "\n")
    else:
        print("[MAIN] ERROR: Could not load data stream")
        print("="*70 + "\n")


if __name__ == "__main__":
    import uvicorn
    # Check for recommended API keys
    if not (os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print("WARNING: No model API key detected. Set GROQ_API_KEY or OPENROUTER_API_KEY in your .env for production.")
        print("Create a local .env from .env.sample and restart the app.")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
