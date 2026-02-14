# RCA/CAPA Agent Integration Guide

## Overview
A new Root Cause Analysis (RCA) and Corrective/Preventive Action (CAPA) agent has been integrated into the existing vehicle analysis system. This agent triggers automatically when the rolling buffer reaches 20 items and provides detailed analysis without running continuously.

## What Was Added

### 1. New RCA/CAPA Agent (`agents_final.py`)
- **Agent Name**: `rca_capa_agent`
- **Purpose**: Performs comprehensive root cause analysis and recommends corrective and preventive actions
- **Knowledge Base**: Uses Maintenance_History.json, Manufacturing_Database.json, and Service_Center_For_LLM.json
- **Tools**: 
  - `get_anomaly_details()` - Fetch current anomaly information
  - `get_historical_maintenance_data()` - Historical patterns
  - `get_manufacturing_specs()` - Design specifications
  - `get_service_center_data()` - Known issues and service procedures
  - `analyze_component_degradation()` - Component aging analysis

### 2. RCA/CAPA Routing Function (`agents_final.py`)
- **Function**: `route_rca_capa()`
- **Input**: Vehicle ID, data manager, analysis context
- **Output**: Structured RCA/CAPA analysis with root causes and recommended actions
- **Automatic Triggering**: Triggered when buffer reaches 20 items during streaming

### 3. MongoDB Collections (`mongodb_handler.py`)
- **New Collections**:
  - `rca_capa` - Stores RCA/CAPA analyses
  - `llm_responses` - Stores all parsed LLM responses (diagnostic, maintenance, performance, rca_capa)
- **New Methods**:
  - `save_rca_capa()` - Save RCA/CAPA analysis to DB
  - `get_rca_capa_analyses()` - Retrieve RCA/CAPA analyses (with filters)
  - `save_llm_response()` - Save parsed LLM response to DB
  - `get_llm_responses()` - Retrieve LLM responses (with filters)
  - `get_rca_capa_count()` - Get count of RCA/CAPA documents
  - `get_llm_responses_count()` - Get count of LLM responses

### 4. Response Parsing Functions (`response_parser.py`)
- **New Functions**:
  - `parse_rca_table()` - Parse RCA markdown table
  - `parse_capa_table()` - Parse CAPA markdown table
  - `parse_rca_capa_response()` - Complete RCA/CAPA response parsing
  - `structure_rca_capa_for_db()` - Prepare RCA/CAPA for MongoDB storage
  - `structure_llm_response_for_db()` - Universal LLM response parser

### 5. Main Application Logic (`main.py`)

#### New Global Variable
- `rca_capa_triggered`: Tracks whether RCA/CAPA has been triggered for current buffer

#### New Function
- `trigger_rca_capa_analysis()`: Async function that:
  - Analyzes accumulated anomalies
  - Parses RCA/CAPA response
  - Saves to MongoDB (both RCA/CAPA and LLM response collections)
  - Updates latest_analysis

#### Integration in Packet Stream Worker
- Checks buffer size after each packet
- When buffer reaches 20 items AND hasn't triggered yet: Calls `trigger_rca_capa_analysis()`
- Resets flag when buffer drops below 20 items
- **Does NOT run continuously** - only triggers once per buffer cycle

#### New API Endpoints

##### RCA/CAPA Endpoints
- **POST /rca_capa** - Manually trigger RCA/CAPA analysis
  - Input: (none, uses current buffer)
  - Output: RCA/CAPA analysis with parsed data, affected components, OEM owners
  
- **GET /rca_capa** - Retrieve RCA/CAPA analyses
  - Parameters: `vehicle_id`, `oem_owner`, `limit`
  - Output: List of RCA/CAPA documents with root causes and preventive actions

##### LLM Response Endpoints
- **POST /llm_response** - Save detailed LLM response
  - Input: QueryRequest (vehicle_id, query)
  - Output: Parsed LLM response with agent type and extracted data
  
- **GET /llm_response** - Retrieve parsed LLM responses
  - Parameters: `vehicle_id`, `agent_type` (diagnostic/maintenance/performance/rca_capa), `limit`
  - Output: List of parsed LLM responses

## How It Works

### Automatic Triggering (No Continuous Running)
1. System streams packets at 1 packet/sec
2. Each packet is added to rolling_buffer (max 300 items)
3. When buffer reaches 20 items:
   - RCA/CAPA analysis is triggered automatically
   - `rca_capa_triggered` flag is set to prevent repeated triggers
4. When buffer drops below 20 items:
   - Flag is reset for next cycle
5. RCA/CAPA only runs ONCE per buffer cycle (not continuously)

### Data Stored in MongoDB

**RCA/CAPA Document Structure**:
```json
{
  "vehicle_id": "default",
  "timestamp": "ISO_TIMESTAMP",
  "buffer_size": 20,
  "anomalies_count": 5,
  "manual_trigger": false,
  "parsed_data": {
    "vehicle_id": "default",
    "rca_analysis": [...],  // Array of RCA entries
    "capa_analysis": [...], // Array of CAPA entries
    "affected_components": ["Battery", "Motor"],
    "oem_owners": ["Battery Team", "Software Team"],
    "safety_criticality": "High"
  },
  "affected_components": [...],
  "oem_owners": [...],
  "safety_criticality": "High"
}
```

**LLM Response Document Structure**:
```json
{
  "vehicle_id": "default",
  "agent_type": "rca_capa",
  "query": "Analyze anomalies",
  "timestamp": "ISO_TIMESTAMP",
  "buffer_size": 20,
  "anomalies_count": 5,
  "parsed_data": {
    "vehicle_id": "default",
    "rca_analysis": [...],
    "capa_analysis": [...],
    ...
  }
}
```

## Parsing Format

RCA/CAPA responses are parsed from markdown tables into structured JSON:

**RCA Table Columns**: Failure Component | Primary Cause | Contributing Factors | Evidence

**CAPA Table Columns**: Action Type | Action Item | Timeline | Expected Outcome | OEM Owner

All table data is extracted and stored as JSON arrays for easy querying and filtering.

## Knowledge Base Integration

The RCA/CAPA agent uses:
1. **Maintenance_History.json** - Historical maintenance patterns
2. **Manufacturing_Database.json** - Component specs and design limits
3. **Service_Center_For_LLM.json** - Common issues and service procedures
4. **Analysis from existing agents** - Current diagnostic data

These are referenced as tools within the agent context.

## API Usage Examples

### Trigger RCA/CAPA Analysis
```bash
POST /rca_capa
```

### Get RCA/CAPA Analyses
```bash
GET /rca_capa?vehicle_id=default&limit=50
GET /rca_capa?oem_owner=Battery%20Team
```

### Save LLM Response
```bash
POST /llm_response
Body: {
  "vehicle_id": "default",
  "query": "Analyze vehicle health"
}
```

### Get LLM Responses
```bash
GET /llm_response?vehicle_id=default&agent_type=rca_capa&limit=100
```

## Configuration Notes

- **Buffer Trigger Size**: 20 items (configurable by changing the condition in packet_stream_worker)
- **Trigger Frequency**: Once per buffer cycle (when crossing 20 items threshold)
- **MongoDB Collections**: Automatically created on first write
- **No Continuous Running**: RCA/CAPA only executes when triggered, never in a loop

## Existing APIs Not Modified

All existing APIs remain unchanged:
- `/query` - Route user queries to agents
- `/analyze` - Get comprehensive analysis
- `/status` - System status
- `/health` - Health check
- `/vehicles` - List vehicles
- etc.

## Integration with Existing System

- ✅ Uses same knowledge base files (no changes to data)
- ✅ Uses existing MongoDB handler with new collections
- ✅ Uses existing response parsing framework
- ✅ Integrated into packet streaming worker (no separate process)
- ✅ Follows same parsing format as diagnostic/maintenance agents
- ✅ No modifications to existing APIs
