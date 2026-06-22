import ast

MAX_COMPLEXITY = 10

BLOCKED_CALLS = {
    "os.system": "uso de os.system() prohibido fuera del sandbox",
    "subprocess.call": "subprocess.call() prohibido en codigo generado",
    "subprocess.Popen": "subprocess.Popen() prohibido en codigo generado",
    "subprocess.run": "subprocess.run() prohibido en codigo generado",
    "eval": "eval() prohibido en codigo generado",
    "exec": "exec() prohibido en codigo generado",
    "compile": "compile() prohibido en codigo generado",
    "__import__": "__import__() prohibido en codigo generado",
}


class RefactorRequiredError(Exception):
    pass


class InjectionError(Exception):
    pass


def cyclomatic_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    c = 1
    for node in ast.walk(func_node):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Assert)):
            c += 1
        elif isinstance(node, ast.BoolOp):
            c += len(node.values) - 1
        elif isinstance(node, (ast.ExceptHandler, ast.With, ast.AsyncWith)):
            c += 1
        elif isinstance(node, ast.Try):
            c += len(node.handlers)
    return c


def check_complexity(tree: ast.AST) -> list[str]:
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = cyclomatic_complexity(node)
            if cc > MAX_COMPLEXITY:
                errors.append(
                    f"FUNCION '{node.name}': complejidad ciclomatica {cc} "
                    f"supera el maximo {MAX_COMPLEXITY}. RefactorRequiredError.",
                )
    return errors


def check_injections(tree: ast.AST) -> list[str]:
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            call_str = ""
            if isinstance(func, ast.Attribute):
                call_str = f"{ast.unparse(func.value)}.{func.attr}"
            elif isinstance(func, ast.Name):
                call_str = func.id

            if call_str in BLOCKED_CALLS:
                errors.append(
                    f"LINEA {node.lineno}: {BLOCKED_CALLS[call_str]} (llamada: {call_str})",
                )

            if call_str == "open" and len(node.args) >= 2:
                mode_arg = node.args[1]
                if isinstance(mode_arg, ast.Constant) and "w" in str(mode_arg.value):
                    errors.append(
                        f"LINEA {node.lineno}: open() en modo escritura prohibido en codigo generado",
                    )
    return errors


def lint_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SyntaxError(f"SyntaxError: {e}")

    cpx_errs = check_complexity(tree)
    if cpx_errs:
        raise RefactorRequiredError(cpx_errs[0])

    inj_errs = check_injections(tree)
    if inj_errs:
        raise InjectionError(inj_errs[0])
