-- Tabla para almacenar mensajes de WhatsApp
-- Permite procesar conversaciones completas con contexto

CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_sid TEXT UNIQUE NOT NULL,  -- SID único de Twilio
    conversation_id TEXT NOT NULL,     -- Agrupa mensajes por contacto (from_number)
    from_number TEXT NOT NULL,         -- Número del remitente
    to_number TEXT NOT NULL,           -- Número de destino (tu número)
    body TEXT NOT NULL,                -- Contenido del mensaje
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Estado de procesamiento
    processed BOOLEAN DEFAULT FALSE,           -- Si ya se procesó para eventos
    event_extracted BOOLEAN DEFAULT FALSE,    -- Si se extrajo evento de este mensaje
    event_id UUID REFERENCES extracted_events(id) ON DELETE SET NULL,  -- Evento relacionado
    
    -- Metadata
    num_media INTEGER DEFAULT 0,       -- Número de archivos adjuntos
    media_urls JSONB,                  -- URLs de archivos adjuntos (si hay)
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas eficientes
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_conversation 
    ON whatsapp_messages(conversation_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_processed 
    ON whatsapp_messages(processed, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_from_number 
    ON whatsapp_messages(from_number, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_event_extracted 
    ON whatsapp_messages(event_extracted, received_at DESC);

-- Tabla opcional para gestionar conversaciones
CREATE TABLE IF NOT EXISTS whatsapp_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT UNIQUE NOT NULL,  -- from_number (identificador único)
    contact_name TEXT,                     -- Nombre del contacto (si está disponible)
    contact_number TEXT NOT NULL,          -- Número del contacto
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,       -- Total de mensajes en la conversación
    event_count INTEGER DEFAULT 0,          -- Eventos extraídos de esta conversación
    last_processed_at TIMESTAMPTZ,          -- Última vez que se procesó para eventos
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_conversations_last_message 
    ON whatsapp_conversations(last_message_at DESC);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_whatsapp_messages_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_whatsapp_messages_updated_at
    BEFORE UPDATE ON whatsapp_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_whatsapp_messages_updated_at();

CREATE TRIGGER trigger_update_whatsapp_conversations_updated_at
    BEFORE UPDATE ON whatsapp_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_whatsapp_messages_updated_at();

-- Función para actualizar estadísticas de conversación
CREATE OR REPLACE FUNCTION update_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO whatsapp_conversations (conversation_id, contact_number, last_message_at, message_count)
    VALUES (NEW.conversation_id, NEW.from_number, NEW.received_at, 1)
    ON CONFLICT (conversation_id) 
    DO UPDATE SET
        last_message_at = NEW.received_at,
        message_count = whatsapp_conversations.message_count + 1,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_conversation_stats
    AFTER INSERT ON whatsapp_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_stats();


