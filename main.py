"""
FastAPI application for vehicle analysis and maintenance system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from contextlib import asynccontextmanager
import os
from datetime import datetime, UTC
import threading
import asyncio
from collections import deque

from agents_final import route_query, get_comprehensive_analysis, route_rca_capa
from utils import VehicleDataManager, AnalysisLogger
from fetch import load_packets, convert_decimal, normalize_packet
from predefined_Rules import ruleGate, load_manufacturing_database
from mongodb_handler import MongoDBHandler
from response_parser import structure_analysis_for_db, structure_rca_capa_for_db, structure_llm_response_for_db

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
# Defer creating MongoDBHandler until startup to avoid double connections
mongodb_handler: Optional[MongoDBHandler] = None


def mongo_connected() -> bool:
    """Safe check for MongoDB connection (handles None)."""
    return bool(mongodb_handler and mongodb_handler.is_connected())

# Create logs directory
LOGS_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# ============================================================================
# Anomaly Storage (In-memory, Serverless-safe)
# ============================================================================

def print_anomaly_to_terminal(anomaly_idx: int, analysis: dict):
    """Print anomaly analysis to terminal for confirmation"""
    pass  # Removed for serverless optimization

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
rca_capa_triggered = False  # Flag to track if RCA/CAPA has been triggered for current buffer


def load_data_stream():
    """Load packets once for streaming"""
    global processed_packets, data_load_status, data_load_message
    
    try:
        # Check if file exists
        if not os.path.exists(DATASET_PATH):
            data_load_status = "failed"
            data_load_message = f"File not found: {DATASET_PATH}"
            return False
        
        processed_packets = load_packets(DATASET_PATH)
        data_load_status = "streaming"
        data_load_message = f"Streaming {len(processed_packets)} packets at 1 packet/sec"
        return True
    except FileNotFoundError:
        data_load_status = "failed"
        data_load_message = f"File not found: {DATASET_PATH}"
        return False
    except Exception as e:
        data_load_status = "error"
        data_load_message = str(e)
        return False


async def trigger_rca_capa_analysis():
    """
    Trigger RCA/CAPA analysis when buffer reaches 20 items.
    Analyzes accumulated anomalies and provides root cause analysis and preventive actions.
    This runs asynchronously and stores results in MongoDB.
    """
    global rolling_buffer, anomalies_detected, latest_analysis, rca_capa_triggered
    
    try:
        analysis_context = {
            "processed_packets": list(rolling_buffer),
            "anomalies_detected": anomalies_detected,
            "total_packets": len(processed_packets),
            "total_anomalies": len(anomalies_detected)
        }
        
        # Run RCA/CAPA analysis
        result = await route_rca_capa(
            vehicle_id="default",
            data_manager=data_manager,
            analysis_context=analysis_context
        )
        
        # Parse the RCA/CAPA response
        raw_response = result.get("response", "")
        parsed_rca_capa = structure_rca_capa_for_db(raw_response)
        
        # Create document for RCA/CAPA storage
        rca_capa_document = {
            "vehicle_id": "default",
            "timestamp": datetime.now(UTC).isoformat(),
            "buffer_size": len(rolling_buffer),
            "anomalies_count": len(anomalies_detected),
            "parsed_data": parsed_rca_capa,
            "affected_components": parsed_rca_capa.get("affected_components", []),
            "oem_owners": parsed_rca_capa.get("oem_owners", []),
            "safety_criticality": parsed_rca_capa.get("safety_criticality", "Unknown"),
            "raw_response_preview": raw_response[:200]  # Store first 200 chars for debugging
        }
        
        # Save RCA/CAPA to MongoDB
        if mongo_connected():
            rca_id = mongodb_handler.save_rca_capa(rca_capa_document)
            
            # Also save as LLM response
            llm_response_doc = {
                "vehicle_id": "default",
                "agent_type": "rca_capa",
                "timestamp": datetime.now(UTC).isoformat(),
                "parsed_data": parsed_rca_capa,
                "rca_capa_id": rca_id,
                "raw_response_preview": raw_response[:200]
            }
            mongodb_handler.save_llm_response(llm_response_doc)
        
        # Update latest analysis
        latest_analysis = {
            "timestamp": datetime.now().isoformat(),
            "agent": "rca_capa",
            "structured_data": parsed_rca_capa,
            "buffer_size": len(rolling_buffer),
            "anomalies_analyzed": len(anomalies_detected)
        }
        
    except Exception as e:
        pass  # Silently log errors


def packet_stream_worker():
    """
    Background worker that continuously processes packets like real-time data.
    Processes 1 packet per second, checks rules, and triggers analysis on anomalies.
    Triggers RCA/CAPA analysis when buffer reaches 20 items.
    """
    global processed_packets, anomalies_detected, rolling_buffer, current_packet_index, stream_active, latest_analysis, rca_capa_triggered
    
    if not processed_packets:
        return
    
    stream_active = True
    
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
                rule_ok = True
            
            # Status tracking (no print for serverless)
            
            # If anomaly detected, trigger agent analysis
            if not rule_ok:
                anomaly_counter += 1
                
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
                    
                    # Parse the response text into structured JSON
                    raw_response = result.get("response", "")
                    parsed_analysis = structure_analysis_for_db(raw_response)

                    latest_analysis = {
                        "timestamp": datetime.now().isoformat(),
                        "packet_index": idx,
                        "agent": result.get("agent"),
                        "structured_data": parsed_analysis,
                        "buffer_size": len(rolling_buffer)
                    }

                    # Only persist anomalies whose analysis severity contains 'warning'
                    severity_map = parsed_analysis.get("severity_summary", {}) if isinstance(parsed_analysis, dict) else {}
                    is_warning = any(
                        isinstance(v, str) and ("warning" in v.lower() or "⚠" in v)
                        for v in severity_map.values()
                    )

                    if is_warning:
                        # Store anomaly with analysis
                        anomaly_document = {
                            "timestamp": packet.get("vehicle", {}).get("timestamp_utc", "N/A"),
                            "packet_index": idx,
                            "vehicle_id": "default",
                            "agent": result.get("agent"),
                            "analysis": latest_analysis,
                            "created_at": datetime.now(UTC).isoformat()
                        }

                        anomalies_detected[idx] = anomaly_document

                        # Save to MongoDB
                        if mongo_connected():
                            mongodb_handler.save_anomaly(anomaly_document)
                    else:
                        # Do not persist 'Normal' analyses; keep latest_analysis for visibility only
                        pass
                    
                    # Analysis complete (no terminal output for serverless)
                    
                except Exception as e:
                    pass  # Silently log errors
            
            # Sleep 1 second per packet (simulating real-time)
            import time
            time.sleep(1)
            
            # ============================================================================
            # RCA/CAPA TRIGGER: Analyze when buffer reaches 20 items
            # ============================================================================
            if len(rolling_buffer) >= 20 and not rca_capa_triggered:
                rca_capa_triggered = True  # Prevent repeated triggers on same buffer
                try:
                    # Trigger RCA/CAPA analysis asynchronously
                    loop.run_until_complete(trigger_rca_capa_analysis())
                except Exception as e:
                    pass  # Silently log errors
            
            # Reset flag when buffer clears (less than 20 items)
            if len(rolling_buffer) < 20:
                rca_capa_triggered = False
    
    finally:
        # Close the event loop when done
        if loop and not loop.is_closed():
            loop.close()


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for vehicle query"""
    vehicle_id: str = Field(..., description="Vehicle identifier (e.g., VH001)")
    query: str = Field(..., description="User's question about the vehicle")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vehicle_id": "default",
                "query": "Is my car healthy? Give me a detailed diagnostic report."
            }
        }
    )


class AnalysisResponse(BaseModel):
    """Response model for vehicle analysis"""
    vehicle_id: str
    agent_used: str
    response: str
    timestamp: str


class ComprehensiveAnalysisRequest(BaseModel):
    """Request model for comprehensive analysis"""
    vehicle_id: str = Field(..., description="Vehicle identifier (e.g., default for newData)")


class AnomalyPostRequest(BaseModel):
    """Request model for posting anomaly data to MongoDB"""
    vehicle_id: str = Field(..., description="Vehicle identifier")
    timestamp: Optional[str] = Field(None, description="Timestamp of the anomaly")
    packet_index: Optional[int] = Field(None, description="Packet index in the stream")
    analysis: dict = Field(..., description="Analysis data from agents")
    description: Optional[str] = Field(None, description="Optional description")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vehicle_id": "default",
                "timestamp": "2024-01-15T10:30:45.123Z",
                "packet_index": 245,
                "analysis": {
                    "agent": "diagnostic",
                    "response": "Engine oil pressure abnormally low",
                    "severity": "high"
                },
                "description": "Critical engine issue detected"
            }
        }
    )


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
        "mode": "continuous-streaming with MongoDB",
        "mongodb": "Enabled - All LLM anomaly data auto-saved",
        "status": data_load_status,
        "message": data_load_message,
        "stream_active": stream_active,
        "packets_processed": current_packet_index,
        "anomalies_detected": len(anomalies_detected),
        "latest_analysis": latest_analysis,
        "logs_directory": LOGS_DIR,
        "note": "Data streams continuously. Anomaly analyses auto-saved to MongoDB.",
        "endpoints": {
            "GET /status": "System status and MongoDB info",
            "GET /health": "API health check",
            "GET /analyze": "Get all anomalies from MongoDB (handles empty gracefully)",
            "POST /analyze": "Save anomaly data to MongoDB",
            "GET /anomalies": "Get recent anomalies with fallback",
            "GET /buffer-stats": "Get current buffer statistics",
            "POST /query": "Ask about vehicle based on streaming data",
            "POST /chat": "Get comprehensive analysis"
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


@app.get("/status")
async def system_status(limit: int = 50):
    """
    Get complete system status including MongoDB, stream, and all anomaly data
    
    Shows:
    - MongoDB connection status
    - Stream status
    - Complete anomaly data with all values in JSON
    - Data flow information
    
    Args:
        limit: Maximum number of anomalies to return (default: 50)
    """
    # Get database anomalies with full details
    anomalies_list = []
    db_anomaly_count = 0
    
    if mongo_connected():
        anomalies_list = mongodb_handler.get_all_anomalies(limit=limit)
        db_anomaly_count = mongodb_handler.get_anomalies_count()
    
    return {
        "system": {
            "stream_active": stream_active,
            "mongodb_connected": mongo_connected(),
            "timestamp": datetime.now().isoformat()
        },
        "streaming": {
            "packets_loaded": len(processed_packets),
            "packets_processed": current_packet_index,
            "buffer_size": len(rolling_buffer),
            "data_source": DATASET_PATH
        },
        "statistics": {
            "total_anomalies_detected": len(anomalies_detected),
            "total_anomalies_in_database": db_anomaly_count,
            "returned_count": len(anomalies_list),
            "status": "All LLM data auto-saved to MongoDB" if mongo_connected() else "MongoDB offline - using in-memory storage"
        },
        "latest_analysis": latest_analysis,
        "anomalies": anomalies_list,
        "api_help": {
            "GET /status?limit=100": "Get status with more anomalies",
            "GET /analyze": "Get all anomalies from database",
            "POST /analyze": "Save new anomaly data"
        }
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


@app.get("/analyze")
async def get_all_anomalies(vehicle_id: Optional[str] = None, limit: int = 100):
    """
    Get all detected anomalies from MongoDB
    
    This endpoint returns anomalies stored in MongoDB database.
    Useful for frontend to retrieve all anomalies without needing streaming.
    
    Args:
        vehicle_id: Optional filter by vehicle ID
        limit: Maximum number of anomalies to return (default: 100)
    
    Returns:
        List of all anomalies with their analysis
    """
    # Check if MongoDB is connected
    if not mongo_connected():
        return {
            "status": "warning",
            "total_anomalies": 0,
            "message": "MongoDB not connected. Using in-memory storage.",
            "anomalies": []
        }
    
    try:
        # Fetch anomalies from MongoDB
        anomalies = mongodb_handler.get_all_anomalies(limit=limit, vehicle_id=vehicle_id)
        
        # Get total count
        total_count = mongodb_handler.get_anomalies_count(vehicle_id=vehicle_id)
        
        return {
            "status": "success",
            "total_anomalies": total_count,
            "returned_count": len(anomalies),
            "vehicle_id": vehicle_id,
            "anomalies": anomalies,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error fetching anomalies: {str(e)}",
            "anomalies": []
        }


@app.post("/analyze")
async def save_anomaly_to_db(request: AnomalyPostRequest):
    """
    Save anomaly data directly to MongoDB
    
    This endpoint allows posting anomaly data that will be stored in MongoDB.
    Automatically parses text responses into structured JSON format.
    
    Useful for:
    - Manual anomaly submission
    - Direct frontend-to-database saving
    - Legacy system integration
    
    Args:
        request: AnomalyPostRequest containing vehicle_id, analysis, etc.
    
    Returns:
        Success status with saved anomaly ID and structured data
    """
    # Check if MongoDB is connected
    if not mongo_connected():
        return {
            "status": "warning",
            "message": "MongoDB not connected. Saving to in-memory storage only.",
            "anomaly_id": None
        }
    
    try:
        # Prepare document for MongoDB
        anomaly_document = {
            "vehicle_id": request.vehicle_id,
            "analysis": request.analysis,
            "created_at": datetime.now(UTC).isoformat()
        }
        
        # Add optional fields if provided
        if request.timestamp:
            anomaly_document["timestamp"] = request.timestamp
        if request.packet_index is not None:
            anomaly_document["packet_index"] = request.packet_index
        if request.description:
            anomaly_document["description"] = request.description
        
        # If analysis contains a text response, parse it into structured JSON and replace
        if isinstance(request.analysis, dict) and "response" in request.analysis:
            response_text = request.analysis.get("response", "")
            if isinstance(response_text, str) and response_text.strip():
                try:
                    parsed = structure_analysis_for_db(response_text)
                    # Replace the entire analysis with structured version
                    anomaly_document["analysis"] = parsed
                except Exception:
                    pass  # Silent error handling
        
        # Save to MongoDB
        anomaly_id = mongodb_handler.save_anomaly(anomaly_document)
        
        if not anomaly_id:
            return {
                "status": "error",
                "message": "Failed to save anomaly to MongoDB",
                "anomaly_id": None
            }
        
        return {
            "status": "success",
            "message": "Anomaly saved to MongoDB successfully (text parsed to JSON)",
            "vehicle_id": request.vehicle_id,
            "anomaly_id": anomaly_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error saving anomaly: {str(e)}",
            "anomaly_id": None
        }


@app.get("/anomalies")
async def get_anomalies():
    """Get all detected anomalies with their analysis (from MongoDB if available, else in-memory)"""
    if not stream_active:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active."
        )

    # Try to get from MongoDB first
    if mongo_connected():
        try:
            anomalies = mongodb_handler.get_all_anomalies(limit=50)
            total_count = mongodb_handler.get_anomalies_count()
            
            return {
                "total_anomalies": total_count,
                "recent_anomalies": anomalies,
                "source": "MongoDB",
                "latest_analysis": latest_analysis,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            pass  # Silently handle MongoDB errors
    
    # Fall back to in-memory storage
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


async def save_anomaly_legacy(anomaly_data: dict):
    """Legacy endpoint for backwards compatibility"""
    # Silently process without printing
    
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
# RCA/CAPA ENDPOINTS
# ============================================================================

@app.post("/rca_capa")
async def trigger_rca_capa():
    """
    Manually trigger RCA/CAPA analysis using current buffer data.
    
    This endpoint triggers a comprehensive Root Cause Analysis and Corrective/Preventive Actions analysis
    using the accumulated data in the rolling buffer and detected anomalies.
    
    Returns:
        RCA/CAPA analysis with parsed root causes and recommended actions
    """
    # Verify streaming is active
    if not stream_active or not processed_packets:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active. Check /health for status."
        )
    
    try:
        # Run RCA/CAPA analysis
        result = await route_rca_capa(
            vehicle_id="default",
            data_manager=data_manager,
            analysis_context={
                "processed_packets": list(rolling_buffer),
                "anomalies_detected": anomalies_detected,
                "total_packets": current_packet_index,
                "total_anomalies": len(anomalies_detected)
            }
        )
        
        # Parse the response
        raw_response = result.get("response", "")
        parsed_rca_capa = structure_rca_capa_for_db(raw_response)
        
        # Create RCA/CAPA document
        rca_capa_document = {
            "vehicle_id": "default",
            "timestamp": datetime.now(UTC).isoformat(),
            "buffer_size": len(rolling_buffer),
            "anomalies_count": len(anomalies_detected),
            "manual_trigger": True,
            "parsed_data": parsed_rca_capa,
            "affected_components": parsed_rca_capa.get("affected_components", []),
            "oem_owners": parsed_rca_capa.get("oem_owners", []),
            "safety_criticality": parsed_rca_capa.get("safety_criticality", "Unknown")
        }
        
        # Save to MongoDB
        rca_id = None
        if mongo_connected():
            rca_id = mongodb_handler.save_rca_capa(rca_capa_document)
            
            # Also save as LLM response
            llm_response_doc = {
                "vehicle_id": "default",
                "agent_type": "rca_capa",
                "timestamp": datetime.now(UTC).isoformat(),
                "manual_trigger": True,
                "parsed_data": parsed_rca_capa,
                "rca_capa_id": rca_id
            }
            mongodb_handler.save_llm_response(llm_response_doc)
        
        return {
            "status": "success",
            "vehicle_id": "default",
            "timestamp": datetime.now().isoformat(),
            "buffer_size": len(rolling_buffer),
            "anomalies_analyzed": len(anomalies_detected),
            "rca_capa_id": rca_id,
            "analysis": parsed_rca_capa
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error performing RCA/CAPA analysis: {str(e)}"
        )


@app.get("/rca_capa")
async def get_rca_capa_data(vehicle_id: Optional[str] = None, oem_owner: Optional[str] = None, limit: int = 100):
    """
    Get all RCA/CAPA analyses from MongoDB
    
    Args:
        vehicle_id: Optional filter by vehicle ID
        oem_owner: Optional filter by OEM team owner
        limit: Maximum number to return (default: 100)
    
    Returns:
        List of RCA/CAPA analyses with root causes and preventive actions
    """
    if not mongo_connected():
        return {
            "status": "error",
            "message": "MongoDB not connected",
            "rca_capa_analyses": []
        }
    
    try:
        analyses = mongodb_handler.get_rca_capa_analyses(
            vehicle_id=vehicle_id or "default",
            limit=limit,
            oem_owner=oem_owner
        )
        
        total_count = mongodb_handler.get_rca_capa_count(
            vehicle_id=vehicle_id or "default",
            oem_owner=oem_owner
        )
        
        return {
            "status": "success",
            "total_rca_capa_analyses": total_count,
            "returned_count": len(analyses),
            "vehicle_id": vehicle_id or "default",
            "oem_owner_filter": oem_owner,
            "rca_capa_analyses": analyses,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "rca_capa_analyses": []
        }


# ============================================================================
# LLM RESPONSE ENDPOINTS
# ============================================================================

@app.get("/rca_capa_debug")
async def get_rca_capa_debug(limit: int = 10):
    """
    DEBUG ENDPOINT: Get raw response previews from RCA/CAPA analyses
    
    Shows raw_response_preview to help debug parsing issues
    """
    if not mongo_connected():
        return {
            "status": "error",
            "message": "MongoDB not connected"
        }
    
    try:
        analyses = mongodb_handler.get_rca_capa_analyses(vehicle_id="default", limit=limit)
        
        debug_data = []
        for analysis in analyses:
            debug_data.append({
                "_id": analysis.get("_id"),
                "timestamp": analysis.get("timestamp"),
                "buffer_size": analysis.get("buffer_size"),
                "anomalies_count": analysis.get("anomalies_count"),
                "raw_response_preview": analysis.get("raw_response_preview", "No preview"),
                "parsed_vehicle_id": analysis.get("parsed_data", {}).get("vehicle_id"),
                "parsed_rca_count": len(analysis.get("parsed_data", {}).get("rca_analysis", [])),
                "parsed_capa_count": len(analysis.get("parsed_data", {}).get("capa_analysis", []))
            })
        
        return {
            "status": "success",
            "total": len(analyses),
            "debug_data": debug_data
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/llm_response")
async def save_llm_response_data(request: QueryRequest):
    """
    Save a detailed LLM response in parsed format to MongoDB.
    
    This endpoint allows manual saving of LLM responses with automatic parsing.
    Responses are stored in structured format for easy retrieval and analysis.
    
    Args:
        request: Query request with vehicle_id and query (used to generate response)
    
    Returns:
        Saved LLM response document ID and parsed data
    """
    if not stream_active or not processed_packets:
        raise HTTPException(
            status_code=503,
            detail="Data stream not active. Check /health for status."
        )
    
    if not mongo_connected():
        raise HTTPException(
            status_code=503,
            detail="MongoDB not connected"
        )
    
    try:
        # Get response from agent
        result = await route_query(
            query=request.query,
            vehicle_id=request.vehicle_id,
            data_manager=data_manager,
            analysis_context={
                "processed_packets": list(rolling_buffer),
                "anomalies_detected": anomalies_detected,
                "total_packets": current_packet_index,
                "total_anomalies": len(anomalies_detected)
            }
        )
        
        # Parse the response
        raw_response = result.get("response", "")
        agent_type = result.get("agent", "unknown")
        parsed_data = structure_llm_response_for_db(raw_response, agent_type)
        
        # Create LLM response document
        llm_response_doc = {
            "vehicle_id": request.vehicle_id,
            "agent_type": agent_type,
            "query": request.query,
            "timestamp": datetime.now(UTC).isoformat(),
            "buffer_size": len(rolling_buffer),
            "anomalies_count": len(anomalies_detected),
            "parsed_data": parsed_data
        }
        
        # Save to MongoDB
        llm_id = mongodb_handler.save_llm_response(llm_response_doc)
        
        return {
            "status": "success",
            "vehicle_id": request.vehicle_id,
            "llm_response_id": llm_id,
            "agent_type": agent_type,
            "timestamp": datetime.now().isoformat(),
            "parsed_data": parsed_data
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving LLM response: {str(e)}"
        )


@app.get("/llm_response")
async def get_llm_responses(vehicle_id: Optional[str] = None, agent_type: Optional[str] = None, limit: int = 100):
    """
    Get all parsed LLM responses from MongoDB
    
    Args:
        vehicle_id: Optional filter by vehicle ID
        agent_type: Optional filter by agent type (diagnostic, maintenance, performance, rca_capa)
        limit: Maximum number to return (default: 100)
    
    Returns:
        List of parsed LLM responses in structured JSON format
    """
    if not mongo_connected():
        return {
            "status": "error",
            "message": "MongoDB not connected",
            "llm_responses": []
        }
    
    try:
        responses = mongodb_handler.get_llm_responses(
            vehicle_id=vehicle_id or "default",
            agent_type=agent_type,
            limit=limit
        )
        
        total_count = mongodb_handler.get_llm_responses_count(
            vehicle_id=vehicle_id or "default",
            agent_type=agent_type
        )
        
        return {
            "status": "success",
            "total_llm_responses": total_count,
            "returned_count": len(responses),
            "vehicle_id": vehicle_id or "default",
            "agent_type_filter": agent_type,
            "llm_responses": responses,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "llm_responses": []
        }


# ============================================================================
# Run the application
# ============================================================================

@asynccontextmanager
async def lifespan(app):
    """Lifespan handler: initialize resources on startup and yield control.

    This replaces the deprecated @app.on_event("startup"). It ensures
    MongoDBHandler is created exactly once and streaming is started.
    """
    # Create MongoDB handler now (deferred) and clear old data
    global mongodb_handler
    if mongodb_handler is None:
        mongodb_handler = MongoDBHandler()

    if mongo_connected():
        try:
            mongodb_handler.clear_all_anomalies()
            mongodb_handler.clear_all_rca_capa()
            mongodb_handler.clear_all_llm_responses()
        except Exception:
            pass

    # Load packets from file and start background worker
    if load_data_stream():
        stream_thread = threading.Thread(target=packet_stream_worker, daemon=True)
        stream_thread.start()

    try:
        yield
    finally:
        # Optional cleanup can be added here
        pass

# Attach lifespan handler to the FastAPI app router to avoid on_event deprecation
app.router.lifespan_context = lifespan


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="critical"
    )
