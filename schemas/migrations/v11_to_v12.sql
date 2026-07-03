-- v11 → v12: Índices para queries frecuentes
--
-- Añade índices para mejorar rendimiento de queries frecuentes
-- identificadas durante la auditoría de rendimiento.

CREATE INDEX IF NOT EXISTS idx_op_jobs_status ON op_jobs(status, job_type);
CREATE INDEX IF NOT EXISTS idx_op_compile_errors_run ON op_compile_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_op_vector_sync_status ON op_vector_sync(status);
CREATE INDEX IF NOT EXISTS idx_op_archives_kind ON op_archives(kind);
