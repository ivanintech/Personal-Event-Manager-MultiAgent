# Pruebas del Protocolo MCP Estándar

## Servidor MCP de Prueba

Hemos creado un servidor MCP de prueba que implementa el protocolo estándar (JSON-RPC 2.0) para verificar que todo funciona correctamente.

### Archivos

- **Servidor**: `app/mcp/servers/test_mcp_server.py`
- **Script de prueba**: `scripts/test_mcp_protocol.py`

## Herramientas Disponibles

El servidor de prueba expone 3 herramientas:

1. **test_echo**: Hace echo de un mensaje
   - Parámetros: `message` (string), `repeat` (integer, opcional)

2. **test_add**: Suma dos números
   - Parámetros: `a` (number), `b` (number)

3. **test_get_time**: Obtiene la hora actual
   - Parámetros: ninguno

## Modos de Ejecución

### 1. Modo stdio (para Cursor/Claude Desktop)

```bash
# Ejecutar servidor
python app/mcp/servers/test_mcp_server.py

# O desde el directorio raíz
python -m app.mcp.servers.test_mcp_server
```

El servidor leerá peticiones JSON-RPC de stdin y escribirá respuestas a stdout.

### 2. Modo HTTP

```bash
# Ejecutar servidor HTTP en puerto 8001
python app/mcp/servers/test_mcp_server.py http 8001

# O usando uvicorn directamente
uvicorn app.mcp.servers.test_mcp_server:app --host 0.0.0.0 --port 8001
```

El servidor expondrá:
- `POST /` - Endpoint JSON-RPC
- `GET /health` - Health check

## Ejecutar Pruebas

### Prueba con Cliente stdio

```bash
python scripts/test_mcp_protocol.py --mode stdio
```

Esto:
1. Inicia el servidor MCP en modo stdio
2. Inicializa la conexión
3. Lista las herramientas disponibles
4. Ejecuta cada herramienta de prueba
5. Muestra los resultados

### Prueba con Cliente HTTP

Primero, inicia el servidor HTTP en otra terminal:

```bash
python app/mcp/servers/test_mcp_server.py http 8001
```

Luego ejecuta las pruebas:

```bash
python scripts/test_mcp_protocol.py --mode http
```

### Prueba Ambos Modos

```bash
python scripts/test_mcp_protocol.py --mode all
```

## Integración con tool_exec.py

El servidor de prueba está configurado en `mcp_servers.json`:

```json
{
  "mcpServers": {
    "test-server": {
      "command": "python",
      "args": ["./app/mcp/servers/test_mcp_server.py"],
      "env": {}
    },
    "test-server-http": {
      "transport": "http",
      "base_url": "http://localhost:8001",
      "env": {}
    }
  }
}
```

Puedes usarlo desde `tool_exec.py` añadiendo mappings en `mapping.json`:

```json
{
  "test_echo": "test-server.test_echo",
  "test_add": "test-server.test_add",
  "test_get_time": "test-server.test_get_time"
}
```

## Verificar Protocolo MCP

El servidor implementa correctamente:

✅ **JSON-RPC 2.0**
- Requests con `jsonrpc: "2.0"`, `id`, `method`, `params`
- Responses con `jsonrpc: "2.0"`, `id`, `result` o `error`
- Códigos de error estándar

✅ **Protocolo MCP**
- `initialize` - Handshake inicial
- `initialized` - Notificación después de initialize
- `tools/list` - Listar herramientas
- `tools/call` - Ejecutar herramientas

✅ **Transportes**
- stdio (newline-delimited JSON)
- HTTP (POST con JSON-RPC)

## Próximos Pasos

1. **Probar con servidor MCP oficial** (ej: GitHub MCP Server)
2. **Añadir más herramientas de prueba**
3. **Integrar con el agente** para usar herramientas MCP reales
4. **Añadir tests automatizados**

## Troubleshooting

### Error: "Server not initialized"
- Asegúrate de llamar `initialize()` antes de usar otras funciones

### Error: "Method not found"
- Verifica que el método esté implementado en el servidor
- Revisa que el nombre del método sea correcto

### Error: "Connection refused" (HTTP)
- Verifica que el servidor HTTP esté ejecutándose
- Comprueba que el puerto sea correcto (8001 por defecto)

### Error: "Process not found" (stdio)
- Verifica que Python esté en el PATH
- Comprueba que la ruta al script sea correcta

