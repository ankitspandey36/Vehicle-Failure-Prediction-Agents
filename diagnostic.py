#!/usr/bin/env python
"""
Comprehensive diagnostic script for Vehicle Failure Prediction system
Tests all critical components: API keys, MongoDB, anomaly detection, API endpoints
"""

import os
import json
import sys
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("🔍 VEHICLE FAILURE PREDICTION - COMPREHENSIVE DIAGNOSTIC")
print("=" * 80)
print()

# ============================================================================
# 1. CHECK ENVIRONMENT VARIABLES
# ============================================================================
print("1️⃣  CHECKING ENVIRONMENT VARIABLES")
print("-" * 80)

from dotenv import load_dotenv
load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
mongo_uri = os.getenv("MONGODB_URI")

if groq_key:
    print(f"✅ GROQ_API_KEY: {groq_key[:20]}...")
else:
    print("❌ GROQ_API_KEY: NOT FOUND")

if mongo_uri:
    print(f"✅ MONGODB_URI: {mongo_uri[:50]}...")
else:
    print("❌ MONGODB_URI: NOT FOUND")

print()

# ============================================================================
# 2. CHECK MONGODB CONNECTION
# ============================================================================
print("2️⃣  CHECKING MONGODB CONNECTION")
print("-" * 80)

from mongodb_handler import MongoDBHandler
mongodb_handler = MongoDBHandler()

if mongodb_handler.is_connected():
    print("✅ MongoDB is connected")
    
    # Check anomalies collection
    try:
        count = mongodb_handler.anomalies_collection.count_documents({})
        print(f"📊 Total anomalies in database: {count}")
    except Exception as e:
        print(f"❌ Error counting anomalies: {e}")
else:
    print("❌ MongoDB is NOT connected")

print()

# ============================================================================
# 3. CHECK DATA FILES
# ============================================================================
print("3️⃣  CHECKING DATA FILES")
print("-" * 80)

dataset_new = Path("dataset/newData.json")
dataset_old = Path("dataset/oldData.json")
mfg_db = Path("Manufacturing_Database.json")

print(f"newData.json: {'✅ EXISTS' if dataset_new.exists() else '❌ MISSING'}")
print(f"oldData.json: {'✅ EXISTS' if dataset_old.exists() else '❌ MISSING'}")
print(f"Manufacturing_Database.json: {'✅ EXISTS' if mfg_db.exists() else '❌ MISSING'}")

if dataset_new.exists():
    try:
        with open(dataset_new) as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"   → {len(data)} packets in newData.json")
            elif isinstance(data, dict) and "packets" in data:
                print(f"   → {len(data.get('packets', []))} packets in newData.json")
    except Exception as e:
        print(f"   → Error reading newData.json: {e}")

print()

# ============================================================================
# 4. CHECK ANOMALY DETECTION RULES
# ============================================================================
print("4️⃣  CHECKING ANOMALY DETECTION RULES")
print("-" * 80)

from predefined_Rules import ruleGate, load_manufacturing_database
from fetch import load_packets, normalize_packet

MD = load_manufacturing_database()
print(f"Manufacturing DB loaded: {len(MD)} entries" if MD else "❌ Manufacturing DB empty")

try:
    packets = load_packets(dataset_new)
    if packets:
        print(f"📦 Loaded {len(packets)} packets from newData.json")
        
        # Test anomaly detection on first 10 packets
        anomalies_found = 0
        print("\nTesting first 10 packets for anomalies:")
        for i in range(min(10, len(packets))):
            packet = normalize_packet(packets[i])
            try:
                is_healthy = ruleGate(packet, MD)
                status = "✅ HEALTHY" if is_healthy else "🔴 ANOMALY"
                print(f"  Packet {i}: {status}")
                if not is_healthy:
                    anomalies_found += 1
            except Exception as e:
                print(f"  Packet {i}: ❌ ERROR - {e}")
        
        print(f"\nAnomalies detected: {anomalies_found}/10")
    else:
        print("❌ No packets loaded from newData.json")
except Exception as e:
    print(f"❌ Error testing anomalies: {e}")

print()

# ============================================================================
# 5. CHECK LLM AVAILABILITY
# ============================================================================
print("5️⃣  CHECKING LLM / AI MODEL")
print("-" * 80)

try:
    from agents_final import active_model, GROQ_API_KEY
    if GROQ_API_KEY:
        print(f"✅ Groq API Key loaded: {GROQ_API_KEY[:20]}...")
        print(f"✅ Model configured: OpenAI model connecting to Groq")
    else:
        print("❌ Groq API Key NOT loaded")
except Exception as e:
    print(f"❌ Error loading agent model: {e}")

print()

# ============================================================================
# 6. CHECK FASTAPI SERVER
# ============================================================================
print("6️⃣  CHECKING FASTAPI SERVER SETUP")
print("-" * 80)

try:
    from main import app
    print("✅ FastAPI app imported successfully")
    
    # List routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.append(route.path)
    
    print(f"📌 Available endpoints ({len(routes)} routes):")
    for route in sorted(set(routes))[:10]:
        print(f"   → {route}")
    
except Exception as e:
    print(f"❌ Error importing FastAPI app: {e}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("📋 DIAGNOSTIC SUMMARY")
print("=" * 80)
print()
print("✅ Next Steps:")
print("  1. Run the server:  python main.py")
print("  2. Visit API docs:  http://localhost:8000/docs")
print("  3. Check anomalies: http://localhost:8000/analyze")
print("  4. Monitor logs for 🔴 ANOMALY messages")
print()
print("💾 Check MongoDB:")
print("  mongosh '<MONGODB_URI>'")
print("  use vehicle_analysis")
print("  db.anomalies.find().pretty()")
print()
print("=" * 80)
