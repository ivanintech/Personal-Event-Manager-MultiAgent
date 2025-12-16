"""
Servicio de métricas y observabilidad para el agente.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class MetricsService:
    """Servicio para recopilar métricas de ejecución del agente."""

    def __init__(self):
        self.tool_call_times: List[float] = []
        self.tool_success_count = defaultdict(int)
        self.tool_error_count = defaultdict(int)
        self.retry_count = defaultdict(int)
        self.rag_retrieval_times: List[float] = []
        self.llm_call_times: List[float] = []
        self.total_requests = 0
        self.total_errors = 0
        
        # Métricas de voz
        self.voice_stt_times: List[float] = []
        self.voice_stt_errors = 0
        self.voice_agent_times: List[float] = []
        self.voice_agent_errors = 0
        self.voice_tts_times: List[float] = []
        self.voice_tts_first_chunk_times: List[float] = []
        self.voice_tts_errors = 0
        self.voice_request_times: List[float] = []

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """Registra una llamada a tool."""
        self.tool_call_times.append(duration_ms)
        if success:
            self.tool_success_count[tool_name] += 1
        else:
            self.tool_error_count[tool_name] += 1
            if error:
                logger.warning(f"Tool {tool_name} error: {error}")

    def record_retry(self, tool_name: str):
        """Registra un reintento de tool."""
        self.retry_count[tool_name] += 1

    def record_rag_retrieval(self, duration_ms: float):
        """Registra tiempo de recuperación RAG."""
        self.rag_retrieval_times.append(duration_ms)

    def record_llm_call(self, duration_ms: float):
        """Registra tiempo de llamada LLM."""
        self.llm_call_times.append(duration_ms)

    def record_request(self, success: bool = True):
        """Registra una petición completa."""
        self.total_requests += 1
        if not success:
            self.total_errors += 1
    
    def record_voice_stt(self, duration_ms: float, success: bool = True):
        """Registra tiempo de STT (Speech-to-Text)."""
        self.voice_stt_times.append(duration_ms)
        if not success:
            self.voice_stt_errors += 1
    
    def record_voice_agent(self, duration_ms: float, success: bool = True):
        """Registra tiempo de procesamiento del agente."""
        self.voice_agent_times.append(duration_ms)
        if not success:
            self.voice_agent_errors += 1
    
    def record_voice_tts(
        self, 
        duration_ms: float, 
        success: bool = True,
        first_chunk_latency_ms: Optional[float] = None
    ):
        """Registra tiempo de TTS (Text-to-Speech)."""
        self.voice_tts_times.append(duration_ms)
        if first_chunk_latency_ms is not None:
            self.voice_tts_first_chunk_times.append(first_chunk_latency_ms)
        if not success:
            self.voice_tts_errors += 1
    
    def record_voice_request(self, duration_ms: float):
        """Registra latencia end-to-end de una petición de voz."""
        self.voice_request_times.append(duration_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas agregadas."""
        avg_tool_time = (
            sum(self.tool_call_times) / len(self.tool_call_times)
            if self.tool_call_times
            else 0
        )
        avg_rag_time = (
            sum(self.rag_retrieval_times) / len(self.rag_retrieval_times)
            if self.rag_retrieval_times
            else 0
        )
        avg_llm_time = (
            sum(self.llm_call_times) / len(self.llm_call_times)
            if self.llm_call_times
            else 0
        )

        total_tool_calls = sum(self.tool_success_count.values()) + sum(
            self.tool_error_count.values()
        )
        success_rate = (
            sum(self.tool_success_count.values()) / total_tool_calls
            if total_tool_calls > 0
            else 0
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "requests": {
                "total": self.total_requests,
                "errors": self.total_errors,
                "success_rate": (
                    (self.total_requests - self.total_errors) / self.total_requests
                    if self.total_requests > 0
                    else 0
                ),
            },
            "tools": {
                "total_calls": total_tool_calls,
                "success_count": dict(self.tool_success_count),
                "error_count": dict(self.tool_error_count),
                "retry_count": dict(self.retry_count),
                "avg_duration_ms": avg_tool_time,
                "success_rate": success_rate,
            },
            "rag": {
                "total_retrievals": len(self.rag_retrieval_times),
                "avg_duration_ms": avg_rag_time,
            },
            "llm": {
                "total_calls": len(self.llm_call_times),
                "avg_duration_ms": avg_llm_time,
            },
            "embedding_cache": self._get_embedding_cache_stats(),
            "voice": self._get_voice_metrics(),
        }
    
    def _get_voice_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de voz agregadas."""
        avg_stt_time = (
            sum(self.voice_stt_times) / len(self.voice_stt_times)
            if self.voice_stt_times
            else 0
        )
        avg_agent_time = (
            sum(self.voice_agent_times) / len(self.voice_agent_times)
            if self.voice_agent_times
            else 0
        )
        avg_tts_time = (
            sum(self.voice_tts_times) / len(self.voice_tts_times)
            if self.voice_tts_times
            else 0
        )
        avg_first_chunk_time = (
            sum(self.voice_tts_first_chunk_times) / len(self.voice_tts_first_chunk_times)
            if self.voice_tts_first_chunk_times
            else 0
        )
        avg_request_time = (
            sum(self.voice_request_times) / len(self.voice_request_times)
            if self.voice_request_times
            else 0
        )
        
        return {
            "stt": {
                "total_calls": len(self.voice_stt_times),
                "avg_duration_ms": round(avg_stt_time, 2),
                "errors": self.voice_stt_errors,
            },
            "agent": {
                "total_calls": len(self.voice_agent_times),
                "avg_duration_ms": round(avg_agent_time, 2),
                "errors": self.voice_agent_errors,
            },
            "tts": {
                "total_calls": len(self.voice_tts_times),
                "avg_duration_ms": round(avg_tts_time, 2),
                "avg_first_chunk_latency_ms": round(avg_first_chunk_time, 2) if avg_first_chunk_time > 0 else None,
                "errors": self.voice_tts_errors,
            },
            "end_to_end": {
                "total_requests": len(self.voice_request_times),
                "avg_duration_ms": round(avg_request_time, 2),
            },
        }
    
    def _get_embedding_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché de embeddings."""
        try:
            from .embedding import embedding_service
            return embedding_service.cache.get_stats()
        except Exception:
            return {"enabled": False, "error": "Cache not available"}

    def reset(self):
        """Resetea todas las métricas."""
        self.tool_call_times.clear()
        self.tool_success_count.clear()
        self.tool_error_count.clear()
        self.retry_count.clear()
        self.rag_retrieval_times.clear()
        self.llm_call_times.clear()
        self.total_requests = 0
        self.total_errors = 0
        
        # Reset métricas de voz
        self.voice_stt_times.clear()
        self.voice_stt_errors = 0
        self.voice_agent_times.clear()
        self.voice_agent_errors = 0
        self.voice_tts_times.clear()
        self.voice_tts_first_chunk_times.clear()
        self.voice_tts_errors = 0
        self.voice_request_times.clear()


# Instancia global
metrics_service = MetricsService()


