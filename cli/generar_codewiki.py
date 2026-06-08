#!/usr/bin/env python3
"""generar_codewiki.py — Google Code Wiki local con Gemini (free tier)."""
import os, sys
from pathlib import Path

def mapear_repositorio():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import json
            c = json.load(open(Path.home() / ".config/opencode/.credentials/gemini.json"))
            api_key = c.get("api_key", c.get("key", ""))
        except: pass
    if not api_key:
        print("Error: GEMINI_API_KEY no encontrada", file=sys.stderr)
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)
    raiz = Path(".").resolve()
    
    print("[CodeWiki] Escaneando estructura (solo arbol, sin contenido)...")
    arbol = []
    for root, dirs, files in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'prompt_cache', '.nervioso', 'node_modules', '__pycache__')]
        nivel = Path(root).relative_to(raiz)
        indent = '  ' * len(nivel.parts)
        if nivel != Path('.'):
            arbol.append(f"{indent}{nivel.name}/")
        for f in files:
            arbol.append(f"{indent}  {f}")

    arbol_texto = "\n".join(arbol)
    
    prompt = f"""Eres un Staff Engineer. Basado en este arbol de proyecto:
    
{arbol_texto}

Genera en MARKDOWN:
1. ARQUITECTURA: Diagrama ASCII de componentes y flujos principales
2. AUDITORIA: Patrones, posibles problemas, desviaciones
3. RECOMENDACIONES: Mejoras clave

Responde SOLO el analisis, sin introduccion."""
    
    print("[CodeWiki] Analizando arbol con Gemini 2.0 Flash...")
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        Path("docs").mkdir(exist_ok=True)
        wiki_path = Path("docs/CODE_WIKI.md")
        wiki_path.write_text(response.text, encoding='utf-8')
        print(f"\nOK — Code Wiki generada en {wiki_path}")
        print(response.text[:2000])
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    mapear_repositorio()
