# Tests Skipped — Justificación

| # | Test | Archivo | Razón | Ticket / Nota |
|---|------|---------|-------|---------------|
| 1 | test_unregister_removes_subscription | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 2 | test_register_creates_subscription | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 3 | test_hook_is_called | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 4 | test_hook_called_via_event_payload | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 5 | test_failing_hook_does_not_break_other_hooks | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 6 | test_hook_recovers_after_successful_call | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 7 | test_degraded_mode_after_hook_failure | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 8 | test_after_max_errors_hook_is_unsubscribed | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 9 | test_canceling_hook_returns_none | test_hook_manager.py | hook_manager no disponible en entorno de test | Requiere refactor de hook_manager |
| 10 | test_timeout_not_applicable | test_tuneladora_pipeline_negative.py | timeout no aplica a pipeline de imports | Documentado en test |
| 11 | test_simulated_network_failure_opens_runbook | test_openclaw.py | requiere red simulada no disponible en CI | Skip condicional por entorno |
| 12 | test_streaming | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 13 | test_list_conversations | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 14 | test_invalid_mode | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 15 | test_health | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 16 | test_chat_with_user_id | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 17 | test_chat_with_mode | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 18 | test_chat_greeting | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 19 | test_auth_required_when_configured | test_integration_assistant.py | requiere servidor assistant levantado | Skip en CI sin servidor |
| 20 | test_quality_computed | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 21 | test_multipage | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 22 | test_metadata_fields | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 23 | test_extract_basic | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 24 | test_determinism | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 25 | test_asset_id_is_content_hash | test_extractors.py::TestPdfExtractor | requiere pdfplumber/poppler no instalado | Instalar dependencias para activar |
| 26 | test_quality_computed | test_extractors.py::TestOfficeExtractor | requiere libreoffice/python-docx no instalado | Instalar dependencias para activar |
| 27 | test_metadata_fields_docx | test_extractors.py::TestOfficeExtractor | requiere libreoffice/python-docx no instalado | Instalar dependencias para activar |
| 28 | test_extract_pptx | test_extractors.py::TestOfficeExtractor | requiere libreoffice/python-pptx no instalado | Instalar dependencias para activar |
| 29 | test_extract_docx | test_extractors.py::TestOfficeExtractor | requiere libreoffice/python-docx no instalado | Instalar dependencias para activar |
| 30 | test_determinism | test_extractors.py::TestOfficeExtractor | requiere libreoffice/python-docx no instalado | Instalar dependencias para activar |
| 31 | test_thumbnail_created | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 32 | test_quality_computed | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 33 | test_metadata_fields | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 34 | test_extract_png | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 35 | test_extract_jpeg | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 36 | test_determinism | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 37 | test_asset_id_is_content_hash | test_extractors.py::TestImageExtractor | requiere Pillow no instalado | Instalar dependencias para activar |
| 38 | test_approval_metrics | test_api_approvals.py | requiere servidor API levantado | Skip en CI sin servidor |
| 39 | test_approval_health | test_api_approvals.py | requiere servidor API levantado | Skip en CI sin servidor |
| 40 | test_approval_chat_completions | test_api_approvals.py | requiere servidor API levantado | Skip en CI sin servidor |

**Total: 40 skipped. Todas justificadas.**

## Tests Flaky (no skipped, pero fallan intermitentemente)

| # | Test | Archivo | Razón | Acción | Estado |
|---|------|---------|-------|--------|--------|
| 41 | test_100_exitos | test_model_router_selection.py | Estado compartido entre tests (SuccessRates contaminado por otro test) | OpenCode: investigar test contaminador y aislar estado | Pendiente |

**Nota:** Este test pasa cuando se ejecuta solo (`pytest test_model_router_selection.py::TestSuccessRates::test_100_exitos`) pero falla cuando se ejecuta la suite completa. Indica contaminación de estado global entre archivos de test.
