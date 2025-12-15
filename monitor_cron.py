#!/usr/bin/env python3
"""
Scheduled monitoring script for vehicle health analysis.
Run this as a cron job to perform hourly vehicle checks.

Setup cron job (runs every hour):
    crontab -e
    Add line: 0 * * * * /usr/bin/python3 /path/to/monitor_cron.py >> /path/to/cron.log 2>&1

Or for testing every 5 minutes:
    */5 * * * * /usr/bin/python3 /path/to/monitor_cron.py >> /path/to/cron.log 2>&1
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from agents_final import get_comprehensive_analysis
from utils import VehicleDataManager, AnalysisLogger, get_sensor_status


class MonitoringService:
    """Service for scheduled vehicle monitoring"""
    
    def __init__(self):
        self.data_manager = VehicleDataManager()
        self.logger = AnalysisLogger()
        self.monitoring_log_path = Path("dataset/monitoring_reports.json")
        self.alerts_path = Path("dataset/alerts.json")
    
    def load_monitoring_logs(self) -> list:
        """Load existing monitoring logs"""
        if self.monitoring_log_path.exists():
            try:
                with open(self.monitoring_log_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_monitoring_log(self, log_data: dict):
        """Save monitoring log to file"""
        logs = self.load_monitoring_logs()
        logs.append(log_data)
        
        # Keep only last 500 entries
        if len(logs) > 500:
            logs = logs[-500:]
        
        with open(self.monitoring_log_path, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def save_alert(self, alert_data: dict):
        """Save critical alerts to separate file"""
        alerts = []
        if self.alerts_path.exists():
            try:
                with open(self.alerts_path, 'r') as f:
                    alerts = json.load(f)
            except:
                alerts = []
        
        alerts.append(alert_data)
        
        # Keep only last 100 alerts
        if len(alerts) > 100:
            alerts = alerts[-100:]
        
        with open(self.alerts_path, 'w') as f:
            json.dump(alerts, f, indent=2)
    
    def check_critical_sensors(self, vehicle_id: str) -> list:
        """
        Check for critical sensor values that need immediate attention.
        
        Returns list of critical issues found.
        """
        sensors = self.data_manager.get_sensor_data(vehicle_id)
        critical_issues = []
        
        # Check each sensor against critical thresholds
        critical_checks = {
            "engine_temp_c": (110, "Engine temperature critically high"),
            "battery_voltage": (12.0, "Battery voltage critically low", lambda v: v < 12.0 or v > 15.0),
            "oil_pressure_kpa": (150, "Oil pressure critically low"),
            "coolant_temp_c": (105, "Coolant temperature critically high"),
            "fuel_level_percent": (10, "Fuel level critically low"),
            "brake_fluid_level_percent": (50, "Brake fluid critically low"),
            "battery_soc": (10, "Battery charge critically low"),
        }
        
        for sensor, check_info in critical_checks.items():
            if sensor in sensors:
                value = sensors[sensor]
                
                # Handle custom check function
                if len(check_info) > 2 and callable(check_info[2]):
                    if check_info[2](value):
                        critical_issues.append({
                            "sensor": sensor,
                            "value": value,
                            "issue": check_info[1]
                        })
                else:
                    threshold = check_info[0]
                    message = check_info[1]
                    
                    # Check based on sensor type
                    if "low" in message.lower():
                        if value < threshold:
                            critical_issues.append({
                                "sensor": sensor,
                                "value": value,
                                "issue": message
                            })
                    else:  # "high" issues
                        if value > threshold:
                            critical_issues.append({
                                "sensor": sensor,
                                "value": value,
                                "issue": message
                            })
        
        # Check for DTC codes
        if "dtc_codes" in sensors and sensors["dtc_codes"]:
            critical_issues.append({
                "sensor": "dtc_codes",
                "value": sensors["dtc_codes"],
                "issue": f"Diagnostic trouble codes detected: {', '.join(sensors['dtc_codes'])}"
            })
        
        return critical_issues
    
    async def monitor_vehicle(self, vehicle_id: str) -> dict:
        """
        Perform comprehensive monitoring for a single vehicle.
        
        Returns monitoring report with analysis and alerts.
        """
        print(f"[{datetime.now().isoformat()}] Monitoring vehicle: {vehicle_id}")
        
        # Check for critical issues first
        critical_issues = self.check_critical_sensors(vehicle_id)
        
        # Get comprehensive AI analysis
        try:
            analysis = await get_comprehensive_analysis(vehicle_id, self.data_manager)
        except Exception as e:
            print(f"Error analyzing {vehicle_id}: {str(e)}")
            analysis = {"error": str(e)}
        
        # Build monitoring report
        report = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": vehicle_id,
            "critical_issues": critical_issues,
            "has_critical_alerts": len(critical_issues) > 0,
            "analysis": analysis
        }
        
        # Save report
        self.save_monitoring_log(report)
        
        # Save critical alerts separately
        if critical_issues:
            alert = {
                "timestamp": datetime.now().isoformat(),
                "vehicle_id": vehicle_id,
                "severity": "CRITICAL",
                "issues": critical_issues,
                "message": f"Vehicle {vehicle_id} has {len(critical_issues)} critical issue(s) requiring immediate attention"
            }
            self.save_alert(alert)
            print(f"⚠️  CRITICAL ALERT for {vehicle_id}: {len(critical_issues)} issue(s)")
        
        return report
    
    async def monitor_all_vehicles(self):
        """Monitor all vehicles in the system"""
        print(f"\n{'='*60}")
        print(f"Vehicle Monitoring Service - {datetime.now().isoformat()}")
        print(f"{'='*60}\n")
        
        vehicle_ids = self.data_manager.get_vehicle_ids()
        print(f"Monitoring {len(vehicle_ids)} vehicles...")
        
        total_critical = 0
        
        for vehicle_id in vehicle_ids:
            report = await self.monitor_vehicle(vehicle_id)
            
            if report["has_critical_alerts"]:
                total_critical += 1
        
        print(f"\n{'='*60}")
        print(f"Monitoring complete!")
        print(f"Total vehicles checked: {len(vehicle_ids)}")
        print(f"Vehicles with critical alerts: {total_critical}")
        print(f"Reports saved to: {self.monitoring_log_path}")
        if total_critical > 0:
            print(f"⚠️  Alerts saved to: {self.alerts_path}")
        print(f"{'='*60}\n")


def main():
    """Main function for cron job execution"""
    # Check for Gemini API key
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable not set!")
        print("Please set it with: export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Create monitoring service
    service = MonitoringService()
    
    # Run monitoring
    try:
        asyncio.run(service.monitor_all_vehicles())
    except Exception as e:
        print(f"ERROR: Monitoring failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
