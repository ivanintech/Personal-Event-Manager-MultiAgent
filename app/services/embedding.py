# Copyright 2024
# Directory: yt-agentic-rag/app/services/embedding.py

"""
Embedding service for generating text embeddings using OpenAI.
Focused solely on vector embeddings for RAG retrieval.
Includes caching to reduce API costs and latency.
"""

import logging
import hashlib
import time
from typing import List, Dict, Tuple, Optional
from collections import OrderedDict
import openai
import httpx
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingCache:
    """
    LRU Cache para embeddings con TTL.
    Thread-safe para uso en aplicaciones async.
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        Inicializa el caché de embeddings.
        
        Args:
            max_size: Tamaño máximo del caché (número de entradas)
            ttl: Time-to-live en segundos (default: 1 hora)
        """
        self.max_size = max_size
        self.ttl = ttl
        # OrderedDict para implementar LRU
        self._cache: OrderedDict[str, Tuple[List[float], float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def _get_cache_key(self, text: str) -> str:
        """Genera una clave de caché única para un texto."""
        # Normalizar texto: lowercase, strip, y hash
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def get(self, text: str) -> Optional[List[float]]:
        """
        Obtiene un embedding del caché si existe y no ha expirado.
        
        Args:
            text: Texto a buscar en el caché
            
        Returns:
            Embedding si existe y es válido, None en caso contrario
        """
        if not settings.embedding_cache_enabled:
            return None
        
        cache_key = self._get_cache_key(text)
        
        if cache_key in self._cache:
            embedding, timestamp = self._cache[cache_key]
            
            # Verificar si ha expirado
            if time.time() - timestamp < self.ttl:
                # Mover al final (más reciente)
                self._cache.move_to_end(cache_key)
                self._hits += 1
                logger.debug(f"Cache HIT for text: {text[:50]}...")
                return embedding
            else:
                # Expiró, eliminar
                del self._cache[cache_key]
                logger.debug(f"Cache EXPIRED for text: {text[:50]}...")
        
        self._misses += 1
        return None
    
    def set(self, text: str, embedding: List[float]):
        """
        Almacena un embedding en el caché.
        
        Args:
            text: Texto original
            embedding: Vector de embedding a almacenar
        """
        if not settings.embedding_cache_enabled:
            return
        
        cache_key = self._get_cache_key(text)
        timestamp = time.time()
        
        # Si el caché está lleno, eliminar el más antiguo (LRU)
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Eliminar el más antiguo
        
        # Almacenar con timestamp
        self._cache[cache_key] = (embedding, timestamp)
        self._cache.move_to_end(cache_key)  # Mover al final (más reciente)
        logger.debug(f"Cached embedding for text: {text[:50]}...")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            Diccionario con estadísticas (hits, misses, hit_rate, size)
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "enabled": settings.embedding_cache_enabled
        }
    
    def clear(self):
        """Limpia todo el caché."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Embedding cache cleared")


class EmbeddingService:
    """Service for generating text embeddings using OpenAI with caching."""
    
    def __init__(self):
        """Initialize OpenAI client for embeddings."""
        self.provider = settings.ai_provider
        if self.provider == "openai":
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            self.embed_model = settings.openai_embed_model
        elif self.provider == "nebius":
            self.openai_client = None
            self.embed_model = settings.nebius_embed_model
            self.base_url = settings.nebius_base_url.rstrip("/")
            self.api_key = settings.nebius_api_key
        else:
            # fallback: openai config but may error if key missing
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            self.embed_model = settings.openai_embed_model
        
        # Inicializar caché de embeddings
        self.cache = EmbeddingCache(
            max_size=settings.embedding_cache_max_size,
            ttl=settings.embedding_cache_ttl
        )
        logger.info(
            f"EmbeddingService initialized with cache: "
            f"enabled={settings.embedding_cache_enabled}, "
            f"max_size={settings.embedding_cache_max_size}, "
            f"ttl={settings.embedding_cache_ttl}s"
        )
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with caching.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (1536 dimensions for text-embedding-3-small)
        """
        try:
            # Verificar caché primero
            cached_embeddings: Dict[int, List[float]] = {}
            texts_to_embed: List[Tuple[int, str]] = []
            
            for idx, text in enumerate(texts):
                cached = self.cache.get(text)
                if cached is not None:
                    cached_embeddings[idx] = cached
                else:
                    texts_to_embed.append((idx, text))
            
            # Si todos estaban en caché, devolver directamente
            if not texts_to_embed:
                logger.debug(f"All {len(texts)} embeddings retrieved from cache")
                return [cached_embeddings[i] for i in range(len(texts))]
            
            # Generar embeddings solo para textos no cacheados
            texts_to_process = [text for _, text in texts_to_embed]
            logger.debug(
                f"Cache: {len(cached_embeddings)} hits, "
                f"{len(texts_to_embed)} misses. Generating {len(texts_to_process)} embeddings."
            )
            
            if self.provider == "nebius":
                headers = {"Authorization": f"Bearer {self.api_key}"}
                payload = {"model": self.embed_model, "input": texts}
                # trust_env=False para evitar proxys del entorno que causaban 404 con Nebius
                async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                    resp = await client.post(
                        f"{self.base_url}/v1/embeddings",
                        json=payload,
                        headers=headers,
                    )
                    try:
                        resp.raise_for_status()
                    except Exception:
                        logger.error("Nebius embedding error %s: %s", resp.status_code, resp.text)
                        raise
                    data = resp.json()
                embeddings = [item["embedding"] for item in data.get("data", [])]
            else:
                response = self.openai_client.embeddings.create(
                    model=self.embed_model,
                    input=texts
                )
                embeddings = [item.embedding for item in response.data]

            # Ajuste dimensional: alineamos al tamaño configurado (p.ej. 1024) para
            # evitar desbordes con la columna VECTOR en Supabase.
            target_dim = settings.embedding_dimensions
            fixed_embeddings: List[List[float]] = []
            for emb in embeddings:
                if len(emb) > target_dim:
                    fixed_embeddings.append(emb[:target_dim])
                elif len(emb) < target_dim:
                    fixed_embeddings.append(emb + [0.0] * (target_dim - len(emb)))
                else:
                    fixed_embeddings.append(emb)
            
            # Almacenar nuevos embeddings en caché
            for (idx, text), embedding in zip(texts_to_embed, fixed_embeddings):
                self.cache.set(text, embedding)
            
            # Combinar embeddings cacheados y nuevos
            result_embeddings: List[List[float]] = []
            new_idx = 0
            for i in range(len(texts)):
                if i in cached_embeddings:
                    result_embeddings.append(cached_embeddings[i])
                else:
                    result_embeddings.append(fixed_embeddings[new_idx])
                    new_idx += 1

            logger.info(
                f"Generated embeddings for {len(texts)} texts (dim={target_dim}). "
                f"Cache: {len(cached_embeddings)} hits, {len(texts_to_embed)} misses"
            )
            return result_embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector
        """
        embeddings = await self.embed_texts([query])
        return embeddings[0]


# Global service instance
embedding_service = EmbeddingService()
