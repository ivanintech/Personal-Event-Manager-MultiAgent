"""
URL Extraction Tool: Extrae URLs de texto usando regex.

Basado en el patrón de herramientas del curso y ejemplos de MCP.
Referencia: https://github.com/juananpe/google-image-search-mcp-python
"""

import logging
import re
from typing import Dict, Any, List, Set
from urllib.parse import urlparse, urlunparse

from .base import BaseTool

logger = logging.getLogger(__name__)


class URLExtractionTool(BaseTool):
    """
    Tool para extraer URLs de texto.
    
    Extrae todas las URLs válidas de un texto, las valida y filtra duplicados.
    Útil para procesar mensajes de Telegram/WhatsApp y encontrar enlaces.
    """

    @property
    def name(self) -> str:
        return "extract_urls"

    @property
    def description(self) -> str:
        return (
            "Extrae todas las URLs válidas de un texto. "
            "Devuelve una lista de URLs únicas y validadas. "
            "Útil para encontrar enlaces en mensajes de Telegram, WhatsApp o emails."
        )

    def _is_valid_url(self, url: str) -> bool:
        """
        Valida si una URL es válida y accesible.
        
        Args:
            url: URL a validar
            
        Returns:
            True si la URL es válida, False en caso contrario
        """
        try:
            result = urlparse(url)
            # Debe tener scheme (http/https) y netloc (dominio)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False

    def _normalize_url(self, url: str) -> str:
        """
        Normaliza una URL eliminando parámetros de tracking y fragmentos.
        
        Args:
            url: URL a normalizar
            
        Returns:
            URL normalizada
        """
        try:
            parsed = urlparse(url)
            # Eliminar fragmento (#) y algunos parámetros de tracking comunes
            # Mantener parámetros importantes pero eliminar UTM, etc.
            query_params = []
            if parsed.query:
                for param in parsed.query.split('&'):
                    key = param.split('=')[0]
                    # Mantener parámetros importantes, eliminar tracking
                    if not any(track in key.lower() for track in ['utm_', 'ref=', 'source=']):
                        query_params.append(param)
            
            normalized_query = '&'.join(query_params) if query_params else ''
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                normalized_query,
                ''  # Sin fragmento
            ))
            return normalized
        except Exception as e:
            logger.warning(f"Error normalizando URL {url}: {e}")
            return url

    async def execute(
        self,
        text: str,
        normalize: bool = True,
        remove_duplicates: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extrae URLs de un texto.
        
        Args:
            text: Texto del cual extraer URLs
            normalize: Si True, normaliza URLs (elimina tracking params)
            remove_duplicates: Si True, elimina URLs duplicadas
            
        Returns:
            Dict con:
                - success: bool
                - urls: List[str] - Lista de URLs encontradas
                - count: int - Número de URLs encontradas
                - result: str - Mensaje descriptivo
        """
        if not text or not isinstance(text, str):
            return self._error_response("El parámetro 'text' es requerido y debe ser un string")

        try:
            # Patrón regex para URLs (http/https)
            # Basado en: https://stackoverflow.com/questions/3809401/what-is-a-good-regular-expression-to-match-a-url
            url_pattern = re.compile(
                r'https?://'  # http:// o https://
                r'(?:[-\w.])+'  # Dominio (ej: example.com, sub.example.com)
                r'(?::[0-9]+)?'  # Puerto opcional (ej: :8080)
                r'(?:/(?:[\w/_.])*)?'  # Path opcional
                r'(?:\?(?:[\w&=%.])*)?'  # Query string opcional
                r'(?:#(?:[\w.])*)?',  # Fragment opcional
                re.IGNORECASE
            )

            # Encontrar todas las URLs
            found_urls = url_pattern.findall(text)
            
            if not found_urls:
                return {
                    "success": True,
                    "urls": [],
                    "count": 0,
                    "result": "No se encontraron URLs en el texto"
                }

            # Validar URLs
            valid_urls = []
            for url in found_urls:
                if self._is_valid_url(url):
                    # Normalizar si se solicita
                    processed_url = self._normalize_url(url) if normalize else url
                    valid_urls.append(processed_url)

            if not valid_urls:
                return {
                    "success": True,
                    "urls": [],
                    "count": 0,
                    "result": "Se encontraron URLs pero ninguna es válida"
                }

            # Eliminar duplicados si se solicita
            if remove_duplicates:
                # Usar dict para preservar orden (Python 3.7+)
                seen: Set[str] = set()
                unique_urls = []
                for url in valid_urls:
                    if url not in seen:
                        seen.add(url)
                        unique_urls.append(url)
                valid_urls = unique_urls

            logger.info(f"Extraídas {len(valid_urls)} URLs válidas de {len(found_urls)} encontradas")

            return {
                "success": True,
                "urls": valid_urls,
                "count": len(valid_urls),
                "result": f"Se encontraron {len(valid_urls)} URL(s) válida(s)"
            }

        except Exception as e:
            logger.error(f"Error extrayendo URLs: {e}", exc_info=True)
            return self._error_response(f"Error extrayendo URLs: {str(e)}")


# Instancia global del tool
url_extraction_tool = URLExtractionTool()




