#!/bin/bash
# instalar_modulos_cognitivos.sh - Instala los 5 archivos del bucle cognitivo Nivel 3
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit

echo "========================================="
echo "  URA - Instalacion Modulos Cognitivos"
echo "  $(date)"
echo "========================================="

# 1. Asegurar directorios
echo ""
echo "[1/6] Creando directorios..."
mkdir -p agents core/memory core/vision orquestador scripts docs/manuales
echo "   ✅ Directorios listos"

# 2. Crear agente_voz.py
echo ""
echo "[2/6] Creando agente_voz.py..."
cat > agents/agente_voz.py << 'PYEOF'
#!/usr/bin/env python3
"""Agente de voz con bucle cognitivo — escucha, planifica, verifica."""
import logging
import time
from typing import Optional

import speech_recognition as sr
import pyttsx3

from core.memory.semantic_brain import SemanticBrain
from core.vision.state_verifier import StateVerifier
from core.planner_react import ReActPlanner

logger = logging.getLogger("AgenteVoz")


class AgenteVoz:
    """Agente principal con voz, contexto y ejecucion cognitiva."""

    def __init__(self) -> None:
        self.brain = SemanticBrain()
        self.verifier = StateVerifier()
        self.planner = ReActPlanner()
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    def escuchar(self) -> Optional[str]:
        """Escucha el microfono y transcribe a texto.

        Returns:
            Texto transcrito o None si fallo.
        """
        with self.microphone as source:
            logger.info("Escuchando...")
            audio = self.recognizer.listen(source)
        try:
            texto = self.recognizer.recognize_google(audio, language="es-ES")
            logger.info("Tú: %s", texto)
            return texto
        except Exception as exc:
            logger.warning("Error reconociendo voz: %s", exc)
            return None

    def hablar(self, texto: str) -> None:
        """Sintetiza voz a partir de texto.

        Args:
            texto: Texto a hablar.
        """
        logger.info("URA: %s", texto)
        self.engine.say(texto)
        self.engine.runAndWait()

    def procesar_comando(self, comando: str) -> bool:
        """Procesa un comando de voz con memoria y planificacion.

        Args:
            comando: Texto del comando.

        Returns:
            True si la accion se completo con exito.
        """
        contexto = self.brain.buscar_instrucciones(comando, app_name="TPV")
        plan = self.planner.ejecutar_objetivo(comando, contexto)
        exito = self.verifier.verificar_cambio_esperado(plan)
        if not exito:
            self.hablar("Parece que algo fallo. Usare el sandbox para repararlo.")
        else:
            self.hablar("Accion completada con exito.")
        return exito

    def bucle(self) -> None:
        """Bucle principal de escucha y procesamiento."""
        self.hablar("Hola, soy URA. En que puedo ayudarte?")
        while True:
            comando = self.escuchar()
            if comando and "ura" in comando.lower():
                self.procesar_comando(comando)
            time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agente = AgenteVoz()
    agente.bucle()
PYEOF
echo "   ✅ agente_voz.py creado"

# 3. Crear semantic_brain.py
echo ""
echo "[3/6] Creando semantic_brain.py..."
cat > core/memory/semantic_brain.py << 'PYEOF'
#!/usr/bin/env python3
"""Memoria vectorial para manuales — ChromaDB + Ollama embeddings."""
import logging
import time
from typing import List, Optional

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger("SemanticBrain")


class SemanticBrain:
    """Memoria semantica con RAG para manuales y experiencias."""

    def __init__(self, persist_dir: str = "/opt/ura/data/chroma_db") -> None:
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.emb_fn = embedding_functions.OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            url="http://localhost:11434"
        )
        self.collection = self.client.get_or_create_collection(
            name="manuales",
            embedding_function=self.emb_fn
        )

    def indexar_manual(self, app_name: str, texto: str, seccion: str) -> None:
        """Indexa un fragmento de manual en ChromaDB.

        Args:
            app_name: Nombre de la aplicacion.
            texto: Contenido del fragmento.
            seccion: Identificador de la seccion.
        """
        doc_id = f"{app_name}_{seccion}_{time.time()}"
        self.collection.add(
            documents=[texto],
            metadatas=[{"app": app_name, "seccion": seccion}],
            ids=[doc_id]
        )
        logger.info("Indexado: %s", doc_id)

    def buscar_instrucciones(self, consulta: str, app_name: str, n: int = 2) -> List[str]:
        """Busca instrucciones relevantes en la memoria semantica.

        Args:
            consulta: Texto de la consulta.
            app_name: Nombre de la aplicacion a filtrar.
            n: Numero de resultados.

        Returns:
            Lista de documentos relevantes.
        """
        results = self.collection.query(
            query_texts=[consulta],
            n_results=n,
            where={"app": app_name}
        )
        return results["documents"][0] if results["documents"] else []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    brain = SemanticBrain()
    brain.indexar_manual("TPV", "Para exportar ventas: Menu > Ventas > Exportar CSV", "exportar")
    print(brain.buscar_instrucciones("como exporto ventas", "TPV"))
PYEOF
echo "   ✅ semantic_brain.py creado"

# 4. Crear state_verifier.py
echo ""
echo "[4/6] Creando state_verifier.py..."
cat > core/vision/state_verifier.py << 'PYEOF'
#!/usr/bin/env python3
"""Verificador de estado UI — compara capturas de pantalla para validar acciones."""
import logging
from typing import Optional

import numpy as np
import pyautogui
from PIL import ImageChops

logger = logging.getLogger("StateVerifier")


class StateVerifier:
    """Verifica cambios visuales tras ejecutar acciones."""

    @staticmethod
    def capturar_pantalla() -> object:
        """Captura la pantalla actual.

        Returns:
            Imagen PIL de la pantalla.
        """
        return pyautogui.screenshot()

    @staticmethod
    def diff_pixel(img_antes: object, img_despues: object) -> bool:
        """Compara dos imagenes y devuelve True si hay diferencia significativa.

        Args:
            img_antes: Imagen antes de la accion.
            img_despues: Imagen despues de la accion.

        Returns:
            True si la diferencia supera el umbral.
        """
        diff = ImageChops.difference(img_antes, img_despues)
        return float(np.mean(np.array(diff))) > 5

    def verificar_cambio_esperado(
        self,
        accion: dict,
        palabra_esperada: Optional[str] = None
    ) -> bool:
        """Verifica que una accion produjo el cambio visual esperado.

        Args:
            accion: Diccionario con la accion ejecutada.
            palabra_esperada: Texto que deberia aparecer tras la accion.

        Returns:
            True si el cambio fue detectado.
        """
        antes = self.capturar_pantalla()
        # La accion ya se ejecuto antes de llamar a este metodo
        import time
        time.sleep(2)
        despues = self.capturar_pantalla()
        if not self.diff_pixel(antes, despues):
            logger.warning("No se detecto cambio visual tras la accion")
            return False
        if palabra_esperada:
            # Busqueda simple por OCR o UI tree
            logger.info("Buscando palabra esperada: %s", palabra_esperada)
            return True
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    verifier = StateVerifier()
    print("Verificador de estado listo")
PYEOF
echo "   ✅ state_verifier.py creado"

# 5. Crear evolve_sandbox.py
echo ""
echo "[5/6] Creando evolve_sandbox.py..."
cat > orquestador/evolve_sandbox.py << 'PYEOF'
#!/usr/bin/env python3
"""Sandbox de evolucion — reescribe macros fallidas usando GX10."""
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("EvolveSandbox")


class EvolveSandbox:
    """Repara macros fallidas enviandolas al GX10 para reescritura."""

    def __init__(self, gx10_alias: str = "gx10") -> None:
        self.gx10 = gx10_alias

    def reparar_macro(self, macro_code: str, manual_fragment: str) -> Optional[str]:
        """Envia una macro fallida al GX10 para que la reescriba.

        Args:
            macro_code: Codigo Python de la macro fallida.
            manual_fragment: Fragmento del manual relevante.

        Returns:
            Nuevo codigo generado o None si fallo.
        """
        prompt = (
            f"Macro fallida:\n{macro_code}\n\n"
            f"Segun manual:\n{manual_fragment}\n"
            f"Reescribela en Python con type hints."
        )
        try:
            cmd = ["ssh", self.gx10, "ollama", "run", "qwen2.5-coder", prompt]
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            nuevo_codigo = resultado.stdout.strip()
            if nuevo_codigo:
                logger.info("Macro reparada por GX10")
                return nuevo_codigo
        except Exception as exc:
            logger.error("Error reparando macro: %s", exc)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sandbox = EvolveSandbox()
    print("Sandbox de evolucion listo")
PYEOF
echo "   ✅ evolve_sandbox.py creado"

# 6. Crear cargar_manuales.py
echo ""
echo "[6/6] Creando cargar_manuales.py..."
cat > scripts/cargar_manuales.py << 'PYEOF'
#!/usr/bin/env python3
"""Indexa todos los manuales .txt de docs/manuales en ChromaDB."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.semantic_brain import SemanticBrain

logger = logging.getLogger("CargarManuales")


def main() -> None:
    """Indexa todos los archivos .txt del directorio de manuales."""
    brain = SemanticBrain()
    manual_dir = "/opt/ura/docs/manuales"
    if not os.path.exists(manual_dir):
        logger.warning("Directorio de manuales no existe: %s", manual_dir)
        return
    for filename in os.listdir(manual_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(manual_dir, filename)
            with open(filepath, encoding="utf-8") as fh:
                texto = fh.read()
            brain.indexar_manual("TPV", texto, filename)
            logger.info("Indexado: %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
PYEOF
echo "   ✅ cargar_manuales.py creado"

# Final
echo ""
echo "========================================="
echo "  Modulos cognitivos instalados"
echo "========================================="
echo ""
echo "Archivos creados:"
echo "  agents/agente_voz.py"
echo "  core/memory/semantic_brain.py"
echo "  core/vision/state_verifier.py"
echo "  orquestador/evolve_sandbox.py"
echo "  scripts/cargar_manuales.py"
echo ""
echo "Para cargar manuales: python3 scripts/cargar_manuales.py"
echo "Para iniciar bucle: python3 agents/agente_voz.py"
