-- Tabla de Posts para Proyecto Final
-- Ejecutar en Supabase SQL Editor

-- =============================================================================
-- Tabla posts: Almacena posts generados por el agente
-- =============================================================================

CREATE TABLE IF NOT EXISTS posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_url TEXT NOT NULL,
  image_url TEXT,
  release_date DATE NOT NULL DEFAULT CURRENT_DATE,
  provider TEXT,
  type TEXT,
  status TEXT DEFAULT 'pending', -- pending | approved | rejected | published
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by TEXT DEFAULT 'agent', -- agent | user
  approval_notes TEXT -- Notas del usuario al aprobar/rechazar
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_release_date ON posts(release_date DESC);
CREATE INDEX IF NOT EXISTS idx_posts_source_url ON posts(source_url);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para actualizar updated_at
DROP TRIGGER IF EXISTS update_posts_updated_at ON posts;
CREATE TRIGGER update_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS (Row Level Security)
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

-- Política para service role (backend)
CREATE POLICY "sr full posts" ON posts
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Política para lectura anónima (frontend)
CREATE POLICY "anon read posts" ON posts
  FOR SELECT USING (true);

-- Política para inserción anónima (si es necesario)
CREATE POLICY "anon insert posts" ON posts
  FOR INSERT WITH CHECK (true);

-- =============================================================================
-- Tabla curation_state: Persistencia del estado de curación
-- =============================================================================

CREATE TABLE IF NOT EXISTS curation_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL, -- telegram | whatsapp
  last_processed_message_id TEXT,
  last_execution_time TIMESTAMPTZ,
  error_log TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source)
);

CREATE INDEX IF NOT EXISTS idx_curation_state_source ON curation_state(source);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS update_curation_state_updated_at ON curation_state;
CREATE TRIGGER update_curation_state_updated_at
    BEFORE UPDATE ON curation_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS
ALTER TABLE curation_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sr full curation_state" ON curation_state
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "anon read curation_state" ON curation_state
  FOR SELECT USING (true);

-- =============================================================================
-- Vista para posts pendientes (útil para frontend)
-- =============================================================================

CREATE OR REPLACE VIEW posts_pending AS
SELECT 
  id,
  title,
  summary,
  source_url,
  image_url,
  release_date,
  provider,
  type,
  created_at
FROM posts
WHERE status = 'pending'
ORDER BY created_at DESC;

-- =============================================================================
-- Vista para posts publicados (útil para frontend)
-- =============================================================================

CREATE OR REPLACE VIEW posts_published AS
SELECT 
  id,
  title,
  summary,
  source_url,
  image_url,
  release_date,
  provider,
  type,
  created_at
FROM posts
WHERE status = 'published'
ORDER BY release_date DESC, created_at DESC;

-- =============================================================================
-- SUCCESS
-- =============================================================================

SELECT '✅ Tabla posts creada exitosamente!' as result;




