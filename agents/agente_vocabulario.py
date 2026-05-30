#!/usr/bin/env python3
"""
Agente de Vocabulario - Análisis con Ollama y generación de .estado.json
Analiza contenido y genera estado semántico
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

MODELO_OLLAMA = "policia"
BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
RUTA_BASE = BASE_DIR / "sandbox"


class AgenteVocabulario:
    """Agente que analiza contenido con Ollama y genera estados"""

    def __init__(self):
        self.historial = []
        self.modelo = MODELO_OLLAMA
        # Importar guardrails
        try:
            from core.vocabulario.guardrails_vocabulario import guardrails_vocabulario

            self.guardrails = guardrails_vocabulario
        except:
            self.guardrails = None

    def _llamar_ollama(self, prompt: str) -> str:
        """Llama a Ollama para analizar con guardrails"""

        try:
            result = subprocess.run(
                ["ollama", "run", self.modelo, prompt], capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            if self.guardrails:
                self.guardrails.registrar_error("timeout", "Ollama timeout")
            return "Error: Timeout Ollama"
        except Exception as e:
            if self.guardrails:
                self.guardrails.registrar_error("ollama_error", str(e))
            return f"Error: {str(e)}"

    def analizar(self, contenido: str, tipo: str = "texto") -> dict:
        """Analiza el contenido y genera un estado con guardrails"""

        # Verificar tasa de errores antes de continuar
        if self.guardrails and not self.guardrails.verificar_tasa_errores():
            # Tasa de errores muy alta, usar fallback
            return {
                "timestamp": datetime.now().isoformat(),
                "tipo": tipo,
                "error": "Tasa de errores muy alta, usando fallback",
                "estado": self.guardrails.fallback_vocabulario_tecnico("python"),
            }

        ahora = datetime.now().isoformat()

        if tipo == "texto":
            prompt = f"""Analiza este contenido y devuelve un JSON con:
- categoria: (receta/legal/tecnico/general)
- nivel_seguridad: (publico/sensible/critico)
- palabras_clave: lista de 5 palabras clave
- resumen: 1 línea

Contenido: {contenido[:500]}

Responde SOLO con JSON:"""

            respuesta = self._llamar_ollama(prompt)

            # Validar respuesta con guardrails
            if self.guardrails:
                validacion = self.guardrails.validar_respuesta_ollama(respuesta)
                if not validacion["valida"]:
                    self.guardrails.registrar_error("validacion", validacion["error"])
                    # Usar fallback
                    estado = self.guardrails.fallback_vocabulario_tecnico("python")
                else:
                    estado = validacion["datos"]
            else:
                try:
                    estado = json.loads(respuesta)
                except:
                    estado = {
                        "categoria": "general",
                        "nivel_seguridad": "publico",
                        "palabras_clave": [],
                        "resumen": respuesta[:100],
                    }

        elif tipo == "archivo":
            nombre = Path(contenido).name
            extension = Path(contenido).suffix.lower()

            categorias = {
                ".py": "tecnico",
                ".js": "tecnico",
                ".json": "tecnico",
                ".pdf": "documento",
                ".doc": "documento",
                ".txt": "nota",
                ".jpg": "imagen",
                ".png": "imagen",
            }

            estado = {
                "categoria": categorias.get(extension, "desconocido"),
                "nivel_seguridad": "publico",
                "palabras_clave": [extension.replace(".", "")],
                "resumen": f"Archivo {extension} - {nombre}",
            }

        hash_contenido = hashlib.sha256(contenido.encode()).hexdigest()[:16]

        resultado = {"timestamp": ahora, "tipo": tipo, "hash": hash_contenido, "estado": estado}

        self.historial.append(resultado)

        return resultado

    def generar_estado_json(self, analisis: dict, ruta_salida: Path) -> bool:
        """Guarda el análisis en un archivo .estado.json"""

        try:
            contenido = {
                "analisis": analisis,
                "generado": datetime.now().isoformat(),
                "version": "1.0",
            }

            ruta_salida.write_text(json.dumps(contenido, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            print(f"Error guardando estado: {e}")
            return False

    def analizar_pasillo(self, nombre_pasillo: str) -> dict:
        """Analiza todos los archivos de un pasillo"""

        ruta_pasillo = RUTA_BASE / nombre_pasillo

        if not ruta_pasillo.exists():
            return {"error": f"Pasillo {nombre_pasillo} no existe"}

        archivos = []

        for archivo in ruta_pasillo.rglob("*"):
            if archivo.is_file() and not archivo.name.endswith(".estado.json"):
                resultado = self.analizar(str(archivo), tipo="archivo")
                archivos.append(
                    {
                        "nombre": archivo.name,
                        "ruta": str(archivo.relative_to(RUTA_BASE)),
                        "estado": resultado["estado"],
                    }
                )

                estado_json = archivo.parent / f"{archivo.stem}.estado.json"
                self.generar_estado_json(resultado, estado_json)

        return {
            "pasillo": nombre_pasillo,
            "archivos_encontrados": len(archivos),
            "archivos": archivos[:10],
        }


_agente_vocabulario = None


def get_agente_vocabulario() -> AgenteVocabulario:
    global _agente_vocabulario
    if _agente_vocabulario is None:
        _agente_vocabulario = AgenteVocabulario()
    return _agente_vocabulario

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabulario."""
        texto.lower()
        return "Puedo definir palabras, sinónimos y diccionarios. ¿Qué palabra necesitas definir?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabulario."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabulario."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabulario."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = get_agente_vocabulario()

    print("=" * 60)
    print("📚 AGENTE DE VOCABULARIO - ANÁLISIS CON OLLAMA")
    print("=" * 60)

    print("\n🔍 Analizando texto...")
    resultado = agente.analizar(
        "Receta de paella Valenciana tradicional con arroz bomba", tipo="texto"
    )

    print(f"\n   Categoría: {resultado['estado'].get('categoria')}")
    print(f"   Seguridad: {resultado['estado'].get('nivel_seguridad')}")
    print(f"   Palabras clave: {resultado['estado'].get('palabras_clave')}")
    print(f"   Resumen: {resultado['estado'].get('resumen')}")
    print(f"   Hash: {resultado['hash']}")

    print("\n📁 Analizando pasillo (Aduana)...")
    resultado_pasillo = agente.analizar_pasillo("Aduana")
    print(f"   Archivos: {resultado_pasillo.get('archivos_encontrados', 0)}")

    print("\n✅ Agente de Vocabulario listo")
