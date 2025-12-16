"""
Service Container - Dependency Injection Container.

Proporciona un contenedor centralizado para gestionar instancias de servicios,
mejorando testabilidad y control del ciclo de vida.
"""

import logging
from typing import Optional

from ..config.settings import Settings, get_settings
from ..config.database import Database, db
from ..services.rag import RAGService
from ..services.chat import ChatService
from ..services.embedding import EmbeddingService
from ..services.metrics import MetricsService
from ..agents.orchestrator import AgentService
from ..mcp.manager import MCPClientManager, get_mcp_manager

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Contenedor de dependencias para servicios de la aplicación.
    
    Gestiona el ciclo de vida de servicios y proporciona acceso centralizado.
    Útil para testing (puede inyectar mocks) y control de recursos.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa el contenedor de servicios.
        
        Args:
            settings: Configuración (opcional, usa get_settings() si no se proporciona)
        """
        self._settings = settings or get_settings()
        self._database: Optional[Database] = None
        self._rag_service: Optional[RAGService] = None
        self._chat_service: Optional[ChatService] = None
        self._embedding_service: Optional[EmbeddingService] = None
        self._metrics_service: Optional[MetricsService] = None
        self._agent_service: Optional[AgentService] = None
        self._mcp_manager: Optional[MCPClientManager] = None
        
        logger.debug("ServiceContainer inicializado")
    
    @property
    def settings(self) -> Settings:
        """Obtiene la configuración de la aplicación."""
        return self._settings
    
    @property
    def database(self) -> Database:
        """Obtiene la instancia de la base de datos."""
        if self._database is None:
            self._database = db
        return self._database
    
    @property
    def rag_service(self) -> RAGService:
        """Obtiene el servicio RAG (lazy initialization)."""
        if self._rag_service is None:
            # Inyectar dependencias para mejor arquitectura
            self._rag_service = RAGService(
                embedding_service=self.embedding_service,
                chat_service=self.chat_service
            )
            logger.debug("RAGService inicializado con dependencias inyectadas")
        return self._rag_service
    
    @property
    def chat_service(self) -> ChatService:
        """Obtiene el servicio de chat (lazy initialization)."""
        if self._chat_service is None:
            self._chat_service = ChatService()
            logger.debug("ChatService inicializado")
        return self._chat_service
    
    @property
    def embedding_service(self) -> EmbeddingService:
        """Obtiene el servicio de embeddings (lazy initialization)."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
            logger.debug("EmbeddingService inicializado")
        return self._embedding_service
    
    @property
    def metrics_service(self) -> MetricsService:
        """Obtiene el servicio de métricas (lazy initialization)."""
        if self._metrics_service is None:
            self._metrics_service = MetricsService()
            logger.debug("MetricsService inicializado")
        return self._metrics_service
    
    @property
    def agent_service(self) -> AgentService:
        """Obtiene el servicio de agentes (lazy initialization)."""
        if self._agent_service is None:
            # Inyectar dependencias para mejor arquitectura
            self._agent_service = AgentService(
                embedding_service=self.embedding_service,
                metrics_service=self.metrics_service
            )
            logger.debug("AgentService inicializado con dependencias inyectadas")
        return self._agent_service
    
    @property
    def mcp_manager(self) -> MCPClientManager:
        """Obtiene el manager de clientes MCP (lazy initialization)."""
        if self._mcp_manager is None:
            self._mcp_manager = get_mcp_manager(self._settings)
            logger.debug("MCPClientManager obtenido")
        return self._mcp_manager
    
    def reset(self):
        """
        Resetea todas las instancias (útil para testing).
        """
        self._rag_service = None
        self._chat_service = None
        self._embedding_service = None
        self._metrics_service = None
        self._agent_service = None
        self._mcp_manager = None
        logger.debug("ServiceContainer reseteado")


# Instancia global del contenedor (se inicializará en startup)
_container: Optional[ServiceContainer] = None


def get_container(settings: Optional[Settings] = None) -> ServiceContainer:
    """
    Obtiene la instancia global del contenedor de servicios.
    
    Args:
        settings: Configuración (opcional, solo para inicialización)
        
    Returns:
        Instancia del contenedor
    """
    global _container
    
    if _container is None:
        if settings is None:
            settings = get_settings()
        _container = ServiceContainer(settings)
        logger.info("ServiceContainer global inicializado")
    
    return _container


def reset_container():
    """Resetea el contenedor global (útil para tests)."""
    global _container
    if _container is not None:
        _container.reset()
    _container = None
    logger.debug("ServiceContainer global reseteado")

