"""Audit — trazabilidad lock-free del Knowledge Engine.

Paquete:
  backend.py           AuditHealth, AuditBackend(Protocol)
  ndjson_backend.py    NDJSONAuditBackend (append-only, lock-free)
  sqlite_backend.py    SQLiteAuditBackend (batch ingest)
  service.py           AuditService + singleton global
"""

from knowledge.engine.audit.backend import AuditBackend as AuditBackend
from knowledge.engine.audit.backend import AuditHealth as AuditHealth
from knowledge.engine.audit.ndjson_backend import NDJSONAuditBackend as NDJSONAuditBackend
from knowledge.engine.audit.service import AuditService as AuditService
from knowledge.engine.audit.service import get_audit as get_audit
from knowledge.engine.audit.service import set_audit as set_audit
from knowledge.engine.audit.sqlite_backend import SQLiteAuditBackend as SQLiteAuditBackend
