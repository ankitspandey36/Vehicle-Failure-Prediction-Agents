"""
Utility functions for vehicle data management
"""
import json
from typing import Dict, List, Optional
from pathlib import Path


class VehicleDataManager:
    """Manages vehicle data from JSON database"""
    
    def __init__(self, db_path: str = "dataset/vehicle_realtime_data.json"):
        self.db_path = Path(db_path)
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load vehicle data from JSON file"""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"vehicles": []}
    
    def get_vehicle_data(self, vehicle_id: str) -> Optional[Dict]:
        """
        Fetch data for a specific vehicle by ID.
        Simulates API call to car's onboard computer.
        
        Args:
            vehicle_id: Vehicle identifier (e.g., "VH001")
        
        Returns:
            Dictionary containing vehicle data or None if not found
        """
        for vehicle in self.data.get("vehicles", []):
            if vehicle.get("vehicle_id") == vehicle_id:
                return vehicle
        return None
    
    def get_all_vehicles(self) -> List[Dict]:
        """Get data for all vehicles"""
        return self.data.get("vehicles", [])
    
    def get_vehicle_ids(self) -> List[str]:
        """Get list of all vehicle IDs"""
        return [v.get("vehicle_id") for v in self.data.get("vehicles", [])]
    
    def get_sensor_data(self, vehicle_id: str, sensor_fields: Optional[List[str]] = None) -> Dict:
        """
        Get specific sensor data from a vehicle.
        
        Args:
            vehicle_id: Vehicle identifier
            sensor_fields: List of sensor field names to fetch. If None, returns all.
        
        Returns:
            Dictionary of sensor readings
        """
        vehicle = self.get_vehicle_data(vehicle_id)
        if not vehicle:
            return {}
        
        sensors = vehicle.get("available_sensor_fields", {})
        
        if sensor_fields is None:
            return sensors
        
        # Return only requested fields
        return {field: sensors.get(field) for field in sensor_fields if field in sensors}
    
    def get_vehicle_type(self, vehicle_id: str) -> Optional[str]:
        """Get vehicle type/category"""
        vehicle = self.get_vehicle_data(vehicle_id)
        return vehicle.get("car_type") if vehicle else None


class AnalysisLogger:
    """Logger for saving analysis results"""
    
    def __init__(self, log_path: str = "dataset/analysis_logs.json"):
        self.log_path = Path(log_path)
        self.logs = self._load_logs()
    
    def _load_logs(self) -> List[Dict]:
        """Load existing logs"""
        if self.log_path.exists():
            try:
                with open(self.log_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_analysis(self, analysis_data: Dict) -> None:
        """
        Save analysis results to log file
        
        Args:
            analysis_data: Dictionary containing analysis results
        """
        self.logs.append(analysis_data)
        
        # Keep only last 1000 entries
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
        with open(self.log_path, 'w') as f:
            json.dump(self.logs, f, indent=2)
    
    def get_vehicle_history(self, vehicle_id: str, limit: int = 10) -> List[Dict]:
        """Get analysis history for a specific vehicle"""
        vehicle_logs = [
            log for log in self.logs 
            if log.get("vehicle_id") == vehicle_id
        ]
        return vehicle_logs[-limit:]


# Sensor value reference ranges and descriptions
SENSOR_RANGES = {
    "engine_temp_c": {
        "normal": (85, 105),
        "warning": (105, 110),
        "critical": (110, float('inf')),
        "description": "Engine temperature in Celsius. Normal operating range is 85-105°C."
    },
    "battery_voltage": {
        "normal": (12.4, 14.8),  # For 12V systems
        "warning": (12.0, 12.4),
        "critical": (0, 12.0),
        "description": "Battery voltage. 12V systems: 12.4-14.8V normal. EV systems: 300-450V typical."
    },
    "battery_soc": {
        "normal": (20, 100),
        "warning": (10, 20),
        "critical": (0, 10),
        "description": "Battery State of Charge percentage. Below 20% needs charging."
    },
    "oil_pressure_kpa": {
        "normal": (200, 350),
        "warning": (150, 200),
        "critical": (0, 150),
        "description": "Engine oil pressure in kPa. Critical if below 150 kPa during operation."
    },
    "coolant_temp_c": {
        "normal": (80, 95),
        "warning": (95, 105),
        "critical": (105, float('inf')),
        "description": "Coolant temperature. Should stay between 80-95°C."
    },
    "rpm": {
        "normal": (0, 3000),
        "warning": (3000, 5000),
        "critical": (5000, float('inf')),
        "description": "Engine RPM. Idle: 600-1000, normal driving: 1500-3000."
    },
    "fuel_level_percent": {
        "normal": (25, 100),
        "warning": (10, 25),
        "critical": (0, 10),
        "description": "Fuel level percentage. Refuel below 25%."
    },
    "tire_pressure_fl": {
        "normal": (30, 35),
        "warning": (25, 30),
        "critical": (0, 25),
        "description": "Front left tire pressure in PSI. Normal: 30-35 PSI."
    },
    "motor_temp_c": {
        "normal": (40, 80),
        "warning": (80, 90),
        "critical": (90, float('inf')),
        "description": "Electric motor temperature. Should stay under 80°C."
    },
    "brake_fluid_level_percent": {
        "normal": (70, 100),
        "warning": (50, 70),
        "critical": (0, 50),
        "description": "Brake fluid level. Critical safety issue if below 50%."
    }
}


def get_sensor_status(sensor_name: str, value: float) -> str:
    """
    Determine sensor status based on value
    
    Returns: "normal", "warning", or "critical"
    """
    if sensor_name not in SENSOR_RANGES:
        return "normal"
    
    ranges = SENSOR_RANGES[sensor_name]
    
    if ranges["critical"][0] <= value <= ranges["critical"][1]:
        return "critical"
    elif ranges["warning"][0] <= value <= ranges["warning"][1]:
        return "warning"
    else:
        return "normal"
