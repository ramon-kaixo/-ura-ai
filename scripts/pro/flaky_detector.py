#!/usr/bin/env python3
"""
Detector de tests flaky para CI.
Ejecuta tests con --reruns=3 y detecta los que fallan intermitentemente.
"""

import json
import re
import sys
from pathlib import Path


def main():
    results_file = Path("flaky_results.txt")
    if not results_file.exists():
        print("ERROR: flaky_results.txt no encontrado")
        return 1

    content = results_file.read_text()

    # Buscar tests que pasaron y fallaron en diferentes runs
    reruns = re.findall(r"(.+?) (PASSED|FAILED) \(rerun\)", content)

    flaky_tests = {}
    for raw_name, status in reruns:
        clean_name = raw_name.strip()
        if clean_name not in flaky_tests:
            flaky_tests[clean_name] = {"passed": 0, "failed": 0}
        if status == "PASSED":
            flaky_tests[clean_name]["passed"] += 1
        else:
            flaky_tests[clean_name]["failed"] += 1

    # Filtrar tests que tuvieron ambos resultados (flaky)
    truly_flaky = {k: v for k, v in flaky_tests.items() if v["passed"] > 0 and v["failed"] > 0}

    if truly_flaky:
        print("TESTS FLAKY DETECTADOS:")
        for test, stats in truly_flaky.items():
            print("  {}: passed={}, failed={}".format(test, stats["passed"], stats["failed"]))

        Path("flaky_report.json").write_text(json.dumps(truly_flaky, indent=2))
        return 1
    else:
        print("No tests flaky detectados")
        Path("flaky_report.json").write_text(json.dumps({}))
        return 0


if __name__ == "__main__":
    import json
    import re
    import sys

    sys.exit(main())
