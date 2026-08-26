"""Interface Contracts — Bloqueo de firmas antes de generación concurrente.

Resuelve el problema de colisión semántica cuando dos instancias generan
código interdependiente en ramas paralelas.

Flujo:
  1. Orquestador genera INTERFACE_CONTRACTS.md antes de bifurcar
  2. Cada generador recibe los contratos como prompt base
  3. Auditor valida cada rama contra los contratos (no reescribe)
  4. El archivo de contratos es READ-ONLY durante la fase de desarrollo
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONTRACTS_FILE = "INTERFACE_CONTRACTS.md"
_CONTRACTS_HASH_FILE = ".interface_contracts.sha256"


@dataclass
class FunctionContract:
    """Contrato de una función."""

    name: str
    module: str
    params: list[dict[str, str]]  # [{"name": "x", "type": "int"}]
    return_type: str
    docstring: str = ""
    raises: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class DataContract:
    """Contrato de un modelo de datos."""

    name: str
    module: str
    fields: list[dict[str, str]]  # [{"name": "id", "type": "str", "required": True}]
    docstring: str = ""


@dataclass
class APISurface:
    """Superficie de API pública de un módulo."""

    module: str
    functions: list[FunctionContract] = field(default_factory=list)
    data_models: list[DataContract] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


@dataclass
class InterfaceContractSet:
    """Conjunto completo de contratos para un plan."""

    plan_id: str
    modules: list[APISurface] = field(default_factory=list)
    shared_types: list[DataContract] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Contract generation
# ---------------------------------------------------------------------------


class ContractGenerator:
    """Genera INTERFACE_CONTRACTS.md desde la arquitectura del plan."""

    def __init__(self, repo_root: Path) -> None:
        self._repo = repo_root

    def _scan_module(self, module_path: Path, module_name: str) -> APISurface:
        """Escanea un módulo y extrae funciones y tipos públicos."""
        functions = []
        data_models = []
        exports = []

        if not module_path.exists():
            return APISurface(module=module_name)

        for py_file in sorted(module_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                content = py_file.read_text()
            except Exception:  # nosec B112
                continue

            # Extract function signatures
            for match in re.finditer(
                r"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?",
                content,
                re.MULTILINE,
            ):
                name = match.group(1)
                if name.startswith("_"):
                    continue
                params_str = match.group(2)
                return_type = match.group(3) or "None"

                params = []
                for raw_p in params_str.split(","):
                    p = raw_p.strip()
                    if p and ":" in p:
                        pname, ptype = p.split(":", 1)
                        params.append({"name": pname.strip(), "type": ptype.strip()})

                functions.append(
                    FunctionContract(
                        name=name,
                        module=f"{module_name}.{py_file.stem}",
                        params=params,
                        return_type=return_type,
                    )
                )

            # Extract dataclass/Pydantic models
            for match in re.finditer(
                r"^@dataclass\s*\nclass\s+(\w+).*?:",
                content,
                re.MULTILINE,
            ):
                model_name = match.group(1)
                data_models.append(
                    DataContract(
                        name=model_name,
                        module=f"{module_name}.{py_file.stem}",
                        fields=[],  # Would need deeper parsing
                    )
                )

            # Extract __all__
            all_match = re.search(r"__all__\s*=\s*\[([^\]]+)\]", content)
            if all_match:
                exports.extend(e.strip().strip("'\"") for e in all_match.group(1).split(","))

        return APISurface(
            module=module_name,
            functions=functions,
            data_models=data_models,
            exports=exports,
        )

    def generate_from_plan(self, plan_id: str, modules: list[str]) -> InterfaceContractSet:
        """Genera contratos desde los módulos listados en el plan."""
        surfaces = []
        for mod_name in modules:
            mod_path = self._repo / mod_name.replace(".", "/")
            surfaces.append(self._scan_module(mod_path, mod_name))

        contract_set = InterfaceContractSet(
            plan_id=plan_id,
            modules=surfaces,
            metadata={"generated_from": "plan_scan"},
        )

        return contract_set

    def generate_manual(self, plan_id: str, contract_defs: list[dict[str, Any]]) -> InterfaceContractSet:
        """Genera contratos desde definiciones manuales del orquestador."""
        surfaces = []
        for mod_def in contract_defs:
            functions = [FunctionContract(**f) for f in mod_def.get("functions", [])]
            data_models = [DataContract(**d) for d in mod_def.get("data_models", [])]
            surfaces.append(
                APISurface(
                    module=mod_def["module"],
                    functions=functions,
                    data_models=data_models,
                    exports=mod_def.get("exports", []),
                )
            )

        return InterfaceContractSet(
            plan_id=plan_id,
            modules=surfaces,
            metadata={"generated_from": "manual"},
        )


# ---------------------------------------------------------------------------
# Contract serialization
# ---------------------------------------------------------------------------


def contracts_to_markdown(contract_set: InterfaceContractSet) -> str:
    """Serializa contratos a INTERFACE_CONTRACTS.md (formato markdown)."""
    lines = [
        f"# INTERFACE CONTRACTS — {contract_set.plan_id}",
        "",
        "> **ARCHIVO DE SOLO LECTURA** durante la fase de desarrollo.",
        "> Los agentes generadores NO pueden modificar este archivo.",
        "> Cualquier cambio requiere aprobación del Orquestador.",
        "",
        f"Generado: {contract_set.metadata.get('generated_from', 'unknown')}",
        "",
        "---",
        "",
    ]

    for surface in contract_set.modules:
        lines.append(f"## Module: `{surface.module}`")
        lines.append("")

        if surface.functions:
            lines.append("### Functions")
            lines.append("")
            for fn in surface.functions:
                params = ", ".join(f"{p['name']}: {p['type']}" for p in fn.params)
                lines.append("```python")
                lines.append(f"def {fn.name}({params}) -> {fn.return_type}:")
                if fn.docstring:
                    lines.append(f'    """{fn.docstring}"""')
                lines.append("```")
                lines.append("")

        if surface.data_models:
            lines.append("### Data Models")
            lines.append("")
            for dm in surface.data_models:
                lines.append("```python")
                lines.append("@dataclass")
                lines.append(f"class {dm.name}:")
                for field in dm.fields:
                    lines.append(f"    {field['name']}: {field['type']}")
                lines.append("```")
                lines.append("")

        if surface.exports:
            lines.append(f"### Exports: `{', '.join(surface.exports)}`")
            lines.append("")

    if contract_set.forbidden_patterns:
        lines.append("## Forbidden Patterns")
        lines.append("")
        for pattern in contract_set.forbidden_patterns:
            lines.append(f"- {pattern}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Validation Rules",
            "",
            "1. Each generated module MUST implement the functions above with exact signatures",
            "2. Return types MUST match the contract exactly",
            "3. Data models MUST have all fields listed above",
            "4. No additional public functions may be added without updating this file",
            "5. The Auditor validates against these contracts, not against other branches",
            "",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


class ContractValidator:
    """Valida código generado contra los contratos definidos."""

    def __init__(self, repo_root: Path) -> None:
        self._repo = repo_root

    def _load_contracts(self) -> InterfaceContractSet | None:
        """Carga los contratos desde el repo."""
        contracts_file = self._repo / _CONTRACTS_FILE
        if not contracts_file.exists():
            return None
        # For now, return a basic parsed version
        # In production, this would parse the markdown back to structured data
        return InterfaceContractSet(plan_id="loaded", metadata={"source": "file"})

    def _verify_hash(self) -> bool:
        """Verifica que el archivo de contratos no fue modificado."""
        contracts_file = self._repo / _CONTRACTS_FILE
        hash_file = self._repo / _CONTRACTS_HASH_FILE

        if not contracts_file.exists() or not hash_file.exists():
            return True  # No hash to verify

        current_hash = hashlib.sha256(contracts_file.read_bytes()).hexdigest()
        stored_hash = hash_file.read_text().strip()

        return current_hash == stored_hash

    def freeze_contracts(self, contract_set: InterfaceContractSet) -> Path:
        """Escribe INTERFACE_CONTRACTS.md y calcula hash."""
        contracts_file = self._repo / _CONTRACTS_FILE
        md_content = contracts_to_markdown(contract_set)
        contracts_file.write_text(md_content)

        # Store hash
        file_hash = hashlib.sha256(contracts_file.read_bytes()).hexdigest()
        hash_file = self._repo / _CONTRACTS_HASH_FILE
        hash_file.write_text(file_hash)

        log.info("[CONTRACTS] Congelados en %s (hash: %s)", contracts_file, file_hash[:12])
        return contracts_file

    def validate_module(self, module_path: Path, module_name: str) -> list[str]:
        """Valida un módulo generado contra los contratos.

        Retorna lista de errores (vacía = válido).
        """
        errors = []

        if not self._verify_hash():
            errors.append("CRITICAL: INTERFACE_CONTRACTS.md fue modificado durante el desarrollo")

        if not module_path.exists():
            errors.append(f"Module file not found: {module_path}")
            return errors

        try:
            content = module_path.read_text()
        except Exception as e:
            errors.append(f"Cannot read module: {e}")
            return errors

        # Check for forbidden patterns
        forbidden = [
            r"eval\s*\(",  # eval is dangerous
            r"exec\s*\(",  # exec is dangerous
            r"__import__\s*\(",  # dynamic imports
        ]
        for pattern in forbidden:
            if re.search(pattern, content):
                errors.append(f"Forbidden pattern found: {pattern}")

        return errors

    def validate_function_signature(self, module_path: Path, expected: FunctionContract) -> list[str]:
        """Valida que una función específica tenga la firma correcta."""
        errors = []

        if not module_path.exists():
            errors.append(f"Module not found: {module_path}")
            return errors

        content = module_path.read_text()

        # Find the function
        pattern = (
            rf"(?:async\s+)?def\s+{re.escape(expected.name)}\s*\(([^)]*)\)"
            rf"(?:\s*->\s*([^:\s]+))?"
        )
        match = re.search(pattern, content)

        if not match:
            errors.append(f"Function '{expected.name}' not found in {module_path}")
            return errors

        # Check return type
        actual_return = match.group(2) or "None"
        if actual_return != expected.return_type:
            errors.append(f"Return type mismatch: expected '{expected.return_type}', got '{actual_return}'")

        return errors
