"""
JSON-RPC 2.0 Protocol Implementation for MCP.

Based on JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
"""

import json
import uuid
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum


class JSONRPCErrorCode(int, Enum):
    """JSON-RPC 2.0 Error Codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Server error codes (-32000 to -32099) are reserved for implementation-defined errors
    SERVER_ERROR = -32000


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.params is not None:
            result["params"] = self.params
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params"),
        )


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 Response."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    _error: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def get_error(self) -> Optional[Dict[str, Any]]:
        """Get error field."""
        return self._error
    
    @property
    def error(self) -> Optional[Dict[str, Any]]:
        """Get error field (property)."""
        return self._error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            result["id"] = self.id
        
        # JSON-RPC 2.0: response debe tener "result" O "error", no ambos
        # Si hay error, incluir error; si no, incluir result (aunque sea None)
        if self._error is not None:
            result["error"] = self._make_json_serializable(self._error)
        else:
            # Si no hay error, siempre incluir result (puede ser None)
            serialized_result = self._make_json_serializable(self.result)
            result["result"] = serialized_result
        return result
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convierte un objeto a formato JSON serializable."""
        import types
        
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {str(k): self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (types.FunctionType, types.MethodType, types.BuiltinFunctionType, types.BuiltinMethodType)):
            # Ignorar métodos y funciones - no serializables
            return None
        elif isinstance(obj, type):
            # Ignorar clases
            return None
        elif hasattr(obj, '__dict__'):
            # Para objetos con __dict__, convertir a dict (pero evitar métodos)
            try:
                d = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith('_') and not isinstance(v, (types.FunctionType, types.MethodType)):
                        d[k] = self._make_json_serializable(v)
                return d
            except:
                return str(obj)
        else:
            # Fallback: convertir a string
            try:
                return str(obj)
            except:
                return None

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCResponse":
        """Create from dictionary."""
        # Si error es None/null, debe haber result (puede ser None)
        error = data.get("error")
        result = data.get("result")
        
        # Si error es explícitamente None en el dict, tratarlo como que no hay error
        if error is None and "error" in data:
            # El dict tiene "error": null, así que no hay error, usar result
            pass
        elif error is not None:
            # Hay error, result debe ser None
            result = None
        
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            result=result,
            _error=error if error is not None else None,
        )

    @classmethod
    def success(cls, request_id: Optional[Union[str, int]], result: Any) -> "JSONRPCResponse":
        """Create success response."""
        return cls(jsonrpc="2.0", id=request_id, result=result)

    @classmethod
    def create_error(
        cls,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> "JSONRPCResponse":
        """Create error response."""
        error_dict = {"code": code, "message": message}
        if data is not None:
            error_dict["data"] = data
        return cls(jsonrpc="2.0", id=request_id, _error=error_dict)
    
    @classmethod
    def create_error_response(
        cls,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> "JSONRPCResponse":
        """Create error response."""
        error_dict = {"code": code, "message": message}
        if data is not None:
            error_dict["data"] = data
        return cls(jsonrpc="2.0", id=request_id, _error=error_dict)
    
    @classmethod
    def error(
        cls,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> "JSONRPCResponse":
        """Create error response (alias for create_error_response for backward compatibility)."""
        return cls.create_error_response(request_id, code, message, data)
    
    @classmethod
    def error(
        cls,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> "JSONRPCResponse":
        """Create error response (alias for create_error_response for backward compatibility)."""
        return cls.create_error_response(request_id, code, message, data)


@dataclass
class JSONRPCNotification:
    """JSON-RPC 2.0 Notification (no response expected)."""
    jsonrpc: str = "2.0"
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.params is not None:
            result["params"] = self.params
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCNotification":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params"),
        )


def parse_jsonrpc_message(data: Union[str, Dict[str, Any]]) -> Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]:
    """
    Parse JSON-RPC 2.0 message from string or dict.
    
    Returns:
        JSONRPCRequest, JSONRPCResponse, or JSONRPCNotification
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("Message must be a dictionary")

    jsonrpc = data.get("jsonrpc")
    if jsonrpc != "2.0":
        raise ValueError(f"Invalid jsonrpc version: {jsonrpc}")

    # Check if it's a notification (no id field)
    if "id" not in data:
        return JSONRPCNotification.from_dict(data)

    # Check if it's a response (has result or error)
    if "result" in data or "error" in data:
        return JSONRPCResponse.from_dict(data)

    # Otherwise it's a request
    return JSONRPCRequest.from_dict(data)

