"""
Test script to verify agents produce properly formatted markdown table output
"""

import asyncio
import json
from dotenv import load_dotenv
from agents_final import diagnostic_agent, maintenance_agent, performance_agent, route_query, VehicleContext
from utils import VehicleDataManager

load_dotenv()

# Sample vehicle data for testing
SAMPLE_DATA = {
    "default": {
        "vehicle_id": "default",
        "car_type": "Electric Vehicle",
        "timestamp_utc": "2026-01-29T09:18:13Z",
        "available_sensor_fields": {
            "battery_soc_pct": 67.68,
            "battery_soh_pct": 96.8,
            "pack_voltage_v": 371.1,
            "pack_current_a": 114.0,
            "battery_temp_avg_c": 33.1,
            "battery_temp_max_c": 38.1,
            "cell_voltage_min_v": 3.72,
            "cell_voltage_max_v": 3.78,
            "motor_rpm": 7420,
            "motor_torque_nm": 182.6,
            "inverter_temperature_c": 54.2,
            "brake_pad_wear_pct": 72.0,
            "brake_disc_temp_c": 138.4,
            "brake_pedal_pos_pct": 22.6,
            "hydraulic_pressure_bar": 74.5,
            "steering_angle_deg": 4.6,
            "steering_torque_nm": 3.8,
            "yaw_rate_deg_s": 0.86,
            "pitch_rate_deg_s": 0.21,
            "roll_rate_deg_s": 0.32,
            "ambient_temp_c": 22.0,
            "ambient_humidity_pct": 65.0,
            "vehicle_speed_kmh": 85.0,
            "avg_speed_kmh": 62.5,
            "driving_efficiency_score": 0.82,
            "energy_consumption_kwh_per_km": 0.18
        }
    }
}

async def test_diagnostic_agent():
    """Test diagnostic agent output format"""
    print("\n" + "="*80)
    print("TESTING DIAGNOSTIC AGENT")
    print("="*80)
    
    data_manager = VehicleDataManager()
    data_manager.vehicles = SAMPLE_DATA
    
    context = VehicleContext(vehicle_id="default", data_manager=data_manager)
    
    try:
        result = await diagnostic_agent.run(
            "Perform a complete diagnostic analysis of the vehicle",
            deps=context
        )
        
        response_text = result.data
        print("\nAgent Response (first 500 chars):")
        print(response_text[:500])
        
        # Check for markdown table format
        if "|" in response_text and "Category" in response_text:
            print("\n✅ Response contains markdown table format")
        else:
            print("\n❌ Response MISSING markdown table format")
            
        # Check for Vehicle ID line
        if "**Vehicle ID:**" in response_text:
            print("✅ Response contains Vehicle ID header")
        else:
            print("❌ Response MISSING Vehicle ID header")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_maintenance_agent():
    """Test maintenance agent output format"""
    print("\n" + "="*80)
    print("TESTING MAINTENANCE AGENT")
    print("="*80)
    
    data_manager = VehicleDataManager()
    data_manager.vehicles = SAMPLE_DATA
    
    context = VehicleContext(vehicle_id="default", data_manager=data_manager)
    
    try:
        result = await maintenance_agent.run(
            "Provide maintenance recommendations for the vehicle",
            deps=context
        )
        
        response_text = result.data
        print("\nAgent Response (first 500 chars):")
        print(response_text[:500])
        
        # Check for markdown table format
        if "|" in response_text and "Category" in response_text:
            print("\n✅ Response contains markdown table format")
        else:
            print("\n❌ Response MISSING markdown table format")
            
        # Check for Vehicle ID line
        if "**Vehicle ID:**" in response_text:
            print("✅ Response contains Vehicle ID header")
        else:
            print("❌ Response MISSING Vehicle ID header")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_performance_agent():
    """Test performance agent output format"""
    print("\n" + "="*80)
    print("TESTING PERFORMANCE AGENT")
    print("="*80)
    
    data_manager = VehicleDataManager()
    data_manager.vehicles = SAMPLE_DATA
    
    context = VehicleContext(vehicle_id="default", data_manager=data_manager)
    
    try:
        result = await performance_agent.run(
            "Analyze the vehicle's performance characteristics",
            deps=context
        )
        
        response_text = result.data
        print("\nAgent Response (first 500 chars):")
        print(response_text[:500])
        
        # Check for markdown table format
        if "|" in response_text and "Category" in response_text:
            print("\n✅ Response contains markdown table format")
        else:
            print("\n❌ Response MISSING markdown table format")
            
        # Check for Vehicle ID line
        if "**Vehicle ID:**" in response_text:
            print("✅ Response contains Vehicle ID header")
        else:
            print("❌ Response MISSING Vehicle ID header")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    print("\n" + "="*80)
    print("AGENT OUTPUT FORMAT VERIFICATION TEST")
    print("="*80)
    
    await test_diagnostic_agent()
    await test_maintenance_agent()
    await test_performance_agent()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
