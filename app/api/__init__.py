"""
Routers de API para endpoints REST y WebSocket.
Se registran desde app.main.
"""

from .routes import router as api_router
from .ws import router as ws_router
from .events import router as events_router
from .calendly import router as calendly_router
from .whatsapp import router as whatsapp_router
from .whatsapp_batch import router as whatsapp_batch_router

__all__ = ["api_router", "ws_router", "events_router", "calendly_router", "whatsapp_router", "whatsapp_batch_router"]

