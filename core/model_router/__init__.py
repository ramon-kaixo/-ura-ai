"""Model Router Enhanced — dividido en submódulos con compatibilidad hacia atrás.

Importa todo desde model_router_main.py (archivo original) para mantener
la compatibilidad mientras se migran funciones a submódulos.
"""

from core.model_router_main import *  # noqa: F401, F403
