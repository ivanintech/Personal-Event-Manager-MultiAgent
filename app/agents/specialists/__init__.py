"""
Agentes especializados para el sistema multiagente.
"""

from .calendar_agent import CalendarAgent
from .email_agent import EmailAgent
from .comms_agent import CommsAgent
from .event_agent import EventAgent

__all__ = [
    "CalendarAgent",
    "EmailAgent",
    "CommsAgent",
    "EventAgent",
]



