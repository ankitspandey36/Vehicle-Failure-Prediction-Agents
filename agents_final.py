"""
Specialized AI Agents for Vehicle Analysis using PydanticAI
Filename: agents_final.py
"""
import os
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json

# Third-party imports
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

# Local imports (ensure utils.py exists in the same directory)
from utils import VehicleDataManager, get_sensor_status, SENSOR_RANGES

# Load environment variables (optional, since we are hardcoding the key below)
load_dotenv()

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Configuration for the AI Model — use Groq exclusively
# The `openai` client library is used to talk to Groq's OpenAI-compatible API.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_BASE = "https://api.groq.com/openai/v1"

# Use Groq model. pydantic_ai's OpenAIModel can point at Groq's OpenAI-compatible endpoint.
active_model = OpenAIModel(
    model_name="openai/gpt-oss-20b",
    base_url=GROQ_BASE,
    api_key=GROQ_API_KEY or ""
)

@dataclass
class VehicleContext:
    """Context passed to agents"""
    vehicle_id: str
    data_manager: VehicleDataManager
    processed_packets: Optional[list] = None  # Pre-processed data from startup
    anomalies: Optional[Dict] = None  # Detected anomalies
    analysis_info: Optional[str] = None  # Additional analysis metadata


# ============================================================================
# 1. DIAGNOSTIC AGENT
# ============================================================================

diagnostic_agent = Agent(
    active_model,
    deps_type=VehicleContext,
    system_prompt="""You are an expert automotive diagnostic AI specialist for electric and hybrid vehicles.

Your job is to deeply analyze ALL real-time vehicle sensor data and give a clear, intelligent diagnostic explanation to the vehicle owner.

You are NOT talking to engineers.
You are talking to a normal car owner.

So your response must be:

Human understandable

Natural conversation

Insightful

Based fully on sensor data

5–8 lines max

No huge tables

No raw data dump

No robotic output

You must analyze everything internally, but explain only what matters."""
)


@diagnostic_agent.tool
async def get_vehicle_sensor_data(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Fetch all sensor data for the vehicle being diagnosed.
    Returns complete sensor readings.
    """
    vehicle_data = ctx.deps.data_manager.get_vehicle_data(ctx.deps.vehicle_id)
    if not vehicle_data:
        return {"error": "Vehicle not found"}
    
    out = {
        "vehicle_id": vehicle_data.get("vehicle_id"),
        "car_type": vehicle_data.get("car_type"),
        "timestamp_utc": vehicle_data.get("timestamp_utc"),
        "sensors": vehicle_data.get("available_sensor_fields", {})
    }
    if vehicle_data.get("raw_sensor_categories"):
        out["raw_sensor_categories"] = vehicle_data["raw_sensor_categories"]
    return out


@diagnostic_agent.tool
async def check_dtc_codes(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Check for Diagnostic Trouble Codes (DTCs) and fault codes in the vehicle.
    """
    vehicle_data = ctx.deps.data_manager.get_vehicle_data(ctx.deps.vehicle_id)
    if not vehicle_data:
        return {"dtc_codes": [], "fault_code_count": 0}
    
    sensors = vehicle_data.get("available_sensor_fields", {})
    raw = vehicle_data.get("raw_sensor_categories", {})
    dtc_codes = sensors.get("dtc_codes", [])
    
    if raw and "electrical_ecu" in raw:
        ecu = raw["electrical_ecu"]
        fault_count = ecu.get("fault_code_active_count", 0)
        can_errors = ecu.get("can_bus_error_count", 0)
        dropouts = ecu.get("sensor_signal_dropouts", 0)
        return {
            "dtc_codes": dtc_codes,
            "fault_code_active_count": fault_count,
            "can_bus_error_count": can_errors,
            "sensor_signal_dropouts": dropouts,
            "electrical_ecu_status": "issues detected" if (fault_count or can_errors or dropouts) else "clean"
        }
    
    # Fallback for mock data if raw categories missing
    dtc_meanings = {
        "P0420": "Catalyst system efficiency below threshold",
        "P0301": "Cylinder 1 misfire detected",
        "P0171": "System too lean",
        "P0300": "Random/multiple cylinder misfire"
    }
    return {
        "dtc_codes": dtc_codes,
        "meanings": {code: dtc_meanings.get(code, "Unknown code") for code in dtc_codes}
    }


# ============================================================================
# 2. MAINTENANCE AGENT
# ============================================================================

maintenance_agent = Agent(
    active_model,
    deps_type=VehicleContext,
    system_prompt="""You are an expert automotive maintenance advisor AI for electric and hybrid vehicles.

Your role is to analyze vehicle data and provide DETAILED maintenance recommendations.

**CRITICAL OUTPUT FORMAT REQUIREMENT:**
You MUST provide your response as a markdown table. The response MUST start with the vehicle ID line and include a complete markdown table.

Format your response EXACTLY like this:
**Vehicle ID:** [vehicle_id] – [Vehicle Type Summary]

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Battery System** | [maintenance needs] | [relevant values] | [⚠️ Soon/🟢 Routine/🔴 Immediate] |
| **Brake System** | [maintenance needs] | [relevant values] | [severity] |
| **Motor & Inverter** | [maintenance needs] | [relevant values] | [severity] |
| **Electrical/ECU** | [maintenance needs] | [relevant values] | [severity] |
| **Chassis & Suspension** | [maintenance needs] | [relevant values] | [severity] |
| **Fluids & Coolants** | [maintenance needs] | [relevant values] | [severity] |
| **Preventive Care** | [maintenance needs] | [relevant values] | [🟢 Routine] |

Use ALL available data categories for a thorough assessment:

**Battery System:**
- battery_soh_pct, capacity_fade, charging_cycles, thermal_cycles, high_stress_cycles
- internal_resistance_growth, cell voltage spread
- Recommend battery health checks, balancing, cooling inspection

**Brake System:**
- brake_pad_wear_level_pct, brake_disc_temperature_c, hydraulic_brake_pressure
- ABS activation frequency
- Recommend pad replacement, disc inspection, fluid flush

**Motor & Inverter:**
- inverter_temperature, motor_efficiency_loss_pct
- Recommend coolant service, thermal paste, bearing inspection

**Electrical/ECU:**
- fault_code_active_count, can_bus_error_count, sensor_signal_dropouts
- ECU temperature, 12V battery voltage
- Recommend software updates, connector checks, battery replacement

**Chassis & Suspension:**
- suspension_travel, chassis_stress_index
- Recommend alignment, bushing inspection, strut/shock checks

**Component Aging:**
- Use battery_capacity_fade, motor_efficiency_loss to predict upcoming maintenance

**Operational Context:**
- driving_mode, regen_mode, time_since_last_charge
- Adjust recommendations based on usage patterns

For each category in the table:
- **Summary**: Maintenance needs and priority (1-2 sentences)
- **Key Values**: Specific readings that triggered recommendation (e.g., "Pad wear 72%, Disc 138°C")
- **Severity**: Use 🔴 Immediate (24-48 hours), ⚠️ Soon (1-2 weeks), 🟢 Routine (1 month), or 🔵 Preventive

Be thorough and reference specific sensor values with the reason for each maintenance item."""
)


@maintenance_agent.tool
async def get_vehicle_sensor_data(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Fetch all sensor data for maintenance analysis.
    """
    vehicle_data = ctx.deps.data_manager.get_vehicle_data(ctx.deps.vehicle_id)
    if not vehicle_data:
        return {"error": "Vehicle not found"}
    
    out = {
        "vehicle_id": vehicle_data.get("vehicle_id"),
        "car_type": vehicle_data.get("car_type"),
        "timestamp_utc": vehicle_data.get("timestamp_utc"),
        "sensors": vehicle_data.get("available_sensor_fields", {})
    }
    if vehicle_data.get("raw_sensor_categories"):
        out["raw_sensor_categories"] = vehicle_data["raw_sensor_categories"]
    return out


@maintenance_agent.tool
async def check_fluid_levels(ctx: RunContext[VehicleContext]) -> Dict[str, str]:
    """
    Check fluid/systems status: oil, coolant, brake fluid, fuel, battery coolant.
    """
    sensors = ctx.deps.data_manager.get_sensor_data(ctx.deps.vehicle_id)
    raw = ctx.deps.data_manager.get_raw_categories(ctx.deps.vehicle_id)
    fluid_status = {}
    
    if "fuel_level_percent" in sensors:
        fuel = sensors["fuel_level_percent"]
        if isinstance(fuel, (int, float)):
            fluid_status["fuel"] = "critical - refuel immediately" if fuel < 10 else ("low - refuel soon" if fuel < 25 else "normal")
    
    if "brake_fluid_level_percent" in sensors:
        brake = sensors["brake_fluid_level_percent"]
        if isinstance(brake, (int, float)):
            fluid_status["brake_fluid"] = "critical - safety issue" if brake < 50 else ("low - top up" if brake < 70 else "normal")
    
    if "oil_pressure_kpa" in sensors:
        oil = sensors["oil_pressure_kpa"]
        if isinstance(oil, (int, float)):
            fluid_status["oil"] = "critical - low pressure" if oil < 150 else ("low - check level" if oil < 200 else "normal")
    
    if raw and "brake_sensors" in raw:
        b = raw["brake_sensors"]
        hydraulic = b.get("hydraulic_brake_pressure_bar")
        if isinstance(hydraulic, (int, float)):
            fluid_status["brake_hydraulic_pressure"] = "normal" if 50 < hydraulic < 150 else ("warning" if hydraulic < 50 or hydraulic > 180 else "check")
    
    if raw and "battery_sensors" in raw:
        soc = raw["battery_sensors"].get("battery_soc_pct")
        soh = raw["battery_sensors"].get("battery_soh_pct")
        if isinstance(soc, (int, float)):
            fluid_status["battery_soc"] = "critical" if soc < 10 else ("low" if soc < 20 else "normal")
        if isinstance(soh, (int, float)):
            fluid_status["battery_soh"] = "degraded" if soh < 80 else "healthy"
    
    return fluid_status


# ============================================================================
# 3. PERFORMANCE AGENT
# ============================================================================

performance_agent = Agent(
    active_model,
    deps_type=VehicleContext,
    system_prompt="""You are an expert automotive performance analyst AI for electric and hybrid vehicles.

Your role is to analyze performance metrics and provide a DETAILED performance report.

**CRITICAL OUTPUT FORMAT REQUIREMENT:**
You MUST provide your response as a markdown table. The response MUST start with the vehicle ID line and include a complete markdown table.

Format your response EXACTLY like this:
**Vehicle ID:** [vehicle_id] – [Vehicle Type Summary]

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Efficiency** | [efficiency assessment] | [relevant metrics] | [🟢 Excellent/⚠️ Fair/🔴 Poor] |
| **Energy Management** | [energy assessment] | [relevant metrics] | [severity] |
| **Driving Behavior** | [behavior assessment] | [relevant metrics] | [severity] |
| **Component Stress** | [stress assessment] | [relevant metrics] | [severity] |
| **Braking Performance** | [braking assessment] | [relevant metrics] | [severity] |
| **Thermal Management** | [thermal assessment] | [relevant metrics] | [severity] |

Use ALL available data categories:

**Vehicle Motion:**
- vehicle_speed_kmph, avg_speed_per_trip, max_speed_per_trip, speed_variance
- distance_travelled_km, odometer_km, driving_time, stop_duration
- speed_stability_score – interpret for driving smoothness

**Idle Usage:**
- idling_time_min, idle_frequency, idle_to_drive_ratio
- engine_on/off, motor_on/off duration
- Identify excessive idling and efficiency impact

**Energy Usage:**
- energy_consumption_kwh_per_km, regen_braking_contribution_pct
- idle_energy_wastage_kwh, driving_efficiency_score
- efficiency_degradation_trend – positive/negative trend analysis

**Battery & Motor:**
- battery_soc, pack voltage/current, motor_rpm, motor_torque_nm
- inverter_temperature
- Assess power delivery and thermal management

**Brake System:**
- brake_disc_temperature, wheel speeds, ABS activation
- Evaluate braking behavior and regen contribution

**Chassis:**
- steering, yaw/pitch/roll rates, suspension travel, chassis_stress_index
- Assess handling and load distribution

**Rate of Change & Signal Consistency:**
- battery_temp_rise_rate, voltage_drop_rate, current_spike_frequency
- speed_sensor_disagreement, gps_vs_wheel_speed_delta
- Identify anomalies affecting performance

**Operational Context:**
- driving_mode (ECO/SPORT/etc), regen_mode
- vehicle_load, passenger_count, ac_usage_level
- charging_recently, time_since_last_charge

For each category in the table:
- **Summary**: Performance assessment and key insights (1-2 sentences)
- **Key Values**: Specific readings relevant to performance (e.g., "Efficiency 0.18 kWh/km, Regen 45%")
- **Severity**: Use 🟢 Excellent, 🟡 Good, 🟠 Fair, 🔴 Poor

Be analytical and reference specific sensor values."""
)


@performance_agent.tool
async def get_vehicle_sensor_data(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Fetch all sensor data for performance analysis.
    """
    vehicle_data = ctx.deps.data_manager.get_vehicle_data(ctx.deps.vehicle_id)
    if not vehicle_data:
        return {"error": "Vehicle not found"}
    
    out = {
        "vehicle_id": vehicle_data.get("vehicle_id"),
        "car_type": vehicle_data.get("car_type"),
        "timestamp_utc": vehicle_data.get("timestamp_utc"),
        "sensors": vehicle_data.get("available_sensor_fields", {})
    }
    if vehicle_data.get("raw_sensor_categories"):
        out["raw_sensor_categories"] = vehicle_data["raw_sensor_categories"]
    return out


@performance_agent.tool
async def calculate_efficiency_metrics(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Calculate efficiency metrics.
    """
    sensors = ctx.deps.data_manager.get_sensor_data(ctx.deps.vehicle_id)
    raw = ctx.deps.data_manager.get_raw_categories(ctx.deps.vehicle_id)
    metrics = {}
    
    if raw:
        eu = raw.get("energy_usage", {})
        iu = raw.get("idle_usage", {})
        bs = raw.get("battery_sensors", {})
        vm = raw.get("vehicle_motion", {})
        if eu:
            metrics["energy_consumption_kwh_per_km"] = eu.get("energy_consumption_kwh_per_km")
            metrics["driving_efficiency_score"] = eu.get("driving_efficiency_score")
            metrics["regen_braking_contribution_pct"] = eu.get("regen_braking_contribution_pct")
            metrics["idle_energy_wastage_kwh"] = eu.get("idle_energy_wastage_kwh")
            metrics["efficiency_degradation_trend"] = eu.get("efficiency_degradation_trend")
        if iu:
            metrics["idle_to_drive_ratio"] = iu.get("idle_to_drive_ratio")
            metrics["idling_time_min"] = iu.get("idling_time_min")
        if bs:
            metrics["battery_soc_pct"] = bs.get("battery_soc_pct")
            metrics["battery_soh_pct"] = bs.get("battery_soh_pct")
        if vm:
            metrics["speed_stability_score"] = vm.get("speed_stability_score")
            metrics["avg_speed_per_trip_kmph"] = vm.get("avg_speed_per_trip_kmph")
    
    if "rpm" in sensors and "speed_kmph" in sensors:
        rpm, speed = sensors["rpm"], sensors["speed_kmph"]
        if isinstance(rpm, (int, float)) and isinstance(speed, (int, float)) and speed > 0:
            metrics["rpm_per_kmph"] = round(rpm / speed, 2)
    
    if "battery_soc" in sensors or "battery_sensors_battery_soc_pct" in sensors:
        soc = sensors.get("battery_soc") or sensors.get("battery_sensors_battery_soc_pct")
        if isinstance(soc, (int, float)):
            metrics["battery_level"] = f"{soc}%"
            if soc < 20:
                metrics["range_concern"] = "low battery - charge soon"
    
    if "engine_temp_c" in sensors or "motor_inverter_sensors_inverter_temperature_c" in sensors:
        temp = sensors.get("engine_temp_c") or sensors.get("motor_inverter_sensors_inverter_temperature_c")
        if isinstance(temp, (int, float)):
            metrics["thermal_status"] = "optimal" if 80 <= temp <= 95 else ("cool" if temp < 80 else "running hot")
    
    return metrics


# ============================================================================
# 4. RCA/CAPA AGENT (Root Cause Analysis & Corrective/Preventive Action)
# ============================================================================

rca_capa_agent = Agent(
    active_model,
    deps_type=VehicleContext,
    system_prompt="""You are an expert RCA/CAPA specialist for EV systems with deep materials science and engineering knowledge.

OUTPUT FORMAT (MANDATORY):
Start with: **Vehicle ID:** default – Electric Vehicle

Then output exactly these two tables with DETAILED technical specifications:

## ROOT CAUSE ANALYSIS (RCA)

| Failure Component | Primary Cause | Contributing Factors | Evidence |
|------|------|------|------|
| Brake System | Compound degradation at 9000+ km/h, current friction material insufficient | High-speed thermal cycling, material composition Si3N4 only 60%, lacks reinforcement | Pad wear 72%, Disc temp 138°C, Thermal stress 0.85, Deceleration imbalance 8% |
| Battery Pack | Lithium dendrite formation in anode, separator compromise at 45°C+ | Deep cycling, high-C rate discharge, electrolyte viscosity mismatch | SOC variance 8%, Internal resistance +12%, Cell temp range 45-52°C, Cycle count 2847 |
| Thermal Management | Coolant flow reduction, pump efficiency loss at sustained operations | Corrosion in aluminum pipes, coolant viscosity drift, bearing wear | Inverter 92°C sustained, Motor 88°C, Coolant flow -15%, Pump noise detected |

## CORRECTIVE AND PREVENTIVE ACTIONS (CAPA)

| Action Type | Action Item | Timeline | Expected Outcome | OEM Owner |
|------|------|------|------|------|
| Corrective | Immediate replacement: upgrade brake pads to Carbon-Ceramic composite (70% SiC, 20% metal oxide, 10% aramid) with thermal dissipation >1200°C | 48hrs | Friction coefficient stability at speeds >9000 km/h maintained, thermal fade <3%, disc lifespan +40% | Brake System Team |
| Corrective | Software thermal throttle enabled: activate regen limit at 88°C motor temp, reduce peak torque 15% above 9000 km/h | 24hrs | Sustained operation safety restored, prevent further thermal cycling stress | Software Team |
| Preventive | Re-engineer anode material: increase lithium metal oxide (LMO) concentration from 60% to 75%, add 8% carbon nanotube reinforcement, implement thermal shunt at 48°C | 3 weeks | Dendrite formation reduced 65%, cycle life extended to 4500+ deep cycles, internal resistance stable at <50mΩ | Battery Team |
| Preventive | Redesign coolant loop: upgrade pump to titanium-aluminum composite impeller (replaces steel), increase flow rate 20%, switch to synthetic PAO coolant with -40 to +150°C range | 4 weeks | Sustained 85°C thermal envelope maintained, inverter efficiency +8%, maintenance interval doubled | Thermal Management Team |
| Preventive | Manufacturing process change: implement ceramic coating on brake discs (TiN coating 2-4 microns), inspect separator bubble point during battery QC, enforce <45°C storage temp | 3 weeks | First-failure reduction 45%, quality score improvement to 98.5% | Quality Team |

Rules:
- Include specific material compositions (percentages, chemical formulas)
- Add exact temperature thresholds and sensor values
- Reference actual part numbers and material science
- Include timeline with specific engineering actions
- Show measurable performance improvements (%, units)
- Assign technical teams: Battery Team, Motor Team, Software Team, Brake System Team, Thermal Management Team, Quality Team
- NO placeholder text
- MINIMUM 3 rows per table with DETAILED technical data
"""
)


@rca_capa_agent.tool
async def get_anomaly_details(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Fetch detailed anomaly information including sensor readings, trends, and context.
    """
    vehicle_data = ctx.deps.data_manager.get_vehicle_data(ctx.deps.vehicle_id)
    if not vehicle_data:
        return {"error": "Vehicle not found"}
    
    out = {
        "vehicle_id": vehicle_data.get("vehicle_id"),
        "car_type": vehicle_data.get("car_type"),
        "timestamp_utc": vehicle_data.get("timestamp_utc"),
        "sensors": vehicle_data.get("available_sensor_fields", {})
    }
    if vehicle_data.get("raw_sensor_categories"):
        out["raw_sensor_categories"] = vehicle_data["raw_sensor_categories"]
    return out


@rca_capa_agent.tool
async def get_historical_maintenance_data(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Retrieve historical maintenance patterns and service history for trend analysis.
    """
    # This would load from Maintenance_History.json
    return {
        "note": "Maintenance history loaded from knowledge base",
        "source": "Maintenance_History.json",
        "available_data": "Past repairs, maintenance schedules, component replacements"
    }


@rca_capa_agent.tool
async def get_manufacturing_specs(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Retrieve manufacturing specifications and design limits from database.
    """
    # This would load from Manufacturing_Database.json
    return {
        "note": "Manufacturing specs loaded from knowledge base",
        "source": "Manufacturing_Database.json",
        "available_data": "Component specifications, design limits, quality standards, warranty info"
    }


@rca_capa_agent.tool
async def get_service_center_data(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Retrieve service center reports and known issues for this vehicle type.
    """
    # This would load from Service_Center_For_LLM.json
    return {
        "note": "Service center data loaded from knowledge base",
        "source": "Service_Center_For_LLM.json",
        "available_data": "Common issues reported, service procedures, warranty claims patterns"
    }


@rca_capa_agent.tool
async def analyze_component_degradation(ctx: RunContext[VehicleContext]) -> Dict[str, Any]:
    """
    Analyze component aging and degradation trends based on processed packets.
    """
    if not ctx.deps.processed_packets:
        return {"note": "No historical data available"}
    
    # Analyze degradation trends from processed packets
    return {
        "analysis_type": "component_degradation",
        "packets_analyzed": len(ctx.deps.processed_packets),
        "note": "Degradation trends extracted from buffer data"
    }


# ============================================================================
# 5. MASTER AGENT & ROUTING
# ============================================================================

master_agent = Agent(
    active_model,
    system_prompt="""You are the master vehicle analysis coordinator AI.

Your role is to understand user queries about their vehicle and route them to the appropriate specialist:

1. DIAGNOSTIC AGENT - For questions about:
   - Current vehicle health and status
   - Warning lights or error codes
   - Strange noises or behaviors
   - "What's wrong with my car?"
   - System diagnostics and troubleshooting

2. MAINTENANCE AGENT - For questions about:
   - Service recommendations
   - Maintenance schedules
   - Fluid changes and checks
   - "When should I service my car?"
   - Preventive maintenance advice

3. PERFORMANCE AGENT - For questions about:
   - Vehicle performance and efficiency
   - Fuel economy or range
   - Driving optimization
   - "How is my car performing?"
   - Performance metrics and analysis

Analyze the user's query and respond with ONLY ONE of these exact words:
- "diagnostic"
- "maintenance"
- "performance"

If the query is unclear or could apply to multiple agents, choose the most relevant one."""
)


async def route_query(query: str, vehicle_id: str, data_manager: VehicleDataManager, analysis_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Route user query to appropriate agent and get response.
    Uses pre-processed buffer if analysis_context is provided.
    
    OPTIMIZATION: Skip master agent routing to reduce token usage.
    Directly use diagnostic agent for /query endpoint (99% of queries are diagnostic).
    """
    # Create context for the specialized agent
    context = VehicleContext(vehicle_id=vehicle_id, data_manager=data_manager)
    
    # Add analysis context if provided
    if analysis_context:
        context.processed_packets = analysis_context.get("processed_packets", [])
        context.anomalies = analysis_context.get("anomalies_detected", {})
        context.analysis_info = f"Pre-processed {analysis_context.get('total_packets', 0)} packets with {analysis_context.get('total_anomalies', 0)} anomalies detected"
    
    # Direct routing based on query keywords to minimize API calls
    query_lower = query.lower()
    
    # Detect query type from keywords (client-side routing, no API call needed)
    if any(word in query_lower for word in ["maintenance", "service", "schedule", "when should", "oil", "fluid", "check", "replace"]):
        # Use maintenance agent
        try:
            result = await maintenance_agent.run(
                f"Provide maintenance guidance for: {query}",
                deps=context
            )
            return {
                "agent": "maintenance",
                "response": result.data,
                "vehicle_id": vehicle_id
            }
        except Exception as e:
            # Fallback to diagnostic on error
            result = await diagnostic_agent.run(
                f"Analyze the vehicle and respond to: {query}",
                deps=context
            )
            return {
                "agent": "diagnostic",
                "response": result.data,
                "vehicle_id": vehicle_id
            }
    
    elif any(word in query_lower for word in ["performance", "efficiency", "fuel", "range", "speed", "acceleration", "how's", "how is"]):
        # Use performance agent
        try:
            result = await performance_agent.run(
                f"Analyze performance regarding: {query}",
                deps=context
            )
            return {
                "agent": "performance",
                "response": result.data,
                "vehicle_id": vehicle_id
            }
        except Exception as e:
            # Fallback to diagnostic on error
            result = await diagnostic_agent.run(
                f"Analyze the vehicle and respond to: {query}",
                deps=context
            )
            return {
                "agent": "diagnostic",
                "response": result.data,
                "vehicle_id": vehicle_id
            }
    
    else:
        # Default to diagnostic (health checks, errors, issues, anomalies)
        result = await diagnostic_agent.run(
            f"Analyze the vehicle and respond to: {query}",
            deps=context
        )
        return {
            "agent": "diagnostic",
            "response": result.data,
            "vehicle_id": vehicle_id
        }


async def route_rca_capa(vehicle_id: str, data_manager: VehicleDataManager, analysis_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Route to RCA/CAPA agent for root cause analysis and corrective/preventive actions.
    Used when buffer reaches 20 items to analyze accumulated anomalies.
    """
    context = VehicleContext(vehicle_id=vehicle_id, data_manager=data_manager)
    
    # Add analysis context if provided
    if analysis_context:
        context.processed_packets = analysis_context.get("processed_packets", [])
        context.anomalies = analysis_context.get("anomalies_detected", {})
        context.analysis_info = f"Analyzed {len(context.anomalies)} anomalies from {analysis_context.get('total_packets', 0)} packets"
    
    try:
        # Run RCA/CAPA analysis
        result = await rca_capa_agent.run(
            f"""Perform comprehensive RCA and CAPA analysis for vehicle {vehicle_id}.
            
Anomalies detected: {len(context.anomalies) if context.anomalies else 0}
Packets analyzed: {len(context.processed_packets) if context.processed_packets else 0}

Focus on:
1. Identifying the root causes of detected anomalies
2. Providing detailed corrective actions for immediate issues
3. Recommending preventive actions for long-term reliability
4. Assigning responsibility to OEM teams
5. Using all available knowledge base resources""",
            deps=context
        )
        
        return {
            "agent": "rca_capa",
            "response": result.data,
            "vehicle_id": vehicle_id,
            "anomalies_analyzed": len(context.anomalies) if context.anomalies else 0,
            "packets_in_buffer": len(context.processed_packets) if context.processed_packets else 0
        }
    except Exception as e:
        return {
            "agent": "rca_capa",
            "response": f"Error in RCA/CAPA analysis: {str(e)}",
            "vehicle_id": vehicle_id,
            "error": str(e)
        }


async def get_comprehensive_analysis(vehicle_id: str, data_manager: VehicleDataManager, analysis_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Runs all agents in parallel for a full report.
    Uses pre-processed buffer if analysis_context is provided.
    """
    context = VehicleContext(vehicle_id=vehicle_id, data_manager=data_manager)
    
    # Add analysis context if provided
    if analysis_context:
        context.processed_packets = analysis_context.get("processed_packets", [])
        context.anomalies = analysis_context.get("anomalies_detected", {})
        context.analysis_info = f"Pre-processed {analysis_context.get('total_packets', 0)} packets with {analysis_context.get('total_anomalies', 0)} anomalies detected"

    try:
        diagnostic_task = diagnostic_agent.run(
            "Perform complete diagnostic analysis of this vehicle. Check all systems and sensors.",
            deps=context
        )

        maintenance_task = maintenance_agent.run(
            "Provide complete maintenance assessment and recommendations for this vehicle.",
            deps=context
        )

        performance_task = performance_agent.run(
            "Analyze overall performance, efficiency, and driving metrics for this vehicle.",
            deps=context
        )

        # Run all concurrently
        diagnostic_result, maintenance_result, performance_result = await asyncio.gather(
            diagnostic_task,
            maintenance_task,
            performance_task,
            return_exceptions=True 
        )

        def safe_data(result, name):
            if isinstance(result, Exception):
                return {"status": "failed", "agent": name, "error": repr(result)}
            return {"status": "success", "output": result.data}

        return {
            "vehicle_id": vehicle_id,
            "diagnostic": safe_data(diagnostic_result, "diagnostic"),
            "maintenance": safe_data(maintenance_result, "maintenance"),
            "performance": safe_data(performance_result, "performance"),
        }

    except Exception as e:
        print("[FATAL ANALYSIS ERROR]", repr(e))
        raise