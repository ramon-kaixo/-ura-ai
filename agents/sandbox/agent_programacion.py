"""Agente Programación — analiza documentación técnica y código."""
import re

def process(text: str, meta: dict) -> dict:
    result = {
        "categoria": "programacion",
        "tokens": len(text.split()),
        "lenguajes": [],
        "frameworks": [],
        "tipo": "documentacion",
        "relevante": False,
    }

    # Detectar lenguajes
    langs = ["python", "javascript", "typescript", "rust", "go", "java", "c++", "bash"]
    for lang in langs:
        if lang in text.lower():
            result["lenguajes"].append(lang)

    # Detectar frameworks
    frameworks = ["fastapi", "django", "react", "vue", "langchain", "ollama",
                  "pytorch", "tensorflow", "docker", "kubernetes"]
    for fw in frameworks:
        if fw in text.lower():
            result["frameworks"].append(fw)

    # Detectar si tiene código
    if re.search(r'(def |class |import |from |async |await )', text):
        result["tipo"] = "codigo"
        result["relevante"] = True
    elif any(fw in text.lower() for fw in ["api", "documentacion", "tutorial", "guia"]):
        result["tipo"] = "documentacion"
        result["relevante"] = True

    return result
