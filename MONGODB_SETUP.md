# MongoDB Setup Guide

## Quick Setup (3 Steps)

### Step 1: Install MongoDB Driver
```bash
pip install -r requirements.txt
```

Or just install pymongo:
```bash
pip install pymongo
```

### Step 2: Get MongoDB URI
1. Go to [MongoDB Atlas](https://cloud.mongodb.com)
2. Create a free account (if you don't have one)
3. Create a new project
4. Create a database cluster (free tier available)
5. Click "Connect" → "Drivers" → Copy the connection string
6. The URI will look like:
```
mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/
```

### Step 3: Add to .env
Open `.env` file and paste your MongoDB URI:
```env
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/
```

## Done! 🎉

Your anomaly data will now automatically:
- ✅ Store in MongoDB when detected
- ✅ Persist across server restarts
- ✅ Work perfectly with serverless
- ✅ Be queryable via the API

---

## API Endpoints

### Get All Anomalies (MongoDB)
```
GET /analyze?limit=100&vehicle_id=default
```

**Response:**
```json
{
  "status": "success",
  "total_anomalies": 42,
  "returned_count": 42,
  "anomalies": [
    {
      "_id": "65abc123...",
      "timestamp": "2024-01-15T10:30:45.123Z",
      "packet_index": 245,
      "vehicle_id": "default",
      "analysis": {
        "timestamp": "2024-01-15T10:30:50.456Z",
        "agent": "diagnostic",
        "response": "Engine pressure detected..."
      }
    }
  ]
}
```

### Get Recent Anomalies (Fallback)
```
GET /anomalies
```

---

## Troubleshooting

### MongoDB refuses connection
- Check username/password in URI
- Check IP whitelist on MongoDB Atlas (add 0.0.0.0/0 for testing)
- Ensure your internet connection is stable

### "MONGODB not connected" warning
- Verify MONGODB_URI in .env
- Check that `.env` file exists in project root
- Restart the FastAPI server

### Want to clear all anomalies?
Add this to your Python script:
```python
from mongodb_handler import MongoDBHandler

handler = MongoDBHandler()
deleted = handler.clear_all_anomalies()
print(f"Deleted {deleted} anomalies")
```

---

## How It Works

1. **Every anomaly detected** → Saved to MongoDB automatically
2. **Every 1 minute request** → Frontend calls `GET /analyze`
3. **Returns all stored data** → No data loss on server restart
4. **Serverless compatible** → Works on Vercel, AWS Lambda, etc.

No more in-memory storage issues! 🚀
