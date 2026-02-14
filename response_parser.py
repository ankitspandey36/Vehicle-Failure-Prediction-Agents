"""
Parse LLM response text into structured JSON
Converts markdown tables and text into clean JSON objects
"""

import re
from typing import Dict, List, Any
import json


def parse_markdown_table(text: str) -> List[Dict[str, str]]:
    """
    Parse markdown table from text into list of dictionaries
    
    Example input:
    | Category | Summary | Key Values |
    |----------|---------|------------|
    | Battery  | Good    | SOC 67%... |
    
    Returns: [{"Category": "Battery", "Summary": "Good", "Key Values": "SOC 67%..."}]
    """
    lines = text.strip().split('\n')
    
    # Find header line (first line with pipes)
    header_idx = -1
    for i, line in enumerate(lines):
        if '|' in line and 'Category' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
    # Extract header
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split('|')[1:-1]]
    
    # Skip separator line and empty lines
    data = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i].strip()
        
        if not line or '|' not in line:
            continue
        
        values = [v.strip() for v in line.split('|')[1:-1]]
        
        # Only add if we have correct number of columns
        if len(values) == len(headers):
            row = {header: value for header, value in zip(headers, values)}
            data.append(row)
    
    return data


def parse_vehicle_analysis(text: str) -> Dict[str, Any]:
    """
    Parse complete LLM analysis response into structured JSON
    
    Extracts:
    - Vehicle ID
    - Categories (Battery, Motor, Brake, Chassis, etc.)
    - Key metrics and values
    - Severity levels
    
    Returns clean, queryable JSON structure
    """
    result = {
        "vehicle_id": None,
        "summary": None,
        "categories": [],
        "extracted_metrics": {},
        "severity_summary": {}
    }
    
    # Extract Vehicle ID and summary
    vehicle_match = re.search(r'\*\*Vehicle ID:\*\*\s*([^\n–]+?)\s*(?:–|$)', text)
    if vehicle_match:
        result["vehicle_id"] = vehicle_match.group(1).strip()
    
    # Extract summary line (everything after the dash on Vehicle ID line)
    summary_match = re.search(r'Vehicle ID:[^–]*–\s*([^\n]+)', text)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()
    
    # Parse markdown table
    table_data = parse_markdown_table(text)
    
    if not table_data:
        # Fallback: try to extract any useful information if table parsing fails
        result["summary"] = result["summary"] or "Analysis completed"
        return result
    
    # Structure categories with their metrics
    for row in table_data:
        category_name = row.get("Category", "").replace("**", "").strip()
        
        # Skip empty category names
        if not category_name or category_name == "-----------":
            continue
        
        category = {
            "name": category_name,
            "summary": row.get("Summary", "").strip(),
            "key_values": row.get("Key Values", "").strip(),
            "severity": row.get("Severity", "").strip(),
            "metrics": extract_metrics(row.get("Key Values", ""))
        }
        
        result["categories"].append(category)
        result["severity_summary"][category["name"]] = category["severity"]
    
    return result


def extract_metrics(key_values_text: str) -> Dict[str, str]:
    """
    Extract key-value pairs from text like "SOC 67.68 %, SoH 96.8 %"
    
    Returns: {"SOC": "67.68 %", "SoH": "96.8 %", ...}
    """
    metrics = {}
    
    # Split by comma or semicolon
    parts = re.split(r'[,;]', key_values_text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Match pattern: "NAME value" or "NAME value UNIT"
        match = re.match(r'([A-Za-z0-9_\s]+?)\s+([\d\.\-\s°\/°C]+(?:\s*[%°A-Za-z/]*)?)', part)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            metrics[key] = value
    
    return metrics


def convert_response_to_json(llm_response: str) -> Dict[str, Any]:
    """
    Main function: Convert LLM response text to JSON
    
    Args:
        llm_response: Raw text from LLM
    
    Returns:
        Structured JSON dictionary
    """
    return parse_vehicle_analysis(llm_response)


def structure_analysis_for_db(llm_response: str) -> Dict[str, Any]:
    """
    Prepare analysis for database storage
    
    Returns clean JSON structure ready to save to MongoDB
    Only saves structured data, not the original text
    """
    parsed = convert_response_to_json(llm_response)
    
    return {
        "vehicle_id": parsed.get("vehicle_id"),
        "summary": parsed.get("summary"),
        "categories": parsed.get("categories"),
        "severity_summary": parsed.get("severity_summary")
    }


def parse_rca_table(text: str) -> List[Dict[str, str]]:
    """
    Parse RCA markdown table from text into list of dictionaries
    
    Example:
    | Failure Component | Primary Cause | Contributing Factors | Evidence |
    |------|------|------|------|
    | Battery | ... | ... | ... |
    
    Returns list of dictionaries
    """
    lines = text.strip().split('\n')
    
    # Find RCA header line
    header_idx = -1
    for i, line in enumerate(lines):
        if '|' in line and 'Failure Component' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
    # Extract header
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split('|')[1:-1]]
    
    # Skip separator line
    data = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i].strip()
        
        if not line or '|' not in line:
            continue
        
        values = [v.strip() for v in line.split('|')[1:-1]]
        
        if len(values) == len(headers):
            row = {header: value for header, value in zip(headers, values)}
            data.append(row)
    
    return data


def parse_capa_table(text: str) -> List[Dict[str, str]]:
    """
    Parse CAPA markdown table from text into list of dictionaries
    
    Example:
    | Action Type | Action Item | Timeline | Expected Outcome | OEM Owner |
    
    Returns list of dictionaries
    """
    lines = text.strip().split('\n')
    
    # Find CAPA header line
    header_idx = -1
    for i, line in enumerate(lines):
        if '|' in line and 'Action Type' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
    # Extract header
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split('|')[1:-1]]
    
    # Skip separator line
    data = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i].strip()
        
        if not line or '|' not in line:
            continue
        
        values = [v.strip() for v in line.split('|')[1:-1]]
        
        if len(values) == len(headers):
            row = {header: value for header, value in zip(headers, values)}
            data.append(row)
    
    return data


def parse_rca_capa_response(text: str) -> Dict[str, Any]:
    """
    Parse complete RCA/CAPA LLM response into structured JSON
    
    Extracts:
    - Vehicle ID
    - RCA Analysis (Root Cause Analysis table)
    - CAPA Analysis (Corrective and Preventive Actions table)
    - OEM Owners/Teams
    
    Returns clean, queryable JSON structure
    """
    result = {
        "vehicle_id": None,
        "rca_analysis": [],
        "capa_analysis": [],
        "affected_components": None,
        "oem_owners": [],
        "safety_criticality": None,
        "raw_text_preview": text[:300]  # Store first 300 chars for reference
    }
    
    if not text or len(text.strip()) == 0:
        return result
    
    # Extract Vehicle ID - try multiple patterns
    vehicle_patterns = [
        r'\*\*Vehicle ID:\*\*\s*([^\n–]+?)\s*(?:–|$)',
        r'Vehicle ID:\s*([^\n–]+?)\s*(?:–|$)',
        r'\*\*Vehicle ID:\*\*\s*([^\n]+)',
        r'vehicle_id["\']?\s*:\s*["\']?([^"\'\n,]+)'
    ]
    
    for pattern in vehicle_patterns:
        vehicle_match = re.search(pattern, text, re.IGNORECASE)
        if vehicle_match:
            result["vehicle_id"] = vehicle_match.group(1).strip()
            break
    
    # Parse RCA table
    rca_data = parse_rca_table(text)
    if rca_data:
        result["rca_analysis"] = rca_data
        # Extract unique components from RCA
        components = set()
        for row in rca_data:
            component = row.get("Failure Component", "").strip()
            if component and component not in ["", "-", "---"]:
                components.add(component)
        result["affected_components"] = list(components) if components else None
    
    # Parse CAPA table
    capa_data = parse_capa_table(text)
    if capa_data:
        result["capa_analysis"] = capa_data
        # Extract OEM owners from CAPA
        owners = set()
        for row in capa_data:
            owner = row.get("OEM Owner", "").strip()
            if owner and owner.lower() not in ["oem owner", "", "-", "---"]:
                owners.add(owner)
        result["oem_owners"] = list(owners)
    
    # Extract risk assessments - try multiple patterns
    risk_patterns = [
        r'Safety criticality[:\s]+([^\n,;]+)',
        r'Criticality[:\s]+([^\n,;]+)',
        r'Risk[:\s]+(High|Medium|Low|Critical)'
    ]
    
    for pattern in risk_patterns:
        risk_match = re.search(pattern, text, re.IGNORECASE)
        if risk_match:
            result["safety_criticality"] = risk_match.group(1).strip()
            break
    
    return result


def structure_rca_capa_for_db(llm_response: str) -> Dict[str, Any]:
    """
    Prepare RCA/CAPA analysis for database storage
    
    Returns clean JSON structure ready to save to MongoDB
    Focused on parsed data, not raw text
    """
    parsed = parse_rca_capa_response(llm_response)
    
    return {
        "vehicle_id": parsed.get("vehicle_id"),
        "rca_analysis": parsed.get("rca_analysis"),
        "capa_analysis": parsed.get("capa_analysis"),
        "affected_components": parsed.get("affected_components"),
        "oem_owners": parsed.get("oem_owners"),
        "safety_criticality": parsed.get("safety_criticality")
    }


def structure_llm_response_for_db(llm_response: str, agent_type: str) -> Dict[str, Any]:
    """
    Prepare any LLM response for database storage in parsed format
    
    Args:
        llm_response: Raw LLM response text
        agent_type: Type of agent (diagnostic, maintenance, performance, rca_capa)
    
    Returns:
        Structured JSON ready for MongoDB storage
    """
    if agent_type == "rca_capa":
        return structure_rca_capa_for_db(llm_response)
    else:
        return structure_analysis_for_db(llm_response)


# Example usage and testing
if __name__ == "__main__":
    example_response = """
**Vehicle ID:** default – *Electric Vehicle*

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Battery** | Good overall health; only minor temperature imbalance | SOC 67.68 %, SoH 96.8 %, Pack 371.1 V, Pack Curr 114 A, Temp avg 33.1 °C, Temp max 38.1 °C, Cell range 0.06 V, Temp spread 5.7 °C | ⚠️ Warning (temperature spread) |
| **Motor & Inverter** | Nominal operating range, no overload | RPM 7 420, Torque 182.6 Nm, Inverter 54.2 °C | ⚠️ Warning (inverter temp) |
| **Brake System** | Pad wear approaching critical, disc temperature high | Pad wear 72 %, Disc 138.4 °C, Pedal 22.6 %, Pressure 74.5 bar | ⚠️ Warning (pad wear, disc temp) |
| **Chassis** | Stable dynamics, no stress | Steering 4.6°/3.8 Nm, Yaw 0.86°, Pitch 0.21°, Roll 0.32°, Suspension travel 18–19 mm, Stress 0.38 | ✅ Excellent |
    """
    
    result = structure_analysis_for_db(example_response)
    print(json.dumps(result, indent=2))
