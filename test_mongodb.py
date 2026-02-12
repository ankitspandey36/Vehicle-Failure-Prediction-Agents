#!/usr/bin/env python3
"""
Quick test script to verify MongoDB setup
Run this to test if your MongoDB connection is working
"""

import os
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv()

from mongodb_handler import MongoDBHandler

def test_mongodb():
    """Test MongoDB connection and basic operations"""
    
    print("\n" + "="*70)
    print("MongoDB Connection Test")
    print("="*70 + "\n")
    
    # Check if URI is set
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("❌ MONGODB_URI not set in .env")
        print("   Please add: MONGODB_URI=your_uri_here")
        return False
    
    print("✓ MONGODB_URI found")
    
    # Initialize handler
    handler = MongoDBHandler(mongodb_uri)
    
    # Check connection
    if not handler.is_connected():
        print("❌ Failed to connect to MongoDB")
        print("   Check your URI and internet connection")
        return False
    
    print("✓ Successfully connected to MongoDB")
    
    # Test saving an anomaly
    test_anomaly = {
        "vehicle_id": "test-vehicle",
        "packet_index": 999,
        "timestamp": "2024-01-15T10:30:00Z",
        "analysis": {
            "agent": "diagnostic",
            "response": "Test anomaly - can be deleted"
        }
    }
    
    anomaly_id = handler.save_anomaly(test_anomaly)
    if not anomaly_id:
        print("❌ Failed to save test anomaly")
        return False
    
    print(f"✓ Saved test anomaly: {anomaly_id}")
    
    # Test retrieving anomalies
    anomalies = handler.get_all_anomalies(limit=5)
    print(f"✓ Retrieved {len(anomalies)} anomalies from database")
    
    # Test count
    count = handler.get_anomalies_count()
    print(f"✓ Total anomalies in database: {count}")
    
    # Clean up test data
    if handler.delete_anomaly(anomaly_id):
        print(f"✓ Cleaned up test anomaly")
    
    print("\n" + "="*70)
    print("✅ All tests passed! MongoDB is ready to use")
    print("="*70 + "\n")
    
    # Print connection details
    print("Database: vehicle_analysis")
    print("Collection: anomalies")
    print("\nYou can now:")
    print("  - Run: python main.py")
    print("  - Visit: http://localhost:8000/docs")
    print("  - Call: GET /analyze")
    
    return True

if __name__ == "__main__":
    success = test_mongodb()
    sys.exit(0 if success else 1)
