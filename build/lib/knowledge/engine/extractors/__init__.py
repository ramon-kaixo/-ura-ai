"""Extractors — pipeline de extracción de metadatos para Capa 11.

Cada extractor implementa Extractor(Protocol) y produce KnowledgeAssets.
Los extractores son independientes, ejecutables en paralelo.
"""

from knowledge.engine.extractors.audio import AudioExtractor as AudioExtractor
from knowledge.engine.extractors.base import (
    ExtractionResult as ExtractionResult,
)
from knowledge.engine.extractors.base import (
    Extractor as Extractor,
)
from knowledge.engine.extractors.base import (
    ExtractorRegistry as ExtractorRegistry,
)
from knowledge.engine.extractors.git import GitExtractor as GitExtractor
from knowledge.engine.extractors.image import ImageExtractor as ImageExtractor
from knowledge.engine.extractors.markdown import MarkdownExtractor as MarkdownExtractor
from knowledge.engine.extractors.office import OfficeExtractor as OfficeExtractor
from knowledge.engine.extractors.pdf import PdfExtractor as PdfExtractor
from knowledge.engine.extractors.video import VideoExtractor as VideoExtractor
from knowledge.engine.extractors.web import WebExtractor as WebExtractor
