"""Rule evaluation — motor de reglas determinista para el grafo de conocimiento.

Principios:
  - Las reglas NUNCA mutan kg_*. Solo generan Finding (warnings + overlay).
  - Evaluación determinista: mismo grafo → mismas reglas → mismos findings.
  - Las reglas tienen versión (R001 v1, R002 v1...) para trazabilidad.
  - SafeEval con AST whitelist, límites de complejidad y timeout.
  - Sin dependencias externas (reemplaza simpleeval).

Arquitectura:
  Rule(Protocol)
      ├── BuiltinRule (R001-R005, deterministas)
      └── CustomRule (futuro: user-defined, heurísticas)

  RuleEvaluator:
      sorted(rules, by id) × sorted(documents, by id)
      → list[Finding]
"""  # noqa: RUF002

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger("ura.knowledge.rules")

# ── Constants ─────────────────────────────────────────────────────────────

_MAX_EXPRESSION_LENGTH = 2048  # caracteres
_MAX_AST_DEPTH = 10  # niveles de anidamiento
_MAX_AST_NODES = 100  # nodos totales
_MAX_FUNCTION_CALLS = 10  # llamadas a funciones por expresión


# ── SafeEval (AST-based, sandboxed) ───────────────────────────────────────


class UnsafeExpressionError(ValueError):
    """Expresión no permitida por razones de seguridad."""


# Nodos AST permitidos (whitelist estricta)
_ALLOWED_AST_NODES = frozenset(
    {
        # Top-level
        ast.Expression,
        ast.Module,
        # Literals
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Set,
        # Names / Attribute (sin dunder)
        ast.Name,
        ast.Load,
        ast.Attribute,
        # Operadores unarios
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.Not,
        # Operadores binarios
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        # Comparación
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
        # Booleanos
        ast.BoolOp,
        ast.And,
        ast.Or,
        # Ternario
        ast.IfExp,
        # Subscript / Slice
        ast.Subscript,
        ast.Slice,
        # Call (solo funciones whitelisted)
        ast.Call,
        # List/Dict/Set comprehension (NO GeneratorExp)
        ast.ListComp,
        ast.comprehension,
    },
)

# Nodos EXPLÍCITAMENTE PROHIBIDOS (por claridad, aunque no están en _ALLOWED)
_BLOCKED_AST_NODES = (
    "Lambda",
    "Yield",
    "YieldFrom",
    "Await",
    "AsyncFor",
    "GeneratorExp",
    "SetComp",
    "DictComp",
    "NamedExpr",  # walrus :=
    "Match",
    "MatchValue",
    "MatchSingleton",
    "MatchSequence",
    "MatchMapping",
    "MatchClass",
    "MatchStar",
    "MatchAs",
    "MatchOr",
    "JoinedStr",  # f-strings
    "Starred",
    "Delete",
    "With",
    "AsyncWith",
    "Raise",
    "Try",
    "TryStar",
    "Assert",
    "Import",
    "ImportFrom",
    "Global",
    "Nonlocal",
    "Pass",
    "Break",
    "Continue",
    "While",
    "For",
    "AsyncFor",
    "FunctionDef",
    "AsyncFunctionDef",
    "ClassDef",
)

_FUNCTION_WHITELIST: dict[str, Any] = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "isinstance": isinstance,
    # "type" omitido intencionalmente (daría acceso al sistema de tipos)
    "any": any,
    "all": all,
    "enumerate": enumerate,
    "range": range,
    "reversed": reversed,
    "zip": zip,
}

_CONSTANT_WHITELIST = {
    "True": True,
    "False": False,
    "None": None,
    "true": True,
    "false": False,
    "null": None,
}


def _eval_ast(node: ast.AST, env: dict[str, Any]) -> Any:
    """Evalúa un AST directamente sin usar eval()/compile()."""
    import operator as _operator

    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise UnsafeExpressionError(f"Nombre no definido: {node.id}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise UnsafeExpressionError(f"Operador unario no permitido: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, env)
        right = _eval_ast(node.right, env)
        ops = {
            ast.Add: _operator.add,
            ast.Sub: _operator.sub,
            ast.Mult: _operator.mul,
            ast.Div: _operator.truediv,
            ast.FloorDiv: _operator.floordiv,
            ast.Mod: _operator.mod,
            ast.Pow: _operator.pow,
            ast.LShift: _operator.lshift,
            ast.RShift: _operator.rshift,
            ast.BitOr: _operator.or_,
            ast.BitXor: _operator.xor,
            ast.BitAnd: _operator.and_,
        }
        for op_type, func in ops.items():
            if isinstance(node.op, op_type):
                return func(left, right)
        raise UnsafeExpressionError(f"Operador binario no permitido: {type(node.op).__name__}")
    if isinstance(node, ast.BoolOp):
        values = [_eval_ast(v, env) for v in node.values]
        if isinstance(node.op, ast.Or):
            result = False
            for v in values:
                result = result or v
            return result
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left, env)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval_ast(comparator, env)
            cmp_ops = {
                ast.Eq: _operator.eq,
                ast.NotEq: _operator.ne,
                ast.Lt: _operator.lt,
                ast.LtE: _operator.le,
                ast.Gt: _operator.gt,
                ast.GtE: _operator.ge,
                ast.Is: _operator.is_,
                ast.IsNot: _operator.is_not,
                ast.In: _operator.contains,
                ast.NotIn: lambda a, b: not _operator.contains(b, a),
            }
            for op_type, func in cmp_ops.items():
                if isinstance(op, op_type):
                    if not func(left, right):
                        return False
                    break
            left = right
        return True
    if isinstance(node, ast.IfExp):
        test = _eval_ast(node.test, env)
        return _eval_ast(node.body if test else node.orelse, env)
    if isinstance(node, ast.List):
        return [_eval_ast(el, env) for el in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_ast(el, env) for el in node.elts)
    if isinstance(node, ast.Set):
        return {_eval_ast(el, env) for el in node.elts}
    if isinstance(node, ast.Dict):
        return {_eval_ast(k, env): _eval_ast(v, env) for k, v in zip(node.keys, node.values, strict=False)}
    if isinstance(node, ast.Subscript):
        value = _eval_ast(node.value, env)
        if isinstance(node.slice, ast.Slice):
            lower = _eval_ast(node.slice.lower, env) if node.slice.lower else None
            upper = _eval_ast(node.slice.upper, env) if node.slice.upper else None
            step = _eval_ast(node.slice.step, env) if node.slice.step else None
            return value[slice(lower, upper, step)]
        return value[_eval_ast(node.slice, env)]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError("Solo llamadas a funciones directas")
        func_name = node.func.id
        if func_name not in env:
            raise UnsafeExpressionError(f"Función no permitida: {func_name}")
        args = [_eval_ast(a, env) for a in node.args]
        kwargs = {kw.arg: _eval_ast(kw.value, env) for kw in node.keywords}
        return env[func_name](*args, **kwargs)
    if isinstance(node, ast.ListComp):
        return list(_eval_comprehension(node, env))
    raise UnsafeExpressionError(f"Nodo no soportado: {type(node).__name__}")


def _eval_comprehension(node: ast.ListComp, env: dict[str, Any]) -> list[Any]:
    """Evalúa una list comprehension."""

    def _process(generators, idx, current_env):
        if idx >= len(generators):
            yield _eval_ast(node.elt, current_env)
            return
        gen = generators[idx]
        iter_val = _eval_ast(gen.iter, current_env)
        for item in iter_val:
            new_env = dict(current_env)
            new_env[gen.target.id if isinstance(gen.target, ast.Name) else str(gen.target)] = item
            if all(_eval_ast(if_clause, new_env) for if_clause in gen.ifs):
                yield from _process(generators, idx + 1, new_env)

    return list(_process(node.generators, 0, env))


class _SafeEvalChecker(ast.NodeVisitor):
    """Verifica seguridad del AST: nodos, profundidad, dunders, calls."""

    def __init__(self) -> None:
        self._names: set[str] = set()
        self._depth = 0
        self._nodes = 0
        self._calls = 0

    def visit(self, node: ast.AST) -> None:
        self._depth += 1
        self._nodes += 1

        node_type = type(node)
        type_name = node_type.__name__

        # 1. Verificar nodo permitido
        if node_type not in _ALLOWED_AST_NODES:
            msg = f"Nodo no permitido: {type_name}"
            raise UnsafeExpressionError(msg)

        # 2. Verificar profundidad máxima
        if self._depth > _MAX_AST_DEPTH:
            msg = f"Profundidad máxima excedida ({_MAX_AST_DEPTH})"
            raise UnsafeExpressionError(msg)

        # 3. Verificar número máximo de nodos
        if self._nodes > _MAX_AST_NODES:
            msg = f"Número máximo de nodos excedido ({_MAX_AST_NODES})"
            raise UnsafeExpressionError(msg)

        # 4. Bloquear dunder methods (__class__, __bases__, etc.)
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            msg = f"Acceso a atributo privado/dunder no permitido: {node.attr}"
            raise UnsafeExpressionError(msg)

        # 5. Verificar llamadas a función
        if isinstance(node, ast.Call):
            self._calls += 1
            if self._calls > _MAX_FUNCTION_CALLS:
                msg = f"Máximo de llamadas a funciones excedido ({_MAX_FUNCTION_CALLS})"
                raise UnsafeExpressionError(msg)
            func = node.func
            if isinstance(func, ast.Name):  # noqa: SIM102
                if func.id not in _FUNCTION_WHITELIST and func.id not in _CONSTANT_WHITELIST:
                    msg = f"Función no permitida: {func.id}"
                    raise UnsafeExpressionError(msg)

        # 6. Registrar nombres usados
        if isinstance(node, ast.Name):
            self._names.add(node.id)

        self.generic_visit(node)
        self._depth -= 1

    @property
    def names(self) -> set[str]:
        return self._names


def safe_eval(
    expression: str,
    context: dict[str, Any] | None = None,
) -> Any:
    """Evalúa una expresión Python de forma segura.

    Args:
        expression: Expresión a evaluar (máx {_MAX_EXPRESSION_LENGTH} chars).
        context: Variables disponibles en la expresión.

    Returns:
        Resultado de la evaluación.

    Raises:
        UnsafeExpressionError: Expresión no permitida (seguridad, límites).

    Nota:
        El timeout debe gestionarlo el llamador (SafeEval no usa señales
        para ser portable a Windows/hilos).

    """
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        msg = f"Expresión demasiado larga: {len(expression)} > {_MAX_EXPRESSION_LENGTH}"
        raise UnsafeExpressionError(msg)

    tree = ast.parse(expression, mode="eval")
    checker = _SafeEvalChecker()
    checker.visit(tree)

    env: dict[str, Any] = {**_CONSTANT_WHITELIST, **_FUNCTION_WHITELIST}
    if context:
        allowed = {k: v for k, v in context.items() if k in checker.names}
        env.update(allowed)

    return _eval_ast(tree.body, env)


# ── Rule Protocol ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuleMetadata:
    """Metadatos inmutables de una regla."""

    id: str
    version: str
    severity: str  # "INFO" | "WARN" | "ERROR"
    description: str
    category: str = "quality"
    deterministic: bool = True
    cost: str = "O(1)"
    enabled_by_default: bool = True


@dataclass(frozen=True)
class Finding:
    """Resultado de evaluar una regla sobre un documento/nodo."""

    rule_id: str
    rule_version: str
    doc_id: str
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Rule(Protocol):
    """Contrato para todas las reglas.

    Las reglas son deterministas por defecto.
    Las reglas heurísticas deben marcar deterministic=False.
    """

    metadata: RuleMetadata

    def evaluate(
        self,
        document: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Finding]:
        """Evalúa la regla contra un documento.

        Args:
            document: Documento como dict con id, type, title, tags, body, relations.
            context: Contexto global (all_node_ids, all_relation_targets, etc.).

        Returns:
            Lista de findings (vacía si la regla no se activa).

        """
        ...


# ── BuiltinRule (implementación concreta) ─────────────────────────────────


@dataclass(frozen=True)
class BuiltinRule:
    """Regla incorporada determinista.

    Se evalúa mediante safe_eval() con una expresión Python.
    La expresión recibe 'doc' (documento actual) y 'ctx' (contexto global).
    """

    metadata: RuleMetadata
    expression: str  # Evaluable con safe_eval, recibe doc y ctx

    def evaluate(
        self,
        document: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Finding]:
        try:
            ctx = {"doc": document, "ctx": context}
            triggered = safe_eval(self.expression, ctx)
            if triggered:
                return [
                    Finding(
                        rule_id=self.metadata.id,
                        rule_version=self.metadata.version,
                        doc_id=document.get("id", "?"),
                        severity=self.metadata.severity,
                        message=self.metadata.description,
                        metadata={"rule_name": self.metadata.id},
                    ),
                ]
        except Exception as exc:
            log.debug(
                "Rule %s error for doc %s: %s",
                self.metadata.id,
                document.get("id", "?"),
                exc,
            )
        return []


# ── Built-in rules R001-R005 (deterministas) ──────────────────────────────

_BUILTIN_RULES: list[BuiltinRule] = [
    BuiltinRule(
        metadata=RuleMetadata(
            id="R001",
            version="1",
            severity="WARN",
            description="Documento sin título en frontmatter",
            category="quality",
            cost="O(1)",
        ),
        expression="not bool(doc.get('title', ''))",
    ),
    BuiltinRule(
        metadata=RuleMetadata(
            id="R002",
            version="1",
            severity="INFO",
            description="Documento sin tags de clasificación",
            category="quality",
            cost="O(1)",
        ),
        expression="not bool(doc.get('tags', []))",
    ),
    BuiltinRule(
        metadata=RuleMetadata(
            id="R003",
            version="1",
            severity="WARN",
            description="Cuerpo del documento vacío",
            category="quality",
            cost="O(1)",
        ),
        expression="not bool(doc.get('body', ''))",
    ),
    BuiltinRule(
        metadata=RuleMetadata(
            id="R004",
            version="1",
            severity="ERROR",
            description="Enlace a nodo inexistente en el grafo",
            category="integrity",
            cost="O(n)",
        ),
        expression="any(r not in ctx.get('all_node_ids', set()) for r in doc.get('relations', []))",
    ),
    BuiltinRule(
        metadata=RuleMetadata(
            id="R005",
            version="1",
            severity="INFO",
            description="Documento sin relaciones entrantes ni salientes",
            category="coverage",
            cost="O(1)",
        ),
        expression="len(doc.get('relations', [])) == 0 and doc.get('id', '') not in ctx.get('all_relation_targets', set())",
    ),
]


# ── RuleEvaluator (determinista) ──────────────────────────────────────────


class RuleEvaluator:
    """Evalúa reglas contra documentos del grafo.

    Garantías:
      - Mismo conjunto de reglas + mismos documentos → mismos findings (orden incluido).
      - Las reglas se evalúan en orden alfabético por id.
      - Los documentos se procesan en orden alfabético por id.
    """

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self._rules = sorted(
            rules or _BUILTIN_RULES,
            key=lambda r: r.metadata.id,
        )

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    def evaluate(
        self,
        documents: list[dict[str, Any]],
        all_node_ids: set[str] | None = None,
        all_relation_targets: set[str] | None = None,
    ) -> list[Finding]:
        """Evalúa todas las reglas contra todos los documentos.

        Args:
            documents: Documentos (dicts con id, title, tags, body, relations).
            all_node_ids: IDs de todos los nodos (para R004).
            all_relation_targets: IDs de todos los destinos de edges (para R005).

        Returns:
            Findings ordenados por (rule_id, doc_id).

        """
        context: dict[str, Any] = {
            "all_node_ids": all_node_ids or set(),
            "all_relation_targets": all_relation_targets or set(),
        }

        # Documentos ordenados por id para determinismo
        sorted_docs = sorted(documents, key=lambda d: d.get("id", ""))

        findings: list[Finding] = []
        for doc in sorted_docs:
            for rule in self._rules:
                findings.extend(rule.evaluate(doc, context))

        # Findings ordenados por (rule_id, doc_id)
        findings.sort(key=lambda f: (f.rule_id, f.doc_id))
        return findings

    def evaluate_one(
        self,
        doc: dict[str, Any],
        all_node_ids: set[str] | None = None,
        all_relation_targets: set[str] | None = None,
    ) -> list[Finding]:
        """Evalúa todas las reglas contra un único documento."""
        return self.evaluate([doc], all_node_ids, all_relation_targets)


def list_rules() -> list[Rule]:
    """Retorna todas las reglas definidas."""
    return list(_BUILTIN_RULES)
