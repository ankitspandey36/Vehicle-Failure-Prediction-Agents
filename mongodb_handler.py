"""
MongoDB handler for storing and retrieving anomaly data
Simple integration - just requires MONGODB_URI in .env
"""

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime, UTC
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
        self.rca_capa_collection = self.db['rca_capa']
        self.llm_responses_collection = self.db['llm_responses']
        
        # Create indexes for faster queries
        self.anomalies_collection.create_index('timestamp')
        self.anomalies_collection.create_index('vehicle_id')
        self.rca_capa_collection.create_index('timestamp')
        self.rca_capa_collection.create_index('vehicle_id')
        self.rca_capa_collection.create_index('oem_owner')
        self.llm_responses_collection.create_index('timestamp')
        self.llm_responses_collection.create_index('vehicle_id')
        self.llm_responses_collection.create_index('agent_type')
    
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
                anomaly_data['timestamp'] = datetime.now(UTC).isoformat()
            
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
    
    def save_rca_capa(self, rca_capa_data: Dict) -> Optional[str]:
        """
        Save RCA/CAPA analysis to MongoDB
        
        Args:
            rca_capa_data: Dictionary containing RCA/CAPA analysis
                Expected keys: vehicle_id, parsed_rca_capa, raw_response, oem_owners, etc.
        
        Returns:
            Document ID if successful, None otherwise
        """
        if not self.is_connected():
            print("[MONGODB] Not connected - cannot save RCA/CAPA")
            return None
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in rca_capa_data:
                rca_capa_data['timestamp'] = datetime.now(UTC).isoformat()
            
            # Insert into MongoDB
            result = self.rca_capa_collection.insert_one(rca_capa_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MONGODB] Error saving RCA/CAPA: {e}")
            return None
    
    def get_rca_capa_analyses(self, vehicle_id: Optional[str] = None, limit: int = 100, oem_owner: Optional[str] = None) -> List[Dict]:
        """
        Retrieve RCA/CAPA analyses from MongoDB
        
        Args:
            vehicle_id: Optional filter by vehicle ID
            limit: Maximum number of documents to return
            oem_owner: Optional filter by OEM team owner
        
        Returns:
            List of RCA/CAPA documents
        """
        if not self.is_connected():
            return []
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            if oem_owner:
                query['oem_owner'] = oem_owner
            
            analyses = list(
                self.rca_capa_collection
                .find(query)
                .sort('timestamp', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for analysis in analyses:
                analysis['_id'] = str(analysis['_id'])
            
            return analyses
        except Exception as e:
            print(f"[MONGODB] Error fetching RCA/CAPA analyses: {e}")
            return []
    
    def save_llm_response(self, llm_response_data: Dict) -> Optional[str]:
        """
        Save detailed LLM response (parsed format) to MongoDB
        
        Args:
            llm_response_data: Dictionary containing parsed LLM response
                Expected keys: vehicle_id, agent_type, parsed_data, timestamp, etc.
        
        Returns:
            Document ID if successful, None otherwise
        """
        if not self.is_connected():
            print("[MONGODB] Not connected - cannot save LLM response")
            return None
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in llm_response_data:
                llm_response_data['timestamp'] = datetime.now(UTC).isoformat()
            
            # Insert into MongoDB
            result = self.llm_responses_collection.insert_one(llm_response_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MONGODB] Error saving LLM response: {e}")
            return None
    
    def get_llm_responses(self, vehicle_id: Optional[str] = None, agent_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Retrieve parsed LLM responses from MongoDB
        
        Args:
            vehicle_id: Optional filter by vehicle ID
            agent_type: Optional filter by agent type (diagnostic, maintenance, performance, rca_capa)
            limit: Maximum number of documents to return
        
        Returns:
            List of LLM response documents
        """
        if not self.is_connected():
            return []
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            if agent_type:
                query['agent_type'] = agent_type
            
            responses = list(
                self.llm_responses_collection
                .find(query)
                .sort('timestamp', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for response in responses:
                response['_id'] = str(response['_id'])
            
            return responses
        except Exception as e:
            print(f"[MONGODB] Error fetching LLM responses: {e}")
            return []
    
    def get_rca_capa_count(self, vehicle_id: Optional[str] = None, oem_owner: Optional[str] = None) -> int:
        """
        Get count of RCA/CAPA analyses
        
        Args:
            vehicle_id: Optional filter by vehicle ID
            oem_owner: Optional filter by OEM owner
        
        Returns:
            Count of RCA/CAPA documents
        """
        if not self.is_connected():
            return 0
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            if oem_owner:
                query['oem_owner'] = oem_owner
            
            return self.rca_capa_collection.count_documents(query)
        except Exception as e:
            print(f"[MONGODB] Error counting RCA/CAPA: {e}")
            return 0
    
    def get_llm_responses_count(self, vehicle_id: Optional[str] = None, agent_type: Optional[str] = None) -> int:
        """
        Get count of LLM responses
        
        Args:
            vehicle_id: Optional filter by vehicle ID
            agent_type: Optional filter by agent type
        
        Returns:
            Count of LLM response documents
        """
        if not self.is_connected():
            return 0
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            if agent_type:
                query['agent_type'] = agent_type
            
            return self.llm_responses_collection.count_documents(query)
        except Exception as e:
            print(f"[MONGODB] Error counting LLM responses: {e}")
            return 0
    
    def clear_all_rca_capa(self, vehicle_id: Optional[str] = None) -> int:
        """
        Clear all RCA/CAPA analyses (or for a specific vehicle)
        
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
            
            result = self.rca_capa_collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"[MONGODB] Error clearing RCA/CAPA: {e}")
            return 0
    
    def clear_all_llm_responses(self, vehicle_id: Optional[str] = None, agent_type: Optional[str] = None) -> int:
        """
        Clear all LLM responses (or for a specific vehicle/agent)
        
        Args:
            vehicle_id: Optional filter by vehicle ID
            agent_type: Optional filter by agent type
        
        Returns:
            Number of deleted documents
        """
        if not self.is_connected():
            return 0
        
        try:
            query = {}
            if vehicle_id:
                query['vehicle_id'] = vehicle_id
            if agent_type:
                query['agent_type'] = agent_type
            
            result = self.llm_responses_collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"[MONGODB] Error clearing LLM responses: {e}")
            return 0
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("[MONGODB] Connection closed")
