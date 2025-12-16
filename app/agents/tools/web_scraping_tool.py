"""
Web Scraping Tool: Extrae contenido de URLs usando requests + BeautifulSoup.

Extrae título, descripción y primera imagen de una página web.
Útil para procesar URLs encontradas en mensajes y generar posts.
"""

import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import BaseTool

logger = logging.getLogger(__name__)


class WebScrapingTool(BaseTool):
    """
    Tool para extraer contenido de páginas web.
    
    Extrae:
    - Título (Open Graph, Twitter Card, <title>, h1)
    - Descripción (Open Graph, Twitter Card, meta description)
    - Primera imagen (Open Graph, Twitter Card, primera <img>)
    - Contenido básico del texto
    """

    @property
    def name(self) -> str:
        return "scrape_web_content"

    @property
    def description(self) -> str:
        return (
            "Extrae contenido de una página web (título, descripción, imagen). "
            "Útil para procesar URLs y generar resúmenes de artículos o noticias."
        )

    def _extract_meta_tag(self, soup: BeautifulSoup, property_name: str, attribute: str = "property") -> Optional[str]:
        """
        Extrae el valor de una meta tag.
        
        Args:
            soup: BeautifulSoup object
            property_name: Nombre de la propiedad (ej: "og:title")
            attribute: Atributo a buscar ("property" o "name")
            
        Returns:
            Valor de la meta tag o None
        """
        tag = soup.find("meta", {attribute: property_name})
        if tag:
            return tag.get("content", "").strip()
        return None

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extrae el título de la página con prioridad:
        1. Open Graph og:title
        2. Twitter Card twitter:title
        3. <title> tag
        4. Primer <h1>
        5. URL como fallback
        """
        # Open Graph
        og_title = self._extract_meta_tag(soup, "og:title")
        if og_title:
            return og_title

        # Twitter Card
        twitter_title = self._extract_meta_tag(soup, "twitter:title", attribute="name")
        if twitter_title:
            return twitter_title

        # <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Primer <h1>
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.string:
            return h1_tag.string.strip()

        # Fallback: usar dominio de la URL
        parsed = urlparse(url)
        return parsed.netloc or url

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extrae la descripción de la página con prioridad:
        1. Open Graph og:description
        2. Twitter Card twitter:description
        3. Meta description
        """
        # Open Graph
        og_desc = self._extract_meta_tag(soup, "og:description")
        if og_desc:
            return og_desc

        # Twitter Card
        twitter_desc = self._extract_meta_tag(soup, "twitter:description", attribute="name")
        if twitter_desc:
            return twitter_desc

        # Meta description
        meta_desc = self._extract_meta_tag(soup, "description", attribute="name")
        if meta_desc:
            return meta_desc

        return None

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """
        Extrae la imagen destacada de la página con prioridad:
        1. Open Graph og:image
        2. Twitter Card twitter:image
        3. Primera imagen grande en el contenido
        """
        # Open Graph
        og_image = self._extract_meta_tag(soup, "og:image")
        if og_image:
            # Convertir URL relativa a absoluta
            return urljoin(base_url, og_image)

        # Twitter Card
        twitter_image = self._extract_meta_tag(soup, "twitter:image", attribute="name")
        if twitter_image:
            return urljoin(base_url, twitter_image)

        # Buscar primera imagen grande en el contenido
        # Priorizar imágenes con atributos que indican importancia
        img_tags = soup.find_all("img", src=True)
        for img in img_tags:
            src = img.get("src", "")
            if not src:
                continue

            # Filtrar imágenes pequeñas (probablemente iconos)
            width = img.get("width")
            height = img.get("height")
            if width and height:
                try:
                    if int(width) < 200 or int(height) < 200:
                        continue
                except (ValueError, TypeError):
                    pass

            # Filtrar imágenes comunes que no son contenido
            src_lower = src.lower()
            if any(skip in src_lower for skip in ["logo", "icon", "avatar", "favicon"]):
                continue

            # Convertir URL relativa a absoluta
            return urljoin(base_url, src)

        return None

    def _extract_text_content(self, soup: BeautifulSoup, max_length: int = 500) -> str:
        """
        Extrae el texto principal del contenido.
        Elimina scripts, styles y otros elementos no deseados.
        """
        # Eliminar scripts y styles
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()

        # Obtener texto
        text = soup.get_text(separator=" ", strip=True)

        # Limpiar espacios múltiples
        text = re.sub(r'\s+', ' ', text)

        # Limitar longitud
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text.strip()

    async def execute(
        self,
        url: str,
        extract_image: bool = True,
        extract_text: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extrae contenido de una URL.
        
        Args:
            url: URL de la página a scrapear
            extract_image: Si True, extrae imagen destacada
            extract_text: Si True, extrae texto del contenido (más lento)
            
        Returns:
            Dict con:
                - success: bool
                - title: str - Título de la página
                - description: Optional[str] - Descripción
                - image_url: Optional[str] - URL de imagen destacada
                - text_content: Optional[str] - Texto del contenido (si extract_text=True)
                - result: str - Mensaje descriptivo
        """
        if not url or not isinstance(url, str):
            return self._error_response("El parámetro 'url' es requerido y debe ser un string")

        # Validar que sea una URL válida
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return self._error_response(f"URL inválida: {url}")
        except Exception as e:
            return self._error_response(f"Error validando URL: {str(e)}")

        try:
            # Headers para parecer un navegador real
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            }

            # Hacer request con timeout
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Parsear HTML
                soup = BeautifulSoup(response.text, "lxml" if "lxml" in str(BeautifulSoup.__init__) else "html.parser")

                # Extraer contenido
                title = self._extract_title(soup, url)
                description = self._extract_description(soup)
                image_url = None
                text_content = None

                if extract_image:
                    image_url = self._extract_image(soup, url)

                if extract_text:
                    text_content = self._extract_text_content(soup)

                logger.info(f"Extraído contenido de {url}: título='{title[:50]}...', desc={bool(description)}, img={bool(image_url)}")

                return {
                    "success": True,
                    "title": title,
                    "description": description,
                    "image_url": image_url,
                    "text_content": text_content,
                    "result": f"Contenido extraído exitosamente: {title}"
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al scrapear {url}: {e.response.status_code}")
            return self._error_response(f"Error HTTP {e.response.status_code} al acceder a la URL")

        except httpx.TimeoutException:
            logger.error(f"Timeout al scrapear {url}")
            return self._error_response("Timeout al acceder a la URL (más de 30 segundos)")

        except Exception as e:
            logger.error(f"Error scrapeando {url}: {e}", exc_info=True)
            return self._error_response(f"Error al procesar la URL: {str(e)}")


# Instancia global del tool
web_scraping_tool = WebScrapingTool()




