# RCA/CAPA Debug & Fix Guide

## Problem
RCA/CAPA responses were being stored with empty parsed data:
- `vehicle_id: null`
- `rca_analysis: []`
- `capa_analysis: []`
- `affected_components: null`
- `oem_owners: []`
- `safety_criticality: null`

## Root Cause
The LLM response format didn't match what the parsing functions expected, resulting in failed table extraction.

## Fixes Applied

### 1. Improved Response Parsing (`response_parser.py`)

**Changes:**
- Multiple regex patterns for Vehicle ID extraction (fallback support)
- Better table detection with case-insensitive matching
- Validation to skip empty cells and placeholder text
- Handles null values properly instead of defaulting to empty arrays

**Key Functions Updated:**
- `parse_rca_capa_response()` - Added multiple pattern matching
- `parse_rca_table()` - Better header detection
- `parse_capa_table()` - More robust parsing

### 2. Simplified RCA/CAPA Agent Prompt (`agents_final.py`)

**Old Approach:** Complex, multi-section prompt (500+ lines)
**New Approach:** Simple, explicit format specification (30 lines)

**New Prompt Format:**
```
OUTPUT FORMAT (MANDATORY):
Start with: **Vehicle ID:** default – Electric Vehicle

Then output exactly these two tables:

## ROOT CAUSE ANALYSIS (RCA)
| Failure Component | Primary Cause | Contributing Factors | Evidence |
...

## CORRECTIVE AND PREVENTIVE ACTIONS (CAPA)
| Action Type | Action Item | Timeline | Expected Outcome | OEM Owner |
...

Rules:
- Fill all cells with real data
- 2-3 rows minimum per table
- No placeholder text
- Assign to: Battery Team, Motor Team, Software Team, Quality Team, Design Team
```

### 3. Added Debug Endpoint (`main.py`)

**New Endpoint: `GET /rca_capa_debug`**
- Shows raw_response_preview from LLM
- Shows parsed counts (parsed_rca_count, parsed_capa_count)
- Helps identify if parsing is the issue

**Usage:**
```bash
curl http://localhost:8000/rca_capa_debug?limit=5
```

**Response includes:**
- Raw first 200 characters of LLM response
- Count of parsed RCA rows
- Count of parsed CAPA rows
- Timestamp and buffer info

### 4. Added Response Preview Storage (`main.py`)

RCA/CAPA documents now store:
- `raw_response_preview` (first 200 chars of raw response)
- Helps diagnose parsing issues without accessing raw response text

## How to Diagnose Future Issues

### Step 1: Check Debug Endpoint
```bash
curl http://localhost:8000/rca_capa_debug
```

Look at `raw_response_preview` to see what the LLM is outputting.

### Step 2: Verify Response Format
Expected format:
```
**Vehicle ID:** ...

## ROOT CAUSE ANALYSIS (RCA)

| Column1 | Column2 | ... |
|---------|---------|-----|
| Value1  | Value2  | ... |

## CORRECTIVE AND PREVENTIVE ACTIONS (CAPA)

| Column1 | Column2 | ... |
|---------|---------|-----|
| Value1  | Value2  | ... |
```

### Step 3: Check Parsing Functions
If format looks correct but still not parsing:
1. Test parsing function directly
2. Check regex patterns in response_parser.py
3. Verify table header names match expected format

### Step 4: Adjust Agent Prompt if Needed
If LLM keeps using different format:
1. Use simpler instructions
2. Add examples in the prompt
3. Use specific wording that LLM understands better

## Files Modified

1. **agents_final.py** - RCA/CAPA agent prompt simplified
2. **response_parser.py** - Better parsing with multiple fallback patterns
3. **main.py** - Added debug endpoint and response preview storage
4. **mongodb_handler.py** - Stores raw_response_preview (no changes to this)

## Testing the Fix

### Manual Test with Buffer Trigger
1. Start the application: `python main.py`
2. Let it stream until buffer reaches 20 items
3. Check `/rca_capa` endpoint to see parsed data
4. If empty, check `/rca_capa_debug` to see raw response

### Post RCA/CAPA Endpoint Test
```bash
curl -X POST http://localhost:8000/rca_capa
```

Then check results with:
```bash
curl http://localhost:8000/rca_capa
curl http://localhost:8000/rca_capa_debug
```

## Expected Behavior After Fix

**Before (With Issue):**
```json
{
  "parsed_data": {
    "vehicle_id": null,
    "rca_analysis": [],
    "capa_analysis": [],
    "affected_components": null,
    "oem_owners": [],
    "safety_criticality": null
  }
}
```

**After (Fixed):**
```json
{
  "parsed_data": {
    "vehicle_id": "default",
    "rca_analysis": [
      {
        "Failure Component": "Battery System",
        "Primary Cause": "Thermal degradation",
        "Contributing Factors": "High ambient temp, Deep cycling",
        "Evidence": "Temp 48°C, SOC drops 8% per hour"
      }
    ],
    "capa_analysis": [
      {
        "Action Type": "Corrective",
        "Action Item": "Thermal management firmware patch",
        "Timeline": "24hrs",
        "Expected Outcome": "Cool inverter by 5°C",
        "OEM Owner": "Software Team"
      }
    ],
    "affected_components": ["Battery System"],
    "oem_owners": ["Software Team"],
    "safety_criticality": null  // Will be extracted if present
  }
}
```

## Fallback Patterns Added

If the main Vehicle ID pattern doesn't work, parser tries:
1. `\*\*Vehicle ID:\*\*\s*([^\n–]+?)\s*(?:–|$)` (bold markdown)
2. `Vehicle ID:\s*([^\n–]+?)\s*(?:–|$)` (plain text)
3. `\*\*Vehicle ID:\*\*\s*([^\n]+)` (bold with newline)
4. `vehicle_id["\']?\s*:\s*["\']?([^"\'\n,]+)` (JSON format)

Similar fallbacks for Risk Assessment patterns.

## Next Steps if Still Not Working

1. **Run debug endpoint** to see raw response
2. **Compare with expected format** - adjust prompt if needed
3. **Test parsing functions directly** with sample responses
4. **Check Groq API response** - might have different behavior than expected
5. **Consider using different model** or provider if Groq keeps failing

## API Endpoints Summary

### RCA/CAPA Endpoints
- `GET /rca_capa` - Get stored RCA/CAPA analyses
- `POST /rca_capa` - Manually trigger RCA/CAPA analysis
- `GET /rca_capa_debug` - Debug endpoint with raw response preview

### LLM Response Endpoints
- `GET /llm_response` - Get parsed LLM responses
- `POST /llm_response` - Save LLM response

All endpoints support MongoDB filtering by vehicle_id and other fields.
