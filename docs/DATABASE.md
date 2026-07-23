# URA Database Schema

## Overview
URA uses 5 SQLite databases: 1 persistent (knowledge) and 4 runtime (memory, feedback, notes, preferences).

## Databases

### knowledge.db
- Location: knowledge/knowledge.db
- Purpose: Persistent document storage for Knowledge Engine
- Schema: docs/sql/knowledge_db_schema.sql
- Tables:
- kg_nodes
- kg_edges
- kg_nodes_fts
- kg_nodes_fts_data
- kg_nodes_fts_idx
- kg_nodes_fts_content
- kg_nodes_fts_docsize
- kg_nodes_fts_config
- kg_ontology_nodes
- kg_ontology_edges
- kg_active_version
- op_events
- sqlite_sequence
- op_audit
- op_jobs
- op_scheduler
- op_compiler_runs

### memory.db
- Location: ~/.ura/memory.db
- Purpose: Health monitoring state
- Created by: motor/health_monitor.py
- Tables: (created dynamically)

### feedback.db
- Location: config.db_for("feedback")
- Purpose: User feedback storage
- Created by: motor/assistant/implicit_feedback.py

### notes.db
- Location: config.db_for("notes")
- Purpose: User notes storage
- Created by: motor/assistant/executor.py

### preferences.db
- Location: config.db_for("preferences")
- Purpose: User preferences
- Created by: motor/assistant/preferences.py

## Module-Database Mapping
| Module | Database | Purpose |
|--------|----------|---------|
| knowledge/engine/ | knowledge.db | Documents, embeddings, FTS5 |
| motor/assistant/ | memory.db | Conversation state |
| motor/assistant/ | feedback.db | User ratings |
| motor/assistant/ | notes.db | User notes |
| motor/assistant/ | preferences.db | User preferences |
