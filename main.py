"""
FastAPI application for vehicle analysis and maintenance system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime

from agents_final import route_query, get_comprehensive_analysis
from utils import VehicleDataManager, AnalysisLogger


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
data_manager = VehicleDataManager()
logger = AnalysisLogger()


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
                "vehicle_id": "VH001",
                "query": "Is my car healthy? Any issues I should be concerned about?"
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
    vehicle_id: str = Field(..., description="Vehicle identifier (e.g., VH001)")


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
        "endpoints": {
            "POST /query": "Ask questions about a specific vehicle",
            "POST /analyze": "Get comprehensive analysis of a vehicle",
            "GET /vehicles": "List all available vehicles",
            "GET /vehicle/{vehicle_id}": "Get vehicle data",
            "GET /health": "API health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_vehicles": len(data_manager.get_all_vehicles())
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
    Ask a question about a specific vehicle.
    
    The master agent will automatically route your query to the appropriate specialist:
    - Diagnostic Agent: For health checks, error codes, issues
    - Maintenance Agent: For service recommendations, maintenance schedules
    - Performance Agent: For efficiency, performance metrics
    
    Example queries:
    - "Is my car healthy?"
    - "What maintenance does my car need?"
    - "How's my fuel efficiency?"
    - "Check engine light is on, what's wrong?"
    """
    # Verify vehicle exists
    vehicle_data = data_manager.get_vehicle_data(request.vehicle_id)
    if not vehicle_data:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {request.vehicle_id} not found. Use /vehicles to see available vehicles."
        )
    
    try:
        # Route query to appropriate agent
        result = await route_query(
            query=request.query,
            vehicle_id=request.vehicle_id,
            data_manager=data_manager
        )
        
        # Log the analysis
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": request.vehicle_id,
            "query": request.query,
            "agent": result["agent"],
            "response": result["response"]
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
    Get comprehensive analysis from all agents.
    
    This runs diagnostic, maintenance, and performance analysis on the vehicle
    and returns a complete health report.
    
    Useful for:
    - Scheduled maintenance checks
    - Pre-purchase inspections
    - Comprehensive health reports
    """
    # Verify vehicle exists
    vehicle_data = data_manager.get_vehicle_data(request.vehicle_id)
    if not vehicle_data:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {request.vehicle_id} not found. Use /vehicles to see available vehicles."
        )
    
    try:
        # Get comprehensive analysis
        result = await get_comprehensive_analysis(
            vehicle_id=request.vehicle_id,
            data_manager=data_manager
        )
        
        # Log the analysis
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": request.vehicle_id,
            "type": "comprehensive_analysis",
            "result": result
        }
        logger.save_analysis(log_entry)
        
        return {
            "vehicle_id": request.vehicle_id,
            "timestamp": datetime.now().isoformat(),
            "analysis": result
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error performing analysis: {str(e)}"
        )


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

if __name__ == "__main__":
    import uvicorn
    
    # Check for Gemini API key
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY environment variable not set!")
        print("Please set it with: export GEMINI_API_KEY='your-api-key'")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
