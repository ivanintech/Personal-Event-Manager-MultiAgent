# Copyright 2024
# Directory: yt-agentic-rag/app/config/database.py

"""
Database connection and schema management using Supabase SDK.
Handles Supabase Postgres with pgvector extension for RAG operations.
"""

import logging
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Database:
    """Supabase database operations manager for RAG functionality."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.supabase: Optional[Client] = None
        self._admin_client: Optional[Client] = None
    
    async def connect(self) -> None:
        """Initialize Supabase clients."""
        try:
            # Regular client with anon key (for future frontend compatibility)
            self.supabase = create_client(
                settings.supabase_url,
                settings.supabase_anon_key
            )
            
            # Admin client with service role key (for backend operations)
            self._admin_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
            
            logger.info("Supabase clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase clients: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Supabase connections (cleanup if needed)."""
        # Supabase clients don't need explicit disconnection
        logger.info("Supabase clients cleaned up")
    
    def get_client(self, admin: bool = True) -> Client:
        """
        Get Supabase client instance.
        
        Args:
            admin: If True, returns admin client with service role key.
                   If False, returns regular client with anon key.
        """
        if not self.supabase or not self._admin_client:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        return self._admin_client if admin else self.supabase
    
    async def initialize_schema(self) -> None:
        """
        Check if database schema is initialized.
        
        Note: The actual schema setup must be done manually in Supabase.
        Run the SQL script: sql/init_supabase.sql in your Supabase SQL Editor.
        """
        try:
            client = self.get_client(admin=True)
            
            # Check if the table exists and has the required structure
            result = client.table('rag_chunks').select('id').limit(1).execute()
            
            if result.data is not None:
                logger.info("Database schema is properly initialized")
                
                # Test the vector search function
                try:
                    stats_result = client.rpc('get_chunk_stats').execute()
                    if stats_result.data:
                        stats = stats_result.data[0]
                        logger.info(f"Database stats: {stats['total_chunks']} chunks, {stats['unique_sources']} sources")
                except Exception:
                    logger.warning("get_chunk_stats function not available - some features may not work")
                    
            else:
                logger.error("Database schema not initialized!")
                logger.error(
                    "Please run the SQL initialization script:\n"
                    "1. Open your Supabase project dashboard\n"
                    "2. Go to SQL Editor\n"
                    "3. Run the script: sql/init_supabase.sql\n"
                    "4. Restart your application"
                )
                
        except Exception as e:
            logger.error(f"Database schema check failed: {e}")
            logger.error(
                "Please ensure you've run sql/init_supabase.sql in your Supabase dashboard"
            )
    
    async def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Upsert document chunks into the database using Supabase SDK.
        
        Args:
            chunks: List of chunk dictionaries with keys: chunk_id, source, text, embedding
            
        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0
        
        try:
            client = self.get_client(admin=True)
            
            # Prepare data for Supabase
            chunk_data = []
            for chunk in chunks:
                chunk_data.append({
                    'chunk_id': chunk['chunk_id'],
                    'source': chunk['source'],
                    'text': chunk['text'],
                    'embedding': chunk['embedding']  # Supabase handles vector serialization
                })
            
            # Use upsert with on_conflict parameter
            result = client.table('rag_chunks').upsert(
                chunk_data,
                on_conflict='chunk_id'
            ).execute()
            
            inserted_count = len(result.data) if result.data else 0
            logger.info(f"Upserted {inserted_count} chunks to database")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to upsert chunks: {e}")
            raise
    
    async def vector_search(self, query_embedding: List[float], top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using Supabase SDK.
        
        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            
        Returns:
            List of matching chunks with similarity scores
        """
        try:
            client = self.get_client(admin=True)
            
            # Use RPC call for vector similarity search
            # This requires creating a PostgreSQL function in Supabase
            result = client.rpc('match_chunks', {
                'query_embedding': query_embedding,
                'match_count': top_k
            }).execute()
            
            if result.data:
                logger.info(f"Vector search returned {len(result.data)} results")
                return result.data
            else:
                # Fallback: if RPC function doesn't exist, use regular query
                # This won't have vector similarity but will work for basic testing
                logger.info("Using fallback query (match_chunks RPC function not available)")
                result = client.table('rag_chunks').select('*').limit(top_k).execute()
                
                # Add mock similarity scores for fallback
                if result.data:
                    for i, chunk in enumerate(result.data):
                        chunk['similarity'] = 1.0 - (i * 0.1)  # Mock decreasing similarity
                
                return result.data or []
                
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Supabase connection health."""
        try:
            client = self.get_client(admin=True)
            
            # Simple query to test connection
            result = client.table('rag_chunks').select('id').limit(1).execute()
            
            return True  # If no exception, connection is healthy
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def insert_extracted_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert extracted events into the database.
        
        Args:
            events: List of event dictionaries with keys matching extracted_events table
            
        Returns:
            List of inserted events with their IDs
        """
        if not events:
            return []
        
        try:
            client = self.get_client(admin=True)
            
            # Insert events
            result = client.table('extracted_events').insert(events).execute()
            
            inserted_count = len(result.data) if result.data else 0
            logger.info(f"Inserted {inserted_count} events into extracted_events")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to insert extracted events: {e}")
            raise

    async def get_extracted_events(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get extracted events from the database.
        
        Args:
            status: Filter by status (e.g., 'suggested', 'proposed', 'confirmed')
            limit: Maximum number of events to return
            offset: Offset for pagination
            
        Returns:
            List of events
        """
        try:
            client = self.get_client(admin=True)
            
            query = client.table('extracted_events').select('*')
            
            if status:
                query = query.eq('status', status)
            
            query = query.order('created_at', desc=True).limit(limit).offset(offset)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get extracted events: {e}")
            return []

    async def update_extracted_event(
        self,
        event_id: int,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an extracted event.
        
        Args:
            event_id: ID of the event to update
            updates: Dictionary with fields to update
            
        Returns:
            Updated event
        """
        try:
            client = self.get_client(admin=True)
            
            result = client.table('extracted_events').update(updates).eq('id', event_id).execute()
            
            if result.data:
                logger.info(f"Updated event {event_id}")
                return result.data[0]
            else:
                raise ValueError(f"Event {event_id} not found")
                
        except Exception as e:
            logger.error(f"Failed to update extracted event {event_id}: {e}")
            raise


# Global database instance
db = Database()