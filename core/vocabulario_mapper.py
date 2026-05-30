#!/usr/bin/env python3
"""
URA Vocabulario Mapper - Integración Vocabulario-Herramientas
Sistema para mapear vocabulario a herramientas y descubrir herramientas por palabras
"""

from collections import defaultdict

from core.tool_registry import TOOL_REGISTRY


# ============================================================
# MAPPER DE VOCABULARIO A HERRAMIENTAS
# ============================================================
class VocabularioMapper:
    """Mapeador de vocabulario a herramientas"""

    def __init__(self, tool_registry=None):
        self.registry = tool_registry or TOOL_REGISTRY
        self.word_to_tools: dict[str, list[str]] = defaultdict(list)
        self.category_to_words: dict[str, list[str]] = defaultdict(list)
        self._build_index()

    def _build_index(self):
        """Construir índice de palabras a herramientas"""
        for tool_id, spec in self.registry.tools.items():
            if "vocabulario" in spec:
                for categoria, palabras in spec["vocabulario"].items():
                    for palabra in palabras:
                        palabra_lower = palabra.lower()
                        self.word_to_tools[palabra_lower].append(tool_id)

                        # También indexar por categoría de vocabulario
                        cat_key = f"{spec['categoria'].value}_{categoria}"
                        self.category_to_words[cat_key].append(palabra_lower)

    def find_tools_by_word(self, palabra: str) -> list[str]:
        """
        Encontrar herramientas que usan una palabra

        Args:
            palabra: Palabra a buscar

        Returns:
            Lista de IDs de herramientas
        """
        palabra_lower = palabra.lower()

        # Búsqueda exacta
        if palabra_lower in self.word_to_tools:
            return self.word_to_tools[palabra_lower]

        # Búsqueda parcial
        results = []
        for word, tool_ids in self.word_to_tools.items():
            if palabra_lower in word:
                results.extend(tool_ids)

        # Eliminar duplicados
        return list(set(results))

    def get_vocabulario_for_tool(self, tool_id: str) -> dict[str, list[str]]:
        """
        Obtener vocabulario de una herramienta

        Args:
            tool_id: ID de la herramienta

        Returns:
            Diccionario de categorías de vocabulario
        """
        spec = self.registry.get(tool_id)
        return spec.get("vocabulario", {}) if spec else {}

    def get_words_by_category(self, tool_categoria: str, vocab_categoria: str) -> list[str]:
        """
        Obtener palabras por categoría de herramienta y vocabulario

        Args:
            tool_categoria: Categoría de herramienta (ej: "llm")
            vocab_categoria: Categoría de vocabulario (ej: "palabras_clave")

        Returns:
            Lista de palabras
        """
        cat_key = f"{tool_categoria}_{vocab_categoria}"
        return self.category_to_words.get(cat_key, [])

    def suggest_tool_for_query(self, query: str) -> list[str]:
        """
        Sugerir herramientas basado en una consulta

        Args:
            query: Consulta del usuario

        Returns:
            Lista de IDs de herramientas sugeridas (ordenadas por relevancia)
        """
        query_lower = query.lower()
        palabras = query_lower.split()

        # Contar coincidencias por herramienta
        tool_scores = defaultdict(int)

        for palabra in palabras:
            tool_ids = self.find_tools_by_word(palabra)
            for tool_id in tool_ids:
                tool_scores[tool_id] += 1

        # Ordenar por score
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)

        return [tool_id for tool_id, score in sorted_tools if score > 0]

    def get_synonyms(self, palabra: str) -> list[str]:
        """
        Obtener sinónimos de una palabra del vocabulario

        Args:
            palabra: Palabra a buscar

        Returns:
            Lista de sinónimos
        """
        tool_ids = self.find_tools_by_word(palabra)
        synonyms = set()

        for tool_id in tool_ids:
            vocab = self.get_vocabulario_for_tool(tool_id)
            if "sinonimos" in vocab:
                synonyms.update(vocab["sinonimos"])

        return list(synonyms)

    def get_technical_terms(self, tool_categoria: str) -> list[str]:
        """
        Obtener términos técnicos de una categoría de herramientas

        Args:
            tool_categoria: Categoría de herramienta (ej: "llm")

        Returns:
            Lista de términos técnicos
        """
        return self.get_words_by_category(tool_categoria, "terminos_tecnicos")

    def get_keywords(self, tool_categoria: str) -> list[str]:
        """
        Obtener palabras clave de una categoría de herramientas

        Args:
            tool_categoria: Categoría de herramienta (ej: "llm")

        Returns:
            Lista de palabras clave
        """
        return self.get_words_by_category(tool_categoria, "palabras_clave")

    def expand_query(self, query: str) -> list[str]:
        """
        Expandir consulta con sinónimos y palabras relacionadas

        Args:
            query: Consulta original

        Returns:
            Lista de consultas expandidas
        """
        query_lower = query.lower()
        palabras = query_lower.split()

        expanded_queries = [query_lower]

        for palabra in palabras:
            synonyms = self.get_synonyms(palabra)
            for synonym in synonyms:
                expanded_query = query_lower.replace(palabra, synonym)
                if expanded_query != query_lower:
                    expanded_queries.append(expanded_query)

        # Eliminar duplicados
        return list(set(expanded_queries))

    def get_stats(self) -> dict:
        """Obtener estadísticas del mapper"""
        total_palabras = len(self.word_to_tools)
        total_categorias = len(self.category_to_words)

        # Contar palabras por categoría de vocabulario
        vocab_cat_counts = defaultdict(int)
        for cat_key in self.category_to_words:
            vocab_cat = cat_key.split("_")[-1]
            vocab_cat_counts[vocab_cat] += len(self.category_to_words[cat_key])

        return {
            "total_palabras": total_palabras,
            "total_categorias": total_categorias,
            "por_categoria_vocabulario": dict(vocab_cat_counts),
        }


# Instancia global
VOCABULARIO_MAPPER = VocabularioMapper()

# Test
if __name__ == "__main__":
    print("=" * 50)
    print("URA Vocabulario Mapper - Test")
    print("=" * 50)

    # Test buscar herramientas por palabra
    print("\n🔍 Buscar herramientas por palabra:")
    tools = VOCABULARIO_MAPPER.find_tools_by_word("consulta")
    print(f"   'consulta' → {tools}")

    tools = VOCABULARIO_MAPPER.find_tools_by_word("modelo")
    print(f"   'modelo' → {tools}")

    # Test vocabulario de herramienta
    print("\n📚 Vocabulario de herramienta:")
    vocab = VOCABULARIO_MAPPER.get_vocabulario_for_tool("llm_ollama")
    print(f"   llm_ollama: {vocab}")

    # Test sugerir herramienta para consulta
    print("\n💡 Sugerir herramienta para consulta:")
    suggestions = VOCABULARIO_MAPPER.suggest_tool_for_query("quiero hacer una consulta")
    print(f"   'quiero hacer una consulta' → {suggestions}")

    # Test obtener sinónimos
    print("\n🔄 Sinónimos:")
    synonyms = VOCABULARIO_MAPPER.get_synonyms("consulta")
    print(f"   'consulta' → {synonyms}")

    # Test términos técnicos
    print("\n🔧 Términos técnicos LLM:")
    terms = VOCABULARIO_MAPPER.get_technical_terms("llm")
    print(f"   {terms}")

    # Test palabras clave
    print("\n🔑 Palabras clave LLM:")
    keywords = VOCABULARIO_MAPPER.get_keywords("llm")
    print(f"   {keywords}")

    # Test expandir consulta
    print("\n📝 Expandir consulta:")
    expanded = VOCABULARIO_MAPPER.expand_query("hacer una consulta")
    print(f"   'hacer una consulta' → {expanded}")

    # Test estadísticas
    print("\n📊 Estadísticas:")
    stats = VOCABULARIO_MAPPER.get_stats()
    print(f"   {stats}")

    print("\n✅ Vocabulario Mapper OK")
