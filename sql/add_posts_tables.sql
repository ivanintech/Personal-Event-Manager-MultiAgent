-- =============================================================================
-- Añadir Tablas para Proyecto Final (Posts y Curation State)
-- =============================================================================
-- Este script AÑADE las tablas necesarias sin modificar las existentes
-- Ejecutar en Supabase SQL Editor
-- 
-- IMPORTANTE: Este script es idempotente (puede ejecutarse múltiples veces)
-- =============================================================================

-- =============================================================================
-- Tabla posts: Almacena posts generados por el agente
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.posts (
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
CREATE INDEX IF NOT EXISTS idx_posts_status ON public.posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON public.posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_release_date ON public.posts(release_date DESC);
CREATE INDEX IF NOT EXISTS idx_posts_source_url ON public.posts(source_url);

-- Función para actualizar updated_at automáticamente (si no existe)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para actualizar updated_at
DROP TRIGGER IF EXISTS update_posts_updated_at ON public.posts;
CREATE TRIGGER update_posts_updated_at
    BEFORE UPDATE ON public.posts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS (Row Level Security)
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;

-- Política para service role (backend)
DROP POLICY IF EXISTS "sr full posts" ON public.posts;
CREATE POLICY "sr full posts" ON public.posts
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Política para lectura anónima (frontend)
DROP POLICY IF EXISTS "anon read posts" ON public.posts;
CREATE POLICY "anon read posts" ON public.posts
  FOR SELECT USING (true);

-- Política para inserción anónima (si es necesario)
DROP POLICY IF EXISTS "anon insert posts" ON public.posts;
CREATE POLICY "anon insert posts" ON public.posts
  FOR INSERT WITH CHECK (true);

-- =============================================================================
-- Tabla curation_state: Persistencia del estado de curación
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.curation_state (
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

CREATE INDEX IF NOT EXISTS idx_curation_state_source ON public.curation_state(source);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS update_curation_state_updated_at ON public.curation_state;
CREATE TRIGGER update_curation_state_updated_at
    BEFORE UPDATE ON public.curation_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS
ALTER TABLE public.curation_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sr full curation_state" ON public.curation_state;
CREATE POLICY "sr full curation_state" ON public.curation_state
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "anon read curation_state" ON public.curation_state;
CREATE POLICY "anon read curation_state" ON public.curation_state
  FOR SELECT USING (true);

-- =============================================================================
-- Vistas útiles para frontend
-- =============================================================================

-- Vista para posts pendientes
CREATE OR REPLACE VIEW public.posts_pending AS
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
FROM public.posts
WHERE status = 'pending'
ORDER BY created_at DESC;

-- Vista para posts publicados
CREATE OR REPLACE VIEW public.posts_published AS
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
FROM public.posts
WHERE status = 'published'
ORDER BY release_date DESC, created_at DESC;

-- =============================================================================
-- Verificación
-- =============================================================================

-- Verificar que las tablas se crearon correctamente
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'posts') THEN
        RAISE NOTICE '✅ Tabla posts creada exitosamente';
    ELSE
        RAISE EXCEPTION '❌ Error: Tabla posts no se creó';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'curation_state') THEN
        RAISE NOTICE '✅ Tabla curation_state creada exitosamente';
    ELSE
        RAISE EXCEPTION '❌ Error: Tabla curation_state no se creó';
    END IF;
END $$;

-- Mostrar resumen
SELECT 
    '✅ Tablas añadidas exitosamente!' as result,
    (SELECT COUNT(*) FROM public.posts) as posts_count,
    (SELECT COUNT(*) FROM public.curation_state) as curation_states_count;




