#!/bin/bash
source /Users/ramonesnaola/URA/ura_ia_1972/.venv/bin/activate
python3 << 'PYEOF'
import asyncio, pathlib
from core.training_orchestrator import TrainingOrchestrator
from core.seed_pipeline import SeedPipeline
from core.query_decomposer import QueryDecomposer

async def main():
    # Test mode: use local seeds instead of Toshiba
    semillas_path = pathlib.Path("/Users/ramonesnaola/URA/ura_ia_1972/test_seeds.txt")

    if not semillas_path.exists():
        print("ERROR: No se encontraron archivos de semillas")
        return 1

    with open(semillas_path) as f:
        semillas = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    print(f"Cargadas {len(semillas)} semillas")

    decomposer = QueryDecomposer()
    todas = []
    for s in semillas:
        if decomposer.is_complex(s):
            subs = await decomposer.decompose(s, n=10)
            todas.extend(subs)
        else:
            todas.append(s)

    print(f"Expandidas a {len(todas)} queries")

    orchestrator = TrainingOrchestrator(max_queries=5, concurrency=2)
    orchestrator.responses_dir = pathlib.Path("/Users/ramonesnaola/URA/ura_ia_1972/test_responses")
    orchestrator.responses_dir.mkdir(parents=True, exist_ok=True)
    orchestrator.reports_dir = pathlib.Path("/Users/ramonesnaola/URA/ura_ia_1972/test_reports")
    orchestrator.reports_dir.mkdir(parents=True, exist_ok=True)

    print("Iniciando ataque nocturno con N3Orchestrator (Ollama + OpenClaw)...")
    await orchestrator.night_training(max_queries=5)
    print("Ataque nocturno completado.")

asyncio.run(main())
PYEOF
