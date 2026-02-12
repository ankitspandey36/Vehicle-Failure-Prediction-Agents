"""
MongoDB handler for storing and retrieving anomaly data
Simple integration - just requires MONGODB_URI in .env
"""

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime
import os
from typing import List, Dict, Optional

class MongoDBHandler:
    def __init__(self, mongodb_uri: Optional[str] = None):
        """
        Initialize MongoDB connection
        
        Args:
            mongodb_uri: MongoDB connection string. If None, reads from MONGODB_URI env var
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = None
        self.db = None
        self.anomalies_collection = None
        
        if not self.mongodb_uri:
            print("[MONGODB] WARNING: MONGODB_URI not set. Please add it to .env")
            return
        
        try:
            self.connect()
            print("[MONGODB] Successfully connected to MongoDB")
        except Exception as e:
            print(f"[MONGODB] Failed to connect: {e}")
    
    def connect(self):
        """Establish MongoDB connection"""
        if not self.mongodb_uri:
            raise ValueError("MONGODB_URI not set")
        
        self.client = MongoClient(
            self.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000
        )
        
        # Test connection
        self.client.admin.command('ping')
        
        # Get database and collections
        self.db = self.client['vehicle_analysis']
        self.anomalies_collection = self.db['anomalies']
        
        # Create index for faster queries
        self.anomalies_collection.create_index('timestamp')
        self.anomalies_collection.create_index('vehicle_id')
    
    def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
        except:
            pass
        return False
    
    def save_anomaly(self, anomaly_data: Dict) -> Optional[str]:
        """
        Save anomaly data to MongoDB
        
        Args:
            anomaly_data: Dictionary containing anomaly details
        
        Returns:
            Document ID if successful, None otherwise
        """
        if not self.is_connected():
            print("[MONGODB] Not connected")
            return None
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in anomaly_data:
                anomaly_data['timestamp'] = datetime.utcnow().isoformat()
            
            # Insert into MongoDB
            result = self.anomalies_collection.insert_one(anomaly_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MONGODB] Error saving anomaly: {e}")
            return None
    
    def get_all_anomalies(self, limit: int = 100, vehicle_id: Optional[str] = None) -> List[Dict]:
        """
        Get all anomalies from MongoDB
        
        Args:
            limit: Maximum number of anomalies to return
            vehicle_id: Optional filter by vehicle ID
        
        Returns:
            List of anomaly documents
        """
        if not self.is_connected():
            print("[MONGODB] Not connected")
            return []
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            
            # Get anomalies sorted by timestamp (newest first)
            # No projection = return ALL fields
            anomalies = list(
                self.anomalies_collection
                .find(query)
                .sort('timestamp', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for anomaly in anomalies:
                anomaly['_id'] = str(anomaly['_id'])
            
            return anomalies
        except Exception as e:
            print(f"[MONGODB] Error fetching anomalies: {e}")
            return []
        except Exception as e:
            print(f"[MONGODB] Error fetching anomalies: {e}")
            return []
    
    def get_anomaly_by_id(self, anomaly_id: str) -> Optional[Dict]:
        """
        Get a specific anomaly by ID
        
        Args:
            anomaly_id: MongoDB document ID
        
        Returns:
            Anomaly document or None
        """
        if not self.is_connected():
            return None
        
        try:
            from bson.objectid import ObjectId
            
            anomaly = self.anomalies_collection.find_one({'_id': ObjectId(anomaly_id)})
            if anomaly:
                anomaly['_id'] = str(anomaly['_id'])
            return anomaly
        except Exception as e:
            print(f"[MONGODB] Error fetching anomaly: {e}")
            return None
    
    def get_anomalies_count(self, vehicle_id: Optional[str] = None) -> int:
        """
        Get total count of anomalies
        
        Args:
            vehicle_id: Optional filter by vehicle ID
        
        Returns:
            Count of anomalies
        """
        if not self.is_connected():
            return 0
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            
            return self.anomalies_collection.count_documents(query)
        except Exception as e:
            print(f"[MONGODB] Error counting anomalies: {e}")
            return 0
    
    def delete_anomaly(self, anomaly_id: str) -> bool:
        """
        Delete a specific anomaly
        
        Args:
            anomaly_id: MongoDB document ID
        
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            from bson.objectid import ObjectId
            
            result = self.anomalies_collection.delete_one({'_id': ObjectId(anomaly_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"[MONGODB] Error deleting anomaly: {e}")
            return False
    
    def clear_all_anomalies(self, vehicle_id: Optional[str] = None) -> int:
        """
        Clear all anomalies (or for a specific vehicle)
        
        Args:
            vehicle_id: Optional filter by vehicle ID
        
        Returns:
            Number of deleted documents
        """
        if not self.is_connected():
            return 0
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            
            result = self.anomalies_collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"[MONGODB] Error clearing anomalies: {e}")
            return 0
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("[MONGODB] Connection closed")
