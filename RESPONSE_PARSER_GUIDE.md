# Response Parser Documentation

## What It Does

Converts raw LLM text responses (markdown tables, formatted text) into clean, structured JSON that's easy to display on frontend.

## Before Parsing (Raw LLM Response)

```
**Vehicle ID:** default – *Electric Vehicle*  

| Category | Summary | Key Values | Severity |
|----------|---------|------------|----------|
| **Battery** | Good overall health; only minor temperature imbalance | SOC 67.68 %, SoH 96.8 %, Pack 371.1 V | ⚠️ Warning |
| **Motor & Inverter** | Nominal operating range | RPM 7 420, Torque 182.6 Nm | ⚠️ Warning |
```

## After Parsing (Structured JSON)

```json
{
  "vehicle_id": "default",
  "summary": "Electric Vehicle",
  "categories": [
    {
      "name": "Battery",
      "summary": "Good overall health; only minor temperature imbalance",
      "severity": "⚠️ Warning",
      "metrics": {
        "SOC": "67.68 %",
        "SoH": "96.8 %",
        "Pack": "371.1 V"
      }
    },
    {
      "name": "Motor & Inverter",
      "summary": "Nominal operating range",
      "severity": "⚠️ Warning",
      "metrics": {
        "RPM": "7 420",
        "Torque": "182.6 Nm"
      }
    }
  ],
  "severity_summary": {
    "Battery": "⚠️ Warning",
    "Motor & Inverter": "⚠️ Warning"
  }
}
```

## Stored in MongoDB

```json
{
  "_id": "65abc123...",
  "timestamp": "2024-01-15T10:30:45Z",
  "vehicle_id": "default",
  "analysis": {
    "raw_response": "**Vehicle ID:** default...", // Full original text
    "structured_data": { /* parsed JSON above */ }
  },
  "structured_analysis": {
    "original_response": "...",
    "structured_data": { /* parsed JSON */ },
    "categories": [/* array of categories */]
  }
}
```

## Retrieved from GET /analyze

```json
{
  "status": "success",
  "anomalies": [
    {
      "_id": "65abc123...",
      "vehicle_id": "default",
      "structured_analysis": {
        "categories": [
          {
            "name": "Battery",
            "metrics": {
              "SOC": "67.68 %",
              "SoH": "96.8 %"
            }
          }
        ]
      }
    }
  ]
}
```

## Frontend Usage

Now you can access clean data:

```javascript
const response = await fetch('/analyze');
const data = await response.json();

data.anomalies.forEach(anomaly => {
  // Access structured data
  const categories = anomaly.structured_analysis.categories;
  
  categories.forEach(cat => {
    console.log(`${cat.name}: ${cat.summary}`);
    
    // Display metrics nicely
    Object.entries(cat.metrics).forEach(([key, value]) => {
      console.log(`  ${key}: ${value}`);
    });
  });
});
```

## Features

✅ Extracts vehicle ID
✅ Parses markdown tables automatically
✅ Extracts metrics with values (e.g., "SOC: 67.68 %")
✅ Identifies severity levels
✅ Structures data for easy frontend display
✅ Keeps original text for reference
✅ Error-safe (fails gracefully if parsing fails)

## How It's Used in the App

1. **Stream Detection**: Anomaly detected → LLM analyzes → Response is text
2. **Parser**: Response text → Converts to JSON structure
3. **Database**: Stores both original text AND structured JSON
4. **Frontend**: Retrieves structured JSON → Beautiful display

No more ugly markdown tables in frontend! 🎉
