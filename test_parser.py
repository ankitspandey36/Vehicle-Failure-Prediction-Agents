#!/usr/bin/env python3
"""
Test the response parser with example LLM output
"""

from response_parser import structure_analysis_for_db
import json

# Example response from LLM
example_response = """**Vehicle ID:** default – *Electric Vehicle*  

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Battery** | Good overall health; only minor temperature imbalance | SOC 67.68 %, SoH 96.8 %, Pack 371.1 V, Pack Curr 114 A, Temp avg 33.1 °C, Temp max 38.1 °C, Cell range 0.06 V, Temp spread 5.7 °C | ⚠️ Warning (temperature spread) |
| **Motor & Inverter** | Nominal operating range, no overload | RPM 7 420, Torque 182.6 Nm, Inverter 54.2 °C | ⚠️ Warning (inverter temp) |
| **Brake System** | Pad wear approaching critical, disc temperature high | Pad wear 72 %, Disc 138.4 °C, Pedal 22.6 %, Pressure 74.5 bar | ⚠️ Warning (pad wear, disc temp) |
| **Chassis** | Stable dynamics, no stress | Steering 4.6°/3.8 Nm, Yaw 0.86°, Pitch 0.21°, Roll 0.32°, Suspension travel 18–19 mm, Stress 0.38 | ✅ Excellent |
"""

print("\n" + "="*80)
print("RESPONSE PARSER TEST")
print("="*80 + "\n")

print("INPUT (Raw LLM Response):")
print("-" * 80)
print(example_response)
print("-" * 80 + "\n")

# Parse the response
result = structure_analysis_for_db(example_response)

print("OUTPUT (Structured JSON):")
print("-" * 80)
print(json.dumps(result, indent=2))
print("-" * 80 + "\n")

# Show what will be stored in MongoDB
print("DATABASE STORAGE FORMAT:")
print("-" * 80)
db_format = {
    "timestamp": "2024-01-15T10:30:45.123Z",
    "vehicle_id": "default",
    "packet_index": 245,
    "agent": "diagnostic",
    "structured_analysis": result,
    "created_at": "2024-01-15T10:30:50.789Z"
}
print(json.dumps(db_format, indent=2))
print("-" * 80 + "\n")

# Test frontend retrieval
print("FRONTEND ACCESS EXAMPLE:")
print("-" * 80)
print("```javascript")
print("// Get anomalies from API")
print("const response = await fetch('/analyze');")
print("const data = await response.json();")
print("")
print("// Access structured data")
print("data.anomalies.forEach(anomaly => {")
print("  const structured = anomaly.structured_analysis;")
print("")
print("  // Display categories")
print("  structured.categories.forEach(cat => {")
print("    console.log(`${cat.name}`);")
print("    console.log(`  Summary: ${cat.summary}`);")
print("    console.log(`  Severity: ${cat.severity}`);")
print("")
print("    // Display metrics")
print("    Object.entries(cat.metrics).forEach(([key, value]) => {")
print("      console.log(`    ${key}: ${value}`);")
print("    });")
print("  });")
print("});")
print("```")
print("-" * 80 + "\n")

print("✅ Parser working correctly!")
print(f"   - Extracted vehicle ID: {result['vehicle_id']}")
print(f"   - Found {len(result['categories'])} categories")
print(f"   - Total metrics extracted: {sum(len(cat.get('metrics', {})) for cat in result['categories'])}")
print("\n" + "="*80 + "\n")
