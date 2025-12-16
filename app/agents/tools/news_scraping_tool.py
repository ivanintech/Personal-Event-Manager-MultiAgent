"""
News Scraping Tool: Scrapea noticias relevantes y extrae eventos mencionados.

Adaptado del proyecto final del curso para Event Manager.
Scrapea sitios de noticias configurables y busca menciones de eventos/conferencias.
"""

import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import BaseTool
from .web_scraping_tool import web_scraping_tool

logger = logging.getLogger(__name__)


class NewsScrapingTool(BaseTool):
    """
    Tool para scrapear noticias y extraer eventos mencionados.
    
    Funcionalidades:
    - Scrapea sitios de noticias configurables
    - Busca menciones de eventos/conferencias usando keywords
    - Extrae información de eventos de las noticias
    - Retorna eventos encontrados
    """

    # Keywords comunes para identificar eventos en noticias
    EVENT_KEYWORDS = [
        "conferencia", "conference", "evento", "event", "meetup", "workshop",
        "seminario", "seminar", "summit", "congreso", "congress", "exposición",
        "exhibition", "feria", "fair", "festival", "hackathon", "webinar"
    ]

    # Sitios de noticias comunes (configurables)
    DEFAULT_NEWS_SITES = [
        "https://techcrunch.com",
        "https://news.ycombinator.com",
        "https://www.theverge.com",
    ]

    @property
    def name(self) -> str:
        return "scrape_news_for_events"

    @property
    def description(self) -> str:
        return (
            "Scrapea sitios de noticias y busca menciones de eventos/conferencias. "
            "Extrae información de eventos mencionados en artículos de noticias. "
            "Útil para descubrir eventos relevantes para el usuario."
        )

    def _extract_event_mentions(self, text: str, title: str) -> List[Dict[str, Any]]:
        """
        Extrae menciones de eventos del texto de una noticia.
        
        Args:
            text: Texto completo de la noticia
            title: Título de la noticia
            
        Returns:
            Lista de eventos encontrados con información extraída
        """
        events = []
        
        # Combinar título y texto
        full_text = f"{title} {text}".lower()
        
        # Buscar keywords de eventos
        found_keywords = []
        for keyword in self.EVENT_KEYWORDS:
            if keyword.lower() in full_text:
                found_keywords.append(keyword)
        
        if not found_keywords:
            return events
        
        # Si hay keywords, intentar extraer información del evento
        # Buscar patrones comunes:
        # - "Conferencia X el Y de Z"
        # - "Event Y on date"
        # - "Summit in location"
        
        # Patrón para extraer nombre del evento y fecha
        event_patterns = [
            r'(?:' + '|'.join(found_keywords) + r')\s+([^,\.]+?)\s+(?:el|on|in|at)\s+([^,\.]+)',
            r'([A-Z][^,\.]+?)\s+(?:' + '|'.join(found_keywords) + r')\s+([^,\.]+)',
        ]
        
        for pattern in event_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                event_name = match.group(1).strip()
                event_info = match.group(2).strip()
                
                # Intentar extraer fecha
                date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}', event_info)
                date = date_match.group(0) if date_match else None
                
                # Intentar extraer ubicación
                location_keywords = ['en', 'in', 'at', 'Madrid', 'Barcelona', 'San Francisco', 'New York']
                location = None
                for loc_keyword in location_keywords:
                    if loc_keyword.lower() in event_info.lower():
                        location = loc_keyword
                        break
                
                events.append({
                    "name": event_name,
                    "date": date,
                    "location": location,
                    "source_text": match.group(0),
                    "keywords_found": found_keywords
                })
        
        # Si no encontramos eventos estructurados, pero hay keywords, crear evento básico
        if not events and found_keywords:
            events.append({
                "name": title,  # Usar título como nombre del evento
                "date": None,
                "location": None,
                "source_text": title,
                "keywords_found": found_keywords
            })
        
        return events

    async def execute(
        self,
        sites: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_articles: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Scrapea noticias y busca eventos mencionados.
        
        Args:
            sites: Lista de URLs de sitios de noticias (opcional, usa defaults si no se proporciona)
            keywords: Keywords adicionales para buscar eventos (opcional)
            max_articles: Máximo de artículos a procesar por sitio
            
        Returns:
            Dict con:
                - success: bool
                - events: Lista de eventos encontrados
                - articles_processed: Número de artículos procesados
                - result: Mensaje descriptivo
        """
        if sites is None:
            sites = self.DEFAULT_NEWS_SITES
        
        if keywords:
            # Añadir keywords personalizados a los defaults
            self.EVENT_KEYWORDS.extend([k.lower() for k in keywords])
        
        all_events = []
        articles_processed = 0
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for site_url in sites:
                    try:
                        logger.info(f"Scrapeando sitio de noticias: {site_url}")
                        
                        # Obtener página principal
                        response = await client.get(site_url, headers=headers)
                        response.raise_for_status()
                        
                        soup = BeautifulSoup(response.text, "lxml" if "lxml" in str(BeautifulSoup.__init__) else "html.parser")
                        
                        # Buscar enlaces a artículos (patrones comunes)
                        article_links = []
                        
                        # Buscar enlaces en elementos comunes de noticias
                        for link in soup.find_all("a", href=True):
                            href = link.get("href", "")
                            text = link.get_text(strip=True)
                            
                            # Filtrar enlaces que parecen artículos
                            if any(indicator in href.lower() for indicator in ["/article/", "/news/", "/post/", "/story/"]):
                                full_url = urljoin(site_url, href)
                                article_links.append((full_url, text))
                        
                        # Limitar número de artículos
                        article_links = article_links[:max_articles]
                        
                        # Procesar cada artículo
                        for article_url, article_title in article_links:
                            try:
                                # Scrapear artículo usando web_scraping_tool
                                scrape_result = await web_scraping_tool.execute(
                                    url=article_url,
                                    extract_image=False,
                                    extract_text=True
                                )
                                
                                if not scrape_result.get("success"):
                                    continue
                                
                                article_text = scrape_result.get("text_content", "")
                                article_title = scrape_result.get("title", article_title)
                                
                                # Extraer eventos mencionados
                                events = self._extract_event_mentions(article_text, article_title)
                                
                                # Añadir información de fuente
                                for event in events:
                                    event["source_url"] = article_url
                                    event["source_article_title"] = article_title
                                
                                all_events.extend(events)
                                articles_processed += 1
                                
                            except Exception as e:
                                logger.warning(f"Error procesando artículo {article_url}: {e}")
                                continue
                        
                    except Exception as e:
                        logger.error(f"Error scrapeando sitio {site_url}: {e}")
                        continue
            
            logger.info(f"Procesados {articles_processed} artículos, encontrados {len(all_events)} eventos")
            
            return {
                "success": True,
                "events": all_events,
                "articles_processed": articles_processed,
                "sites_scraped": len(sites),
                "result": f"Encontrados {len(all_events)} eventos en {articles_processed} artículos"
            }
            
        except Exception as e:
            logger.error(f"Error en news scraping: {e}", exc_info=True)
            return self._error_response(f"Error scrapeando noticias: {str(e)}")


# Instancia global del tool
news_scraping_tool = NewsScrapingTool()




