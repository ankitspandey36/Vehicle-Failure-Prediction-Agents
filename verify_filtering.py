import json
from response_parser import structure_analysis_for_db

example_response = """
**Vehicle ID:** VH001 – *Analysis Report*

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Battery** | Healthy | SOC 80% | ✅ Normal |
| **Motor** | Slightly hot | Inverter 65 C | ⚠️ Warning |
| **Brakes** | Pads worn | Front pads 20% | ⚠️ Warning |
| **Chassis** | Stable | Travel 15mm | ✅ Normal |
"""

print("Testing structure_analysis_for_db filtering...")
result = structure_analysis_for_db(example_response)

print(f"Vehicle ID: {result.get('vehicle_id')}")
print(f"Total categories returned: {len(result.get('categories', []))}")

for i, cat in enumerate(result.get('categories', [])):
    print(f"Category {i+1}: {cat['name']} - Severity: {cat['severity']}")

# Check if any "Normal" categories leaked through
normals = [cat for cat in result.get('categories', []) if "Normal" in cat.get('severity', '')]
if normals:
    print("FAILED: Found Normal categories in output!")
else:
    print("SUCCESS: Only Warning categories found.")

# Check severity_summary
print(f"Severity Summary: {json.dumps(result.get('severity_summary'), indent=2)}")
