/**
 * Frontend Example: How to fetch anomalies from the backend
 * 
 * Usage:
 *   const anomalies = await fetchAnomalies();
 *   console.log(anomalies);
 */

// ============================================================================
// Basic Fetch (Vanilla JavaScript)
// ============================================================================

async function fetchAnomalies(limit = 100, vehicleId = null) {
    try {
        let url = `http://localhost:8000/analyze?limit=${limit}`;
        if (vehicleId) {
            url += `&vehicle_id=${vehicleId}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching anomalies:", error);
        return null;
    }
}

// ============================================================================
// React Hook Example
// ============================================================================

import { useState, useEffect } from "react";

function useAnomalies(pollInterval = 60000) {
    // Poll every 1 minute (60000ms)
    const [anomalies, setAnomalies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const response = await fetch("http://localhost:8000/analyze?limit=100");
                const data = await response.json();

                if (data.status === "success") {
                    setAnomalies(data.anomalies);
                    setError(null);
                } else {
                    setError(data.message);
                }
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        // Fetch immediately
        fetchData();

        // Then fetch every N milliseconds
        const interval = setInterval(fetchData, pollInterval);

        return () => clearInterval(interval);
    }, [pollInterval]);

    return { anomalies, loading, error };
}

// Usage in a component:
function AnomalyDashboard() {
    const { anomalies, loading, error } = useAnomalies(60000); // Poll every 1 minute

    if (loading) return <div>Loading anomalies...</div>;
    if (error) return <div>Error: {error}</div>;

    return (
        <div>
            <h2>Detected Anomalies ({anomalies.length})</h2>
            {anomalies.map((anomaly) => (
                <div key={anomaly._id} style={{ border: "1px solid red", padding: "10px", marginBottom: "10px" }}>
                    <p><strong>ID:</strong> {anomaly._id}</p>
                    <p><strong>Timestamp:</strong> {anomaly.timestamp}</p>
                    <p><strong>Packet Index:</strong> {anomaly.packet_index}</p>
                    <p><strong>Analysis:</strong> {anomaly.analysis.response}</p>
                </div>
            ))}
        </div>
    );
}

// ============================================================================
// Axios Example
// ============================================================================

import axios from "axios";

async function fetchAnomaliesWithAxios() {
    try {
        const response = await axios.get("http://localhost:8000/analyze", {
            params: {
                limit: 100,
                // vehicle_id: "default"
            },
        });

        console.log("Total anomalies:", response.data.total_anomalies);
        console.log("Anomalies:", response.data.anomalies);

        return response.data.anomalies;
    } catch (error) {
        console.error("Error:", error.message);
    }
}

// ============================================================================
// Vue.js Example
// ============================================================================

export default {
    data() {
        return {
            anomalies: [],
            loading: true,
            error: null,
        };
    },

    mounted() {
        this.fetchAnomalies();

        // Poll every 1 minute
        setInterval(() => {
            this.fetchAnomalies();
        }, 60000);
    },

    methods: {
        async fetchAnomalies() {
            try {
                this.loading = true;
                const response = await fetch("http://localhost:8000/analyze?limit=100");
                const data = await response.json();

                if (data.status === "success") {
                    this.anomalies = data.anomalies;
                    this.error = null;
                } else {
                    this.error = data.message;
                }
            } catch (err) {
                this.error = err.message;
            } finally {
                this.loading = false;
            }
        },
    },
};

// ============================================================================
// Response Format
// ============================================================================

/*
{
  "status": "success",
  "total_anomalies": 42,
  "returned_count": 20,
  "vehicle_id": "default",
  "anomalies": [
    {
      "_id": "65abc123def456ghi789jkl",
      "timestamp": "2024-01-15T10:30:45.123Z",
      "packet_index": 245,
      "vehicle_id": "default",
      "analysis": {
        "timestamp": "2024-01-15T10:30:50.456Z",
        "packet_index": 245,
        "agent": "diagnostic",
        "response": "Engine oil pressure is abnormally low...",
        "buffer_size": 300
      },
      "created_at": "2024-01-15T10:30:50.789Z"
    },
    // ... more anomalies
  ],
  "timestamp": "2024-01-15T10:35:22.123Z"
}
*/

// ============================================================================
// Real-time Card Component
// ============================================================================

function AnomalyCard({ anomaly }) {
    const date = new Date(anomaly.timestamp);
    const timeStr = date.toLocaleTimeString();

    return (
        <div style={{
            border: "2px solid #d32f2f",
            borderRadius: "8px",
            padding: "16px",
            marginBottom: "12px",
            backgroundColor: "#ffebee"
        }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
                <h3 style={{ margin: "0 0 8px 0" }}>🚨 Anomaly Detected</h3>
                <span style={{ fontSize: "12px", color: "#666" }}>{timeStr}</span>
            </div>

            <p style={{ margin: "8px 0", fontSize: "14px" }}>
                <strong>Agent:</strong> {anomaly.analysis.agent}
            </p>

            <p style={{ margin: "8px 0", fontSize: "14px" }}>
                <strong>Analysis:</strong>
            </p>
            <p style={{ margin: "0", padding: "8px", backgroundColor: "#fff", borderRadius: "4px", fontSize: "13px" }}>
                {anomaly.analysis.response}
            </p>

            <p style={{ margin: "8px 0 0 0", fontSize: "12px", color: "#666" }}>
                Packet #{anomaly.packet_index} • ID: {anomaly._id.substring(0, 8)}...
            </p>
        </div>
    );
}

export { fetchAnomalies, useAnomalies, AnomalyCard };
