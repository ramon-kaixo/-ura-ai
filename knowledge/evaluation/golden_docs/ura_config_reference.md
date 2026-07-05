# URA Configuration Reference

The `UraConfig` class in `motor/core/config.py` is the single source of truth for configuration.

## Key Fields

- `deploy_dir`: Deployment directory (default: deploy/)
- `data_dir`: Data directory for runtime files (default: motor/data/)
- `log_level`: Logging level (default: INFO)
- `qdrant_host`: Qdrant host (default: localhost)
- `qdrant_port`: Qdrant port (default: 6333)
- `knowledge_db`: Path to knowledge SQLite database

## Configuration Loading

Configuration is loaded from a JSON file specified via --config flag.
Default config lives in deploy/system_config.json.

## Environment Variables

- `URA_STATE_DIR`: Override state directory
- `URA_LOGS_DIR`: Override logs directory
- `URA_DATA_DIR`: Override data directory
- `MOCHILA_COST_FILE`: Cost tracker file path
- `MOCHILA_HEALTH_FILE`: Provider health file path
