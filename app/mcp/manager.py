"""
MCP Client Manager - Gestión centralizada del ciclo de vida de clientes MCP.

Proporciona:
- Pool de conexiones con límite de tamaño
- Gestión de ciclo de vida (inicialización, limpieza)
- Cache inteligente de clientes
- Reconexión automática
"""

import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from .clients.base import BaseMCPClient, get_mcp_client
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Gestiona el ciclo de vida de clientes MCP.
    
    Características:
    - Pool de conexiones con límite configurable
    - Cache de clientes inicializados
    - Gestión automática de reconexión
    - Limpieza de recursos
    """
    
    def __init__(
        self,
        settings: Settings,
        max_pool_size: int = 10,
        connection_timeout: int = 30,
    ):
        """
        Inicializa el manager de clientes MCP.
        
        Args:
            settings: Configuración de la aplicación
            max_pool_size: Tamaño máximo del pool de conexiones
            connection_timeout: Timeout para conexiones (segundos)
        """
        self.settings = settings
        self.max_pool_size = max_pool_size
        self.connection_timeout = connection_timeout
        
        # Cache de clientes: {cache_key: (client, last_used, initialized)}
        self._clients: Dict[str, tuple[BaseMCPClient, datetime, bool]] = {}
        
        # Configuración de servidores MCP
        self._servers_config: Optional[List[Dict[str, Any]]] = None
        
    def set_servers_config(self, servers_config: List[Dict[str, Any]]):
        """Establece la configuración de servidores MCP."""
        self._servers_config = servers_config
    
    def _get_cache_key(
        self,
        server_name: str,
        tool_name: Optional[str] = None,
    ) -> str:
        """Genera una clave de cache única para un cliente."""
        return f"{server_name}_{tool_name or ''}"
    
    def _is_client_stale(
        self,
        last_used: datetime,
        max_idle_time: timedelta = timedelta(minutes=30),
    ) -> bool:
        """Verifica si un cliente está inactivo hace demasiado tiempo."""
        return datetime.now() - last_used > max_idle_time
    
    async def get_client(
        self,
        server_name: str,
        server_config: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ) -> Optional[BaseMCPClient]:
        """
        Obtiene o crea un cliente MCP, inicializándolo si es necesario.
        
        Args:
            server_name: Nombre del servidor MCP
            server_config: Configuración específica del servidor
            tool_name: Nombre del tool (opcional, para selección específica)
            
        Returns:
            Cliente MCP inicializado o None si hay error
        """
        cache_key = self._get_cache_key(server_name, tool_name)
        
        # Verificar si ya existe en cache
        if cache_key in self._clients:
            client, last_used, initialized = self._clients[cache_key]
            
            # Verificar si el cliente está inactivo
            if self._is_client_stale(last_used):
                logger.debug(f"Cliente MCP {cache_key} inactivo, limpiando...")
                await self._cleanup_client(cache_key)
            else:
                # Actualizar timestamp y devolver
                self._clients[cache_key] = (client, datetime.now(), initialized)
                return client
        
        # Verificar límite de pool
        if len(self._clients) >= self.max_pool_size:
            logger.warning(
                f"Pool de clientes MCP lleno ({self.max_pool_size}), "
                f"limpiando clientes inactivos..."
            )
            await self.cleanup_stale_clients()
            
            # Si aún está lleno, eliminar el más antiguo
            if len(self._clients) >= self.max_pool_size:
                await self._remove_oldest_client()
        
        # Crear nuevo cliente
        try:
            client = get_mcp_client(
                use_mock=self.settings.use_mock_mcp,
                servers=self._servers_config or [],
                tool_name=tool_name,
                server_config=server_config,
            )
            
            # Inicializar si no es mock
            initialized = False
            if not self.settings.use_mock_mcp and hasattr(client, "initialize"):
                try:
                    await client.initialize()
                    initialized = True
                    logger.debug(f"Cliente MCP {cache_key} inicializado correctamente")
                except Exception as e:
                    logger.warning(
                        f"Error inicializando cliente MCP {server_name}: {e}"
                    )
                    # Devolver cliente sin inicializar (puede funcionar para algunos casos)
            
            # Guardar en cache
            self._clients[cache_key] = (client, datetime.now(), initialized)
            return client
            
        except Exception as e:
            # Evitar recursión infinita en logging - usar solo el mensaje de error
            error_msg = str(e)
            logger.error(f"Error creando cliente MCP {server_name}: {error_msg}")
            return None
    
    async def _cleanup_client(self, cache_key: str):
        """
        Limpia un cliente específico del cache.
        
        Args:
            cache_key: Clave del cliente a limpiar
        """
        if cache_key not in self._clients:
            return
        
        client, _, _ = self._clients[cache_key]
        
        # Intentar cerrar conexiones si el cliente lo soporta
        try:
            if hasattr(client, "close"):
                await client.close()
            elif hasattr(client, "disconnect"):
                await client.disconnect()
        except Exception as e:
            logger.debug(f"Error cerrando cliente {cache_key}: {e}")
        
        del self._clients[cache_key]
        logger.debug(f"Cliente MCP {cache_key} limpiado del cache")
    
    async def _remove_oldest_client(self):
        """Elimina el cliente más antiguo del cache."""
        if not self._clients:
            return
        
        # Encontrar el cliente más antiguo
        oldest_key = min(
            self._clients.keys(),
            key=lambda k: self._clients[k][1]
        )
        
        await self._cleanup_client(oldest_key)
    
    async def cleanup_stale_clients(
        self,
        max_idle_time: timedelta = timedelta(minutes=30),
    ):
        """
        Limpia todos los clientes inactivos.
        
        Args:
            max_idle_time: Tiempo máximo de inactividad antes de limpiar
        """
        stale_keys = [
            key
            for key, (_, last_used, _) in self._clients.items()
            if self._is_client_stale(last_used, max_idle_time)
        ]
        
        for key in stale_keys:
            await self._cleanup_client(key)
        
        if stale_keys:
            logger.info(f"Limpiados {len(stale_keys)} clientes MCP inactivos")
    
    async def cleanup_all(self):
        """Limpia todos los clientes del cache."""
        keys = list(self._clients.keys())
        for key in keys:
            await self._cleanup_client(key)
        
        logger.info("Todos los clientes MCP limpiados")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del manager.
        
        Returns:
            Diccionario con estadísticas (tamaño del pool, clientes activos, etc.)
        """
        now = datetime.now()
        active_clients = [
            key
            for key, (_, last_used, _) in self._clients.items()
            if not self._is_client_stale(last_used)
        ]
        
        return {
            "total_clients": len(self._clients),
            "active_clients": len(active_clients),
            "max_pool_size": self.max_pool_size,
            "cache_keys": list(self._clients.keys()),
        }


# Instancia global del manager (se inicializará en startup)
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager(settings: Optional[Settings] = None) -> MCPClientManager:
    """
    Obtiene la instancia global del MCP Client Manager.
    
    Args:
        settings: Configuración (opcional, solo para inicialización)
        
    Returns:
        Instancia del manager
    """
    global _mcp_manager
    
    if _mcp_manager is None:
        if settings is None:
            from ..config.settings import get_settings
            settings = get_settings()
        _mcp_manager = MCPClientManager(settings)
    
    return _mcp_manager


def reset_mcp_manager():
    """Resetea el manager global (útil para tests)."""
    global _mcp_manager
    _mcp_manager = None





