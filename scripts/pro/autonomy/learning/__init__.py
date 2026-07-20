"""Learning — subsistema de aprendizaje avanzado para autonomía.

Componentes:
  PatternAnalyzer    — detecta patrones repetitivos
  KnowledgeBase      — persiste conocimiento útil
  RecommendationEngine — transforma patrones en recomendaciones
  PolicyEngine       — decide aplicar políticas (observación/asistido/autónomo)
  TrendMonitor       — verifica impacto de políticas aplicadas
"""

from scripts.pro.autonomy.learning.pattern_analyzer import PatternAnalyzer
from scripts.pro.autonomy.learning.knowledge_base import KnowledgeBase
from scripts.pro.autonomy.learning.recommendation_engine import RecommendationEngine
from scripts.pro.autonomy.learning.policy_engine import PolicyEngine
from scripts.pro.autonomy.learning.trend_monitor import TrendMonitor

__all__ = [
    "PatternAnalyzer",
    "KnowledgeBase",
    "RecommendationEngine",
    "PolicyEngine",
    "TrendMonitor",
]
