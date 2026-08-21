#!/usr/bin/env python3
"""mutmut_daily — Barrido diario progresivo de mutation testing (PLAN v5).

Ejecutado por systemd timer a las 06:00. Selecciona el lote del día por
rotación semanal, ejecuta mutmut sobre ese lote con HYPOTHESIS_PROFILE=ci,
genera un reporte markdown en docs/udo/mutation-reports/ y crea una TASK
UDO para que OpenCode Terminal la revise.

Sin fricción: no toca hooks de git, no muta en el working tree (mutmut usa
una copia de trabajo propia en .mutmut-cache/). El fallo del lote se
registra (exit code) y la TASK queda BLOCKED.

Uso: scripts/pro/mutmut_daily.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from datetime import UTC
from pathlib import Path

REPO = Path("/home/ramon/URA/ura_ia_1972")
VENV_BIN = REPO / ".venv" / "bin"
MUTMUT = VENV_BIN / "mutmut"
REPORT_DIR = REPO / "docs" / "udo" / "mutation-reports"

# Lotes equilibrados por tamaño de código (motor/core: 105, motor/intelligence: 36,
# core: 125, knowledge: 88 — en realidad motor/core tiene ~105 y core ~125, se reparte
# para que cada día dure < 1-2h con mutmut).
BATCHES: list[list[str]] = [
    ["motor/core/"],
    ["core/"],
    ["knowledge/", "motor/intelligence/"],
    ["motor/assistant/", "motor/observability/", "motor/scanner/"],
    ["motor/agents/", "motor/brain/", "motor/memory/", "motor/events/", "motor/cli/"],
]

# mutmut 3.7 solo muta source_paths del pyproject (no acepta paths por CLI);
# BATCHES queda como documentación del equilibrio original. El barrido actual
# cubre todo source_paths y el cache hace el trabajo incremental.

# Tests que dependen de archivos del árbol completo (config/, scripts/pro,
# README, .github/, benchmarks de timing) y rompen la colección dentro de
# mutants/ (mutmut solo copia source_paths + tests).
TEST_IGNORES: list[str] = [
    "tests/contracts/test_llm_contract.py",
    "tests/infra/test_ci_cd.py",
    "tests/infra/test_documentation.py",
    "tests/infra/test_f25_b7_hardening.py",
    "tests/infra/test_infrastructure.py",
    "tests/infra/test_preflight_system.py",
    "tests/integration/test_api.py",
    "tests/integration/test_auditoria_paralela.py",
    "tests/integration/test_f26_b2_memory.py",
    "tests/integration/test_git_hooks.py",
    "tests/integration/test_manage_timers.py",
    "tests/integration/test_tuneladora_cleanup_integration.py",
    "tests/integration/test_tuneladora_pipeline_negative.py",
    "tests/integration/test_vram_guard_integration.py",
    "tests/legacy/test_unit.py",
    "tests/nightly/test_f26_b3_hardening.py",
    "tests/nightly/test_f26_rr1_operational.py",
    "tests/nightly/test_knowledge_engine.py",
    "tests/pending/test_audit_conversation.py",
    "tests/unit/test_agents_ejecutor.py",
    "tests/unit/test_config.py",
    "tests/unit/test_core_voice_main_inferencia.py",
    "tests/unit/test_f25_b4_fact_index.py",
    "tests/unit/test_health_check.py",
    "tests/unit/test_model_router_cache.py",
    "tests/unit/test_model_router_cli.py",
    "tests/unit/test_model_router_metrics.py",
    "tests/unit/test_model_router_proxy.py",
    "tests/unit/test_model_router_router.py",
    "tests/unit/test_model_router_handler.py",
    "tests/unit/test_model_router_selection.py",
    "tests/unit/test_router_dashboard.py",
    "tests/unit/test_router_handler.py",
    "tests/unit/test_search_engine.py",
    "tests/unit/test_ura_query.py",
    "tests/unit/test_vram_guard.py",
    "tests/unit/test_motor_cmd_ura.py",
    "tests/unit/test_scripts_check_secrets.py",
    "tests/unit/test_reglas_loader.py",
    "tests/unit/test_quality_gate.py",
    "tests/unit/test_orchestrator.py",
    "tests/unit/test_master_conciencia.py",
    "tests/unit/test_lock_manager.py",
    "tests/unit/test_cleanup_assistant.py",
    "tests/unit/test_chaos_test.py",
    "tests/unit/test_backup_f26_memory.py",
    "tests/unit/test_backup_assistant.py",
    "tests/unit/test_auditoria_continua.py",
    "tests/unit/test_verificador_tests.py",
    "tests/unit/test_audit_secrets.py",
    "tests/unit/test_motor_llm_obs_state.py",
    "tests/unit/test_llm_providers.py",
    "tests/unit/test_mochila_provider_ollama.py",
    "tests/unit/test_mochila_providers_openrouter_gemini.py",
    "tests/unit/test_mochila_providers_clonados.py",
    "tests/unit/test_refactor_large_functions_v2.py",
    "tests/unit/test_motor_health_monitor.py",
    "tests/unit/test_guardian_opencode.py",
    "tests/unit/test_knowledge_snapshot_store.py",
    "tests/property/",
    "tests/nightly/test_platform_resilience.py",
    "tests/unit/test_moderation_sanitizer_hypothesis.py",
    "tests/unit/test_rules_hypothesis.py",
    "tests/unit/test_knowledge_metrics_cobertura.py",
    "tests/unit/test_config_manager_cobertura.py",
    "tests/unit/test_debate_engine_cobertura.py",
    "tests/unit/test_extraction_service_cobertura.py",
    "tests/unit/test_extractor_git_cobertura.py",
    "tests/unit/test_extractor_office_cobertura.py",
    "tests/unit/test_extractor_video_cobertura.py",
    "tests/unit/test_extractor_web_cobertura.py",
    "tests/unit/test_guardian_acciones_cobertura.py",
    "tests/unit/test_guardian_logger_cobertura.py",
    "tests/unit/test_ingestador_red_cobertura.py",
    "tests/unit/test_knowledge_agent_cobertura.py",
    "tests/unit/test_knowledge_api_cobertura.py",
    "tests/unit/test_knowledge_archiver_cobertura.py",
    "tests/unit/test_knowledge_asset_store_cobertura.py",
    "tests/unit/test_knowledge_audit_cobertura.py",
    "tests/unit/test_knowledge_base_cobertura.py",
    "tests/unit/test_knowledge_cli_agent_cobertura.py",
    "tests/unit/test_knowledge_cli_audit_cobertura.py",
    "tests/unit/test_knowledge_cli_cobertura.py",
    "tests/unit/test_knowledge_cli_main_cobertura.py",
    "tests/unit/test_knowledge_compiler_cobertura.py",
    "tests/unit/test_knowledge_connection_cobertura.py",
    "tests/unit/test_knowledge_deduction_cobertura.py",
    "tests/unit/test_knowledge_determinism_cobertura.py",
    "tests/unit/test_knowledge_errors_cobertura.py",
    "tests/unit/test_knowledge_eventbus_cobertura.py",
    "tests/unit/test_knowledge_extractors_base_cobertura.py",
    "tests/unit/test_knowledge_extractors_git_cobertura.py",
    "tests/unit/test_knowledge_extractors_markdown_cobertura.py",
    "tests/unit/test_knowledge_feedback_cobertura.py",
    "tests/unit/test_knowledge_governance_cobertura.py",
    "tests/unit/test_knowledge_graphrag_cobertura.py",
    "tests/unit/test_knowledge_jobs_cobertura.py",
    "tests/unit/test_knowledge_lineage_cobertura.py",
    "tests/unit/test_knowledge_lock_cobertura.py",
    "tests/unit/test_knowledge_memory_store_cobertura.py",
    "tests/unit/test_knowledge_migrations_cobertura.py",
    "tests/unit/test_knowledge_notify_cobertura.py",
    "tests/unit/test_knowledge_orchestrator_cobertura.py",
    "tests/unit/test_knowledge_pipeline_cobertura.py",
    "tests/unit/test_knowledge_qdrant_sync_cobertura.py",
    "tests/unit/test_knowledge_reader_cobertura.py",
    "tests/unit/test_knowledge_recommendation_cobertura.py",
    "tests/unit/test_knowledge_repository_cobertura.py",
    "tests/unit/test_knowledge_rules_cobertura.py",
    "tests/unit/test_knowledge_schema_org_cobertura.py",
    "tests/unit/test_knowledge_sqlite_writer_cobertura.py",
    "tests/unit/test_knowledge_subscribers_cobertura.py",
    "tests/unit/test_knowledge_validator_cobertura.py",
    "tests/unit/test_knowledge_vector_base_cobertura.py",
    "tests/unit/test_memoria_imagen_extractor_cobertura.py",
    "tests/unit/test_memory_engine_cobertura.py",
    "tests/unit/test_mochila_adapter_cobertura.py",
    "tests/unit/test_mochila_provider_ollama_cobertura.py",
    "tests/unit/test_mochila_proxy_cobertura.py",
    "tests/unit/test_mochila_server_cobertura.py",
    "tests/unit/test_mochila_tools_cobertura.py",
    "tests/unit/test_model_router_handler_cobertura.py",
    "tests/unit/test_model_router_proxy_cobertura.py",
    "tests/unit/test_motor_agents_agent_cobertura.py",
    "tests/unit/test_motor_config_cobertura.py",
    "tests/unit/test_motor_document_quality_cobertura.py",
    "tests/unit/test_motor_pipeline_executor_cobertura.py",
    "tests/unit/test_motor_pipeline_loader_cobertura.py",
    "tests/unit/test_motor_pipeline_orchestrator_cobertura.py",
    "tests/unit/test_reparador_cobertura.py",
    "tests/unit/test_resolver_red_cobertura.py",
    "tests/unit/test_web_base_cobertura.py",
    "tests/unit/test_web_citation_cobertura.py",
    "tests/unit/test_web_cleaner_cobertura.py",
    "tests/unit/test_web_duckduckgo_cobertura.py",
    "tests/unit/test_web_html_extractor_cobertura.py",
    "tests/unit/test_web_httpx_crawler_cobertura.py",
    "tests/unit/test_web_models_cobertura.py",
    "tests/unit/test_web_pipeline_cobertura.py",
    "tests/unit/test_web_ranker_cobertura.py",
    "tests/unit/test_web_registry_cobertura.py",
    "tests/unit/test_web_searxng_cobertura.py",
    "tests/unit/test_web_summarizer_cobertura.py",
    "tests/unit/test_knowledge_migration_v15.py",
    "tests/unit/test_knowledge_migrations_cobertura.py",
    "tests/unit/test_knowledge_migration_v15.py",
    "tests/integration/test_f27_b8_hardening.py",
    "tests/unit/test_agents_healing.py",
    "tests/unit/test_motor_tracing_exporter.py",
    "tests/property/test_property_ura.py",
    "tests/unit/test_guardian_middleware_path.py",
    "tests/integration/test_thread_safety.py",
    "tests/integration/test_degraded_mode.py",
    "tests/integration/test_extractors.py",
    "tests/unit/test_compactador_espacios.py",
    "tests/integration/test_audit_api.py",
    "tests/integration/test_api_approvals.py",
    "tests/integration/test_tuneladora_unified_scheduler.py",
    "tests/integration/test_tuneladora_sofia.py",
    "tests/integration/test_tuneladora_shadow_layer3.py",
    "tests/integration/test_tuneladora_shadow_layer0.py",
    "tests/integration/test_tuneladora_shadow_health.py",
    "tests/integration/test_tuneladora_scheduler.py",
    "tests/integration/test_tuneladora_preflight_system.py",
    "tests/integration/test_tuneladora_plugins.py",
    "tests/integration/test_tuneladora_pipeline_snapshot.py",
    "tests/integration/test_tuneladora_pipeline_runner.py",
    "tests/integration/test_tuneladora_pipeline_cli.py",
    "tests/integration/test_tuneladora_notifier.py",
    "tests/integration/test_tuneladora_memory_short_term.py",
    "tests/integration/test_tuneladora_memory_semantic.py",
    "tests/integration/test_tuneladora_memory_long_term.py",
    "tests/integration/test_tuneladora_memory_episodic.py",
    "tests/integration/test_tuneladora_ledger.py",
    "tests/integration/test_tuneladora_engine.py",
    "tests/integration/test_tuneladora_detector.py",
    "tests/integration/test_tuneladora_dashboard_plugin.py",
    "tests/integration/test_tuneladora_daemon_install.py",
    "tests/integration/test_tuneladora_cleanup_plugin.py",
    "tests/integration/test_tuneladora_checkpoint.py",
    "tests/integration/test_tuneladora_auto_trigger.py",
    "tests/integration/test_orquestador.py",
    "tests/integration/test_extractors_cobertura.py",
    "tests/unit/test_voice_modules.py",
]


def _lote_del_dia() -> tuple[int, list[str]]:
    """Índice por día de la semana (0=lunes..6=domingo) → lote rotativo."""
    idx = datetime.datetime.now(UTC).date().weekday() % len(BATCHES)
    return idx, BATCHES[idx]


def _ejecutar_mutmut(lote: list[str], dry: bool) -> int:
    # mutmut 3.7: los args posicionales de "run" son filtros de NOMBRES de
    # mutante ("motor.core.config.x_foo__mutmut_1"), NO paths. Un path como
    # motor/core/ nunca matchea -> AssertionError "Filtered for specific
    # mutants, but nothing matches". El camino soportado: sin args (muta
    # source_paths del pyproject) y el cache incremental reutiliza los
    # mutantes ya ejecutados (barrido progresivo real).
    cmd = [str(MUTMUT), "run"]
    if dry:
        print("[dry-run] mutmut:", " ".join(cmd))
        return 0
    env = dict(os.environ)
    env["HYPOTHESIS_PROFILE"] = "ci"
    # Los tests insertan sys.path relativo a scripts/pro (no existe en el
    # árbol mutado de mutmut); sin PYTHONPATH la colección falla y el lote
    # muere con "failed to collect stats" (exit 1).
    env.setdefault("PYTHONPATH", str(REPO / "scripts" / "pro"))
    # Tests que dependen del árbol completo (config/, scripts/pro, README,
    # .github/, benchmarks de timing) y rompen la colección dentro de
    # mutants/ porque mutmut solo copia source_paths + tests. Excluirlos del
    # baseline mutmut (se siguen ejecutando en la suite pytest normal).
    env.setdefault(
        "PYTEST_ADDOPTS",
        " ".join(f"--ignore={t}" for t in TEST_IGNORES),
    )
    print("Ejecutando:", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(REPO), env=env, check=False).returncode


def _reporte_mutmut() -> str:
    res = subprocess.run([str(MUTMUT), "results"], capture_output=True, text=True, cwd=str(REPO), check=False)
    return res.stdout if res.returncode == 0 else f"(mutmut results falló: {res.stderr})"


def _crear_task_udo(reporte_path: Path, lote: list[str], exit_code: int, dry: bool) -> str:
    """Crea una TASK UDO con el resumen del lote para que TERM la revise."""
    estado = "BLOCKED" if exit_code != 0 else "PLANNED"
    desc = f"Revisar reporte mutmut {lote[0] if len(lote) == 1 else 'lote combinado'} ({reporte_path.name})"
    if dry:
        print(f"[dry-run] ura-udo create: {desc} | estado={estado}")
        return "TASK-dry-run"
    cmd = [str(REPO / "scripts" / "pro" / "ura-udo"), "create", desc]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), check=False).stdout
    task_id = next((tok for tok in out.split() if tok.startswith("TASK-")), "TASK-?")
    # Registra el estado inicial (BLOCKED si el lote falló) con nota del reporte
    subprocess.run(
        [
            str(REPO / "scripts" / "pro" / "ura-udo"),
            "update",
            task_id,
            "--estado",
            estado,
            "--nota",
            f"Reporte mutmut: {reporte_path.name} (exit={exit_code})",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        check=False,
    )
    return task_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    idx, lote = _lote_del_dia()
    date_str = datetime.datetime.now(UTC).date().isoformat()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lote_name = "+".join(p.rstrip("/").replace("/", "_") for p in lote)
    reporte_path = REPORT_DIR / f"{date_str}_{lote_name}.md"

    # Lote ya cubierto hoy (idempotente): no re-ejecutar
    if reporte_path.exists() and not args.dry_run:
        print(f"Lote ya ejecutado hoy: {reporte_path.name}")
        return 0

    print(f"== Barrido mutmut {date_str} — lote {idx}: {', '.join(lote)}")
    exit_code = _ejecutar_mutmut(lote, args.dry_run)

    reporte = _reporte_mutmut() if not args.dry_run else "(reporte en dry-run)"
    reporte_path.write_text(
        f"# Reporte mutmut {date_str} — {lote_name}\n\n"
        f"**Lote**: {', '.join(lote)} · **Exit code**: {exit_code}\n\n"
        f"```\n{reporte}\n```\n"
    )
    print(f"Reporte: {reporte_path}")

    task = _crear_task_udo(reporte_path, lote, exit_code, args.dry_run)
    print(f"TASK UDO: {task}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
