# Directory: yt-agentic-rag/app/schemas/tool_schemas.py

"""
Tool Schemas - LLM Function Calling Definitions.

This file defines the tools available to the agent in OpenAI's
function-calling format. The LLM uses these definitions to:
- Understand what tools are available
- Know what parameters each tool requires
- Generate valid tool calls

When adding a new tool, add its definition to TOOL_DEFINITIONS.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class ToolName(str, Enum):
    """
    Available tool names in the system.
    Add new tools here as they are implemented.
    """
    CREATE_CALENDAR_EVENT = "create_calendar_event"
    SEND_EMAIL = "send_email"
    LIST_AGENDA_EVENTS = "list_agenda_events"
    CONFIRM_AGENDA_EVENT = "confirm_agenda_event"
    LIST_CAL_EVENTS = "list_cal_events"
    EXTRACT_URLS = "extract_urls"
    SCRAPE_WEB_CONTENT = "scrape_web_content"
    # Future tools can be added here:
    # SEARCH_AVAILABILITY = "search_availability"
    # UPDATE_USER_PROFILE = "update_user_profile"
    # LOOKUP_CUSTOMER_INFO = "lookup_customer_info"


class ToolParameter(BaseModel):
    """Schema for a single tool parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, array, etc.)")
    description: str = Field(..., description="Description of the parameter")
    required: bool = Field(default=True, description="Whether the parameter is required")
    enum: Optional[List[str]] = Field(default=None, description="Allowed values if restricted")


class ToolDefinition(BaseModel):
    """Schema for defining a tool available to the agent."""
    name: ToolName = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Human-readable description of the tool")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")


class ToolCall(BaseModel):
    """Represents a tool call made by the agent."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    call_id: str = Field(
        default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}",
        description="Unique identifier for this tool call"
    )


class ToolResult(BaseModel):
    """Result from executing a tool."""
    call_id: str = Field(..., description="ID of the tool call this result is for")
    tool_name: str = Field(..., description="Name of the tool that was executed")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    result: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Tool result data if successful"
    )
    error: Optional[str] = Field(
        default=None, 
        description="Error message if execution failed"
    )


# ============================================================================
# TOOL DEFINITIONS - OpenAI Function Calling Format
# ============================================================================
# These definitions tell the LLM what tools are available and how to use them.
# Format follows OpenAI's function calling specification.

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_agenda_events",
            "description": (
                "Lista las próximas citas importantes almacenadas en la agenda (Supabase). "
                "Devuelve eventos propuestos/confirmados que el agente ha extraído o creado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de eventos a devolver (por defecto 5)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_agenda_event",
            "description": (
                "Confirma una cita propuesta creando el evento en Google Calendar y actualizando Supabase "
                "(extracted_events.status=confirmed, calendar_events insert/update)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "ID del extracted_event a confirmar"
                    }
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_cal_events",
            "description": (
                "Lista eventos confirmados en Google Calendar en la ventana próxima (default 14 días)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Días hacia adelante a consultar (default 14)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados (default 10)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Create a calendar event/meeting on Google Calendar. "
                "Use this when the user wants to schedule a meeting, appointment, or call. "
                "If the user mentions a 'standard consultation' or similar, check the RAG context "
                "for default durations before setting the end time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Title/summary of the event (e.g., 'Consultation Call with John')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the event (optional)"
                    },
                    "start_datetime": {
                        "type": "string",
                        "description": (
                            "Start date and time in ISO 8601 format "
                            "(e.g., '2024-12-15T14:00:00')"
                        )
                    },
                    "end_datetime": {
                        "type": "string",
                        "description": (
                            "End date and time in ISO 8601 format "
                            "(e.g., '2024-12-15T15:00:00')"
                        )
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses"
                    },
                    "timezone": {
                        "type": "string",
                        "description": (
                            "Timezone for the event (e.g., 'America/New_York'). "
                            "Defaults to UTC if not specified."
                        )
                    }
                },
                "required": ["summary", "start_datetime", "end_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": (
                "Send an email to a recipient. Use this when the user wants to send "
                "a confirmation, follow-up, notification, or any email communication."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text)"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_urls",
            "description": (
                "Extrae todas las URLs válidas de un texto. "
                "Útil para encontrar enlaces en mensajes de Telegram, WhatsApp o emails. "
                "Devuelve una lista de URLs únicas y validadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Texto del cual extraer URLs"
                    },
                    "normalize": {
                        "type": "boolean",
                        "description": (
                            "Si es true, normaliza URLs eliminando parámetros de tracking "
                            "(por defecto true)"
                        )
                    },
                    "remove_duplicates": {
                        "type": "boolean",
                        "description": (
                            "Si es true, elimina URLs duplicadas (por defecto true)"
                        )
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_web_content",
            "description": (
                "Extrae contenido de una página web (título, descripción, imagen). "
                "Útil para procesar URLs y generar resúmenes de artículos o noticias. "
                "Extrae título, descripción (Open Graph, Twitter Card, meta tags) y imagen destacada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL de la página web a scrapear"
                    },
                    "extract_image": {
                        "type": "boolean",
                        "description": (
                            "Si es true, extrae la imagen destacada de la página "
                            "(por defecto true)"
                        )
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": (
                            "Si es true, extrae el texto del contenido "
                            "(más lento, por defecto false)"
                        )
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": (
                "Busca emails vía IMAP. "
                "Parámetros: 'query' (criterio IMAP: 'ALL', 'UNSEEN', 'FROM user@example.com', 'SUBJECT texto', etc.), "
                "'folder' (carpeta, default: 'INBOX'), 'max_results' (default: 10)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Criterio de búsqueda IMAP (ej: 'ALL', 'UNSEEN', 'FROM user@example.com', 'SUBJECT texto')"
                    },
                    "folder": {
                        "type": "string",
                        "description": "Carpeta de email a buscar (default: 'INBOX')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": (
                "Lee un email específico vía IMAP. "
                "Parámetros: 'email_id' (ID del email), 'folder' (carpeta, default: 'INBOX')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "ID del email a leer"
                    },
                    "folder": {
                        "type": "string",
                        "description": "Carpeta de email (default: 'INBOX')"
                    }
                },
                "required": ["email_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendly_event",
            "description": (
                "Crea un evento programado en Calendly. "
                "Requiere event_type_uri, invitee_email, y opcionalmente start_time/end_time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type_uri": {
                        "type": "string",
                        "description": "URI del tipo de evento en Calendly (obtenido de list_calendly_events)"
                    },
                    "invitee_email": {
                        "type": "string",
                        "description": "Email del invitado"
                    },
                    "invitee_name": {
                        "type": "string",
                        "description": "Nombre del invitado (opcional)"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Hora de inicio en formato ISO 8601 (opcional)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Hora de fin en formato ISO 8601 (opcional)"
                    }
                },
                "required": ["event_type_uri", "invitee_email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendly_events",
            "description": (
                "Lista eventos próximos desde Calendly usando el token OAuth almacenado. "
                "Devuelve eventos agendados y tipos de eventos disponibles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Días hacia adelante a consultar (default: 30)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados (default: 20)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ingest_calendly_events",
            "description": (
                "Ingesta eventos de Calendly a extracted_events en Supabase (source=calendly). "
                "Sincroniza eventos de Calendly con la base de datos local."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de eventos a ingerir (default: 20)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": (
                "Envía un mensaje de WhatsApp a un número de teléfono vía Twilio. "
                "Requiere: to (número con código país, ej: +1234567890), message (texto del mensaje)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Número de teléfono con código país (ej: +1234567890)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Texto del mensaje a enviar"
                    }
                },
                "required": ["to", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_news_for_events",
            "description": (
                "Scrapea sitios de noticias y busca menciones de eventos/conferencias. "
                "Extrae información de eventos mencionados en artículos de noticias. "
                "Útil para descubrir eventos relevantes para el usuario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sites": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de URLs de sitios de noticias (opcional, usa defaults si no se proporciona)"
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords adicionales para buscar eventos (opcional)"
                    },
                    "max_articles": {
                        "type": "integer",
                        "description": "Máximo de artículos a procesar por sitio (default: 10)"
                    }
                },
                "required": []
            }
        }
    }
]


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get all available tool definitions for the LLM.
    
    Returns:
        List of tool definitions in OpenAI function-calling format.
    """
    return TOOL_DEFINITIONS


def get_tool_names() -> List[str]:
    """
    Get list of all available tool names.
    
    Returns:
        List of tool name strings.
    """
    return [t["function"]["name"] for t in TOOL_DEFINITIONS]

