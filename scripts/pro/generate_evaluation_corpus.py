#!/usr/bin/env python3
"""Generate reproducible evaluation corpus for KE benchmarking.
Outputs to knowledge/evaluation/corpus/"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime

random.seed(42)  # reproducible

QUERIES_SYSTEM = [
    ("sys_001", "How do I configure the Qdrant client in URA?"),
    ("sys_002", "What is DegradedMode and how does it work?"),
    ("sys_003", "How to check if a subsystem is degraded?"),
    ("sys_004", "Explain the purpose of PluginRegistry"),
    ("sys_005", "How does EventBus publish work?"),
    ("sys_006", "What topics does the EventBus support?"),
    ("sys_007", "How to subscribe to pipeline events?"),
    ("sys_008", "What is the difference between publish and emit_sync?"),
    ("sys_009", "How to configure UraConfig?"),
    ("sys_010", "What services does URA run on systemd?"),
    ("sys_011", "How to check URA system health?"),
    ("sys_012", "What is the SubprocessExecutor used for?"),
    ("sys_013", "How to run a command with SubprocessExecutor?"),
    ("sys_014", "How does the Model Router work?"),
    ("sys_015", "What models are configured in Ollama?"),
    ("sys_016", "How to instrument the EventBus with metrics?"),
    ("sys_017", "What health checks does the system support?"),
    ("sys_018", "How to check readiness of system dependencies?"),
    ("sys_019", "How does PipelineExecutor handle stage failures?"),
    ("sys_020", "How does rollback work in a pipeline?"),
    ("sys_021", "What is the HookManager circuit breaker?"),
    ("sys_022", "How to register plugin hooks?"),
    ("sys_023", "What happens when a hook fails 3 times?"),
    ("sys_024", "How to load a legacy F9 plugin in RegistryV2?"),
    ("sys_025", "How does plugin dependency resolution work?"),
    ("sys_026", "What is the PluginManifest format?"),
    ("sys_027", "How to validate plugin API compatibility?"),
    ("sys_028", "What is the MOTOR_API_VERSION?"),
    ("sys_029", "How to set up Prometheus alerting for URA?"),
    ("sys_030", "What alerts are defined in the Prometheus rules?"),
    ("sys_031", "How does the contrast proxy work?"),
    ("sys_032", "What is the purpose of the knowledge engine?"),
    ("sys_033", "How to configure the FTS5 index?"),
    ("sys_034", "What is the UraConfig data_dir used for?"),
    ("sys_035", "How to set up the sandbox container?"),
    ("sys_036", "How does the tuneladora pipeline work?"),
    ("sys_037", "What phases does the tuneladora execute?"),
    ("sys_038", "How to deploy a plugin in URA?"),
    ("sys_039", "What is the difference between RegistryV2 and PluginRegistry?"),
    ("sys_040", "How to check the status of all system services?"),
    ("sys_041", "What metrics are collected by the MetricsRegistry?"),
    ("sys_042", "How to create a custom Counter metric?"),
    ("sys_043", "What is the Timer context manager used for?"),
    ("sys_044", "How to observe histogram buckets?"),
    ("sys_045", "What is the purpose of the readiness registry?"),
    ("sys_046", "How to set a component as unhealthy?"),
    ("sys_047", "What happens when a pipeline stage is optional?"),
    ("sys_048", "How to cancel a pipeline stage via hook?"),
    ("sys_049", "What is the circuit breaker pattern in hooks?"),
    ("sys_050", "How does the compatibility matrix work?"),
    ("sys_051", "What happens if plugin api_version is incompatible?"),
    ("sys_052", "How to add a new EventBus topic?"),
    ("sys_053", "What is the format of topic constants?"),
    ("sys_054", "How to use fnmatch patterns in subscriptions?"),
    ("sys_055", "How does the HTTP adapter expose metrics?"),
    ("sys_056", "What endpoints does the observability HTTP adapter provide?"),
    ("sys_057", "How to check if the system is ready?"),
    ("sys_058", "What does a degraded health status mean?"),
    ("sys_059", "How to register a component for health checks?"),
    ("sys_060", "How does the global health aggregation work?"),
    ("sys_061", "What is the SubprocessExecutor timeout behavior?"),
    ("sys_062", "How does process execution error handling work?"),
    ("sys_063", "What is the ProcessResult dataclass?"),
    ("sys_064", "How to configure plugin dependencies?"),
    ("sys_065", "What is the lifecycle of a plugin?"),
    ("sys_066", "How to implement on_load in a plugin?"),
    ("sys_067", "How to implement rollback in a plugin?"),
    ("sys_068", "What is the PipelineDefinition format?"),
    ("sys_069", "How to define a pipeline stage in YAML?"),
    ("sys_070", "What validation does PipelineLoader perform?"),
]

QUERIES_CODE = [
    ("code_001", "How to run all URA tests with pytest?"),
    ("code_002", "What tests cover the EventBus?"),
    ("code_003", "How to add a new test for PluginRegistryV2?"),
    ("code_004", "What ruff rules are enabled for the project?"),
    ("code_005", "How to fix DTZ005 datetime warnings?"),
    ("code_006", "What is the S603 security rule about?"),
    ("code_007", "How to annotate noqa with justification?"),
    ("code_008", "How to migrate subprocess calls to SubprocessExecutor?"),
    ("code_009", "How to create a mock plugin for testing?"),
    ("code_010", "How to test hook cancellation?"),
    ("code_011", "How to write a benchmark test for pipelines?"),
    ("code_012", "How to test DegradedMode concurrency?"),
    ("code_013", "How to measure test coverage?"),
    ("code_014", "What is the test pattern for EventBus?"),
    ("code_015", "How to create a temp plugin directory for tests?"),
    ("code_016", "How to test plugin manifest parsing?"),
    ("code_017", "How to verify YAML pipeline loading in tests?"),
    ("code_018", "How to write a test for MetricsRegistry?"),
    ("code_019", "How to test HealthRegistry snapshot?"),
    ("code_020", "How to assert ReadinessRegistry state changes?"),
    ("code_021", "How to test instrumentation wrapping?"),
    ("code_022", "How to verify EventBus event counts in tests?"),
    ("code_023", "How to test before_stage hook cancellation?"),
    ("code_024", "How to write an integration test for pipeline rollback?"),
    ("code_025", "How to test circular dependency detection in plugins?"),
    ("code_026", "How to test API version incompatibility?"),
    ("code_027", "What is the pattern for testing exception isolation?"),
    ("code_028", "How to test SubprocessExecutor timeout?"),
    ("code_029", "How to test async command execution?"),
    ("code_030", "How to write integration tests for RegistryV2?"),
    ("code_031", "How to test plugin unload and cleanup?"),
    ("code_032", "How to verify EventBus pattern subscriptions?"),
    ("code_033", "How to test concurrent hook execution?"),
    ("code_034", "How to test pipeline with optional stages?"),
    ("code_035", "How to verify context propagation in pipelines?"),
    ("code_036", "How to write custom assertions for snapshot metrics?"),
    ("code_037", "How to test gauge inc/dec operations?"),
    ("code_038", "How to verify histogram bucket distribution?"),
    ("code_039", "How to mock EventBus for testing?"),
    ("code_040", "How to create fixture for PluginRegistryV2?"),
    ("code_041", "How to test HttpAdapter without FastAPI?"),
    ("code_042", "How to skip tests conditionally based on imports?"),
    ("code_043", "How to structure test files for F11 components?"),
    ("code_044", "How to test plugin discover with subdirectories?"),
    ("code_045", "How to verify loaded plugin count after instrumentation?"),
    ("code_046", "What is the convention for test file naming?"),
    ("code_047", "How to use pytest tmp_path for plugin files?"),
    ("code_048", "How to write a test for PipelineLoader validation?"),
    ("code_049", "How to test the compatibility check functions?"),
    ("code_050", "How to write a test for SemVer parsing?"),
    ("code_051", "How to test plugin dependency range resolution?"),
    ("code_052", "How to verify duplicate plugin name handling?"),
    ("code_053", "How to test legacy F9 plugin compatibility?"),
    ("code_054", "How to test that ruff lint passes for new code?"),
    ("code_055", "How to ensure py_compile passes for all modules?"),
    ("code_056", "How to check for regressions in test suite?"),
    ("code_057", "How to run targeted tests for a specific module?"),
    ("code_058", "How to test the pipeline benchmark assertion?"),
    ("code_059", "How to verify EventBus reset clears all subscribers?"),
    ("code_060", "How to test publish_async non-blocking behavior?"),
    ("code_061", "How to test emit_sync exception isolation?"),
    ("code_062", "How to verify priority ordering of subscribers?"),
    ("code_063", "How to test plugin with custom hooks?"),
    ("code_064", "How to test rollback method on PluginBase?"),
    ("code_065", "How to verify context propagation in pipeline executor?"),
]

QUERIES_KNOWLEDGE = [
    ("know_001", "How does the knowledge engine index documents?"),
    ("know_002", "What is the FTS5 schema for the knowledge base?"),
    ("know_003", "How to search documents using FTS5?"),
    ("know_004", "How does Qdrant store vector embeddings?"),
    ("know_005", "What is cosine similarity in Qdrant?"),
    ("know_006", "How to configure chunk size for indexing?"),
    ("know_007", "What embedding model does URA use?"),
    ("know_008", "How to run a similarity search in Qdrant?"),
    ("know_009", "What is the recall metric for retrieval?"),
    ("know_010", "How is nDCG calculated for search results?"),
    ("know_011", "What is the purpose of reranking?"),
    ("know_012", "How does hybrid retrieval work?"),
    ("know_013", "What is semantic chunking?"),
    ("know_014", "How does query expansion improve search?"),
    ("know_015", "What is the MRR metric in information retrieval?"),
    ("know_016", "How to evaluate search quality metrics?"),
    ("know_017", "What is the difference between Recall and Precision?"),
    ("know_018", "How to collect relevance judgments for evaluation?"),
    ("know_019", "What is the benchmark corpus used for?"),
    ("know_020", "How to measure search latency P50 and P95?"),
    ("know_021", "What is the coverage of the document index?"),
    ("know_022", "How to calculate throughput for search queries?"),
    ("know_023", "What is a good Recall@10 score?"),
    ("know_024", "How to interpret nDCG uplift after reranking?"),
    ("know_025", "What is the baseline KE 1.x retrieval method?"),
    ("know_026", "How does KE 1.x chunk documents?"),
    ("know_027", "What are the limitations of token-based chunking?"),
    ("know_028", "How does the benchmark_ke.py script work?"),
    ("know_029", "What metrics does the benchmark produce?"),
    ("know_030", "How to generate the KE baseline?"),
    ("know_031", "What is MAP and when is it used?"),
    ("know_032", "How to improve retrieval accuracy?"),
    ("know_033", "What documents are in the URA knowledge base?"),
    ("know_034", "How to add new documents to the index?"),
    ("know_035", "How to check if a document is indexed?"),
    ("know_036", "What is the Qdrant collection configuration?"),
    ("know_037", "What distance metric does Qdrant use?"),
    ("know_038", "How to filter search results by metadata?"),
    ("know_039", "What is the timeout for Qdrant queries?"),
    ("know_040", "How does the background queue process indexing?"),
    ("know_041", "How to optimize FTS5 search performance?"),
    ("know_042", "What is the chunk overlap strategy?"),
    ("know_043", "How to evaluate cross-encoder reranking?"),
    ("know_044", "What is the cold cache latency for search?"),
    ("know_045", "How does warm cache affect query latency?"),
    ("know_046", "What is the relation between chunk size and recall?"),
    ("know_047", "How to measure search result diversity?"),
    ("know_048", "What is the 'no context' rate in search?"),
    ("know_049", "How to detect when a query lacks relevant context?"),
    ("know_050", "What is the fragmentation problem in retrieval?"),
    ("know_051", "How to verify the KE baseline reproducibility?"),
    ("know_052", "What makes a search result high quality?"),
    ("know_053", "How to define relevance grades for documents?"),
    ("know_054", "What is graded relevance vs binary relevance?"),
    ("know_055", "How to structure an evaluation corpus?"),
    ("know_056", "What fields are in the queries.jsonl format?"),
    ("know_057", "How to reference documents in relevance judgments?"),
    ("know_058", "What is the role of golden passages in evaluation?"),
    ("know_059", "How to ensure corpus stability across versions?"),
    ("know_060", "What metadata should the evaluation corpus include?"),
    ("know_061", "How to validate corpus integrity?"),
    ("know_062", "How to detect duplicate query IDs?"),
    ("know_063", "How to ensure all relevance scores are valid?"),
    ("know_064", "What is the expected throughput for KE 1.x?"),
    ("know_065", "How to document baseline results?"),
]


def generate_corpus() -> None:
    queries = QUERIES_SYSTEM + QUERIES_CODE + QUERIES_KNOWLEDGE
    base_dir = __file__[: __file__.rfind("/scripts")] if "/scripts" in __file__ else "."
    base_dir += "/knowledge/evaluation/corpus"

    import os

    os.makedirs(base_dir, exist_ok=True)

    # Write queries.jsonl
    with open(f"{base_dir}/queries.jsonl", "w") as f:
        for qid, query in queries:
            domain = "system" if qid.startswith("sys") else "code" if qid.startswith("code") else "knowledge"
            f.write(json.dumps({"qid": qid, "query": query, "domain": domain}, ensure_ascii=False) + "\n")

    # Generate relevance judgments
    # Each query has 1-3 relevant documents (logical doc names that should exist in KE index)
    docs_by_topic = {
        "qdrant": ["qdrant_client_docs", "vector_index_guide", "configuration_reference"],
        "degraded": ["degraded_mode_spec", "state_management_docs", "system_health_guide"],
        "eventbus": ["eventbus_api_docs", "event_topics_reference", "pub_sub_pattern_guide"],
        "pipeline": ["pipeline_executor_docs", "pipeline_definition_format", "pipeline_loader_docs"],
        "plugin": ["plugin_registry_docs", "plugin_manifest_format", "plugin_base_docs"],
        "hooks": ["hook_manager_spec", "hook_circuit_breaker_docs", "event_hooks_guide"],
        "observability": ["metrics_registry_docs", "health_registry_docs", "readiness_registry_docs"],
        "metrics": ["counter_gauge_spec", "histogram_timer_docs", "metrics_snapshot_format"],
        "system": ["system_services_docs", "ura_config_reference", "systemd_service_guide"],
        "router": ["model_router_docs", "ollama_config_guide", "provider_configuration"],
        "knowledge": ["knowledge_engine_docs", "fts5_schema_docs", "qdrant_store_docs"],
        "search": ["search_engine_docs", "retrieval_methods_guide", "query_optimization_docs"],
        "chunking": ["chunking_strategy_docs", "semantic_chunking_guide", "chunk_overlap_spec"],
        "testing": ["test_patterns_guide", "pytest_configuration", "mock_plugin_fixtures"],
        "lint": ["ruff_config_docs", "lint_rules_reference", "security_policies"],
        "benchmark": ["benchmark_ke_docs", "evaluation_corpus_guide", "quality_metrics_reference"],
    }

    topic_map: dict[str, list[str]] = {}
    for qid, _ in queries:
        if qid.startswith("sys"):
            if "qdrant" in qid.lower() or "vector" in qid.lower():
                topic_map.setdefault(qid, []).extend(["qdrant", "knowledge"])
            elif "degraded" in qid.lower() or "health" in qid.lower():
                topic_map.setdefault(qid, []).extend(["degraded", "system", "observability"])
            elif (
                "event" in qid.lower()
                or "publish" in qid.lower()
                or "subscribe" in qid.lower()
                or "topic" in qid.lower()
            ):
                topic_map.setdefault(qid, []).extend(["eventbus", "hooks"])
            elif "pipeline" in qid.lower() or "stage" in qid.lower() or "rollback" in qid.lower():
                topic_map.setdefault(qid, []).extend(["pipeline", "hooks"])
            elif (
                "plugin" in qid.lower()
                or "registry" in qid.lower()
                or "manifest" in qid.lower()
                or "compat" in qid.lower()
            ):
                topic_map.setdefault(qid, []).extend(["plugin"])
            elif "hook" in qid.lower() or "circuit" in qid.lower():
                topic_map.setdefault(qid, []).extend(["hooks", "observability"])
            elif (
                "metric" in qid.lower()
                or "counter" in qid.lower()
                or "gauge" in qid.lower()
                or "histogram" in qid.lower()
                or "timer" in qid.lower()
            ):
                topic_map.setdefault(qid, []).extend(["metrics", "observability"])
            elif "readiness" in qid.lower() or "component" in qid.lower():
                topic_map.setdefault(qid, []).extend(["observability", "system"])
            elif "router" in qid.lower() or "ollama" in qid.lower() or "model" in qid.lower():
                topic_map.setdefault(qid, []).extend(["router", "system"])
            elif "prometheus" in qid.lower() or "alert" in qid.lower():
                topic_map.setdefault(qid, []).extend(["observability", "system"])
            elif "config" in qid.lower() or "services" in qid.lower():
                topic_map.setdefault(qid, []).extend(["system", "knowledge"])
            elif "sandbox" in qid.lower() or "container" in qid.lower():
                topic_map.setdefault(qid, []).extend(["system"])
            elif "tuneladora" in qid.lower():
                topic_map.setdefault(qid, []).extend(["pipeline", "system"])
            elif "deploy" in qid.lower():
                topic_map.setdefault(qid, []).extend(["plugin", "system"])
            else:
                topic_map.setdefault(qid, []).extend(["system"])

        elif qid.startswith("code"):
            if "test" in qid.lower() or "pytest" in qid.lower() or "assert" in qid.lower():
                topic_map.setdefault(qid, []).extend(["testing"])
            elif "ruff" in qid.lower() or "lint" in qid.lower() or "noqa" in qid.lower():
                topic_map.setdefault(qid, []).extend(["lint", "testing"])
            elif "mock" in qid.lower() or "fixture" in qid.lower():
                topic_map.setdefault(qid, []).extend(["testing"])
            elif "benchmark" in qid.lower():
                topic_map.setdefault(qid, []).extend(["testing", "benchmark"])
            elif "coverage" in qid.lower() or "tmp_path" in qid.lower() or "conftest" in qid.lower():
                topic_map.setdefault(qid, []).extend(["testing"])
            else:
                topic_map.setdefault(qid, []).extend(["testing", "system"])

        elif qid.startswith("know"):
            if "chunk" in qid.lower() or "embedding" in qid.lower():
                topic_map.setdefault(qid, []).extend(["chunking", "knowledge"])
            elif (
                "search" in qid.lower()
                or "retriev" in qid.lower()
                or "recall" in qid.lower()
                or "precision" in qid.lower()
            ):
                topic_map.setdefault(qid, []).extend(["search", "knowledge", "benchmark"])
            elif "rerank" in qid.lower() or "cross" in qid.lower():
                topic_map.setdefault(qid, []).extend(["search", "benchmark"])
            elif "fts5" in qid.lower() or "sqlite" in qid.lower():
                topic_map.setdefault(qid, []).extend(["knowledge", "search"])
            elif "qdrant" in qid.lower() or "vector" in qid.lower() or "collection" in qid.lower():
                topic_map.setdefault(qid, []).extend(["knowledge", "qdrant"])
            elif (
                "latency" in qid.lower() or "p50" in qid.lower() or "p95" in qid.lower() or "throughput" in qid.lower()
            ) or "ndcg" in qid.lower() or "mrr" in qid.lower() or "map" in qid.lower():
                topic_map.setdefault(qid, []).extend(["benchmark", "search"])
            elif (
                "corpus" in qid.lower()
                or "benchmark" in qid.lower()
                or "baseline" in qid.lower()
                or "evaluat" in qid.lower()
            ):
                topic_map.setdefault(qid, []).extend(["benchmark", "knowledge"])
            elif "relevance" in qid.lower() or "grade" in qid.lower() or "golden" in qid.lower():
                topic_map.setdefault(qid, []).extend(["benchmark", "search"])
            elif "document" in qid.lower() or "index" in qid.lower():
                topic_map.setdefault(qid, []).extend(["knowledge"])
            elif "queue" in qid.lower():
                topic_map.setdefault(qid, []).extend(["knowledge", "system"])
            elif "coverage" in qid.lower() or "diversity" in qid.lower():
                topic_map.setdefault(qid, []).extend(["benchmark", "search"])
            elif "fragmentation" in qid.lower() or "context" in qid.lower():
                topic_map.setdefault(qid, []).extend(["chunking", "search"])
            else:
                topic_map.setdefault(qid, []).extend(["knowledge", "search"])

    with open(f"{base_dir}/relevance.jsonl", "w") as f:
        for qid, query in queries:
            topics = topic_map.get(qid, ["system"])
            seen_docs: set[str] = set()
            for topic in topics:
                for doc in docs_by_topic.get(topic, []):
                    if doc not in seen_docs:
                        seen_docs.add(doc)
                        grade = random.choice([2, 3]) if topic == topics[0] else random.choice([1, 2])
                        f.write(
                            json.dumps(
                                {
                                    "qid": qid,
                                    "doc_id": doc,
                                    "relevance": grade,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )

    # Metadata
    domain_counts: dict[str, int] = {}
    for qid, _ in queries:
        domain = "system" if qid.startswith("sys") else "code" if qid.startswith("code") else "knowledge"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    total_rel = len(open(f"{base_dir}/relevance.jsonl").readlines())
    unique_docs = len(
        {
            line.split('"doc_id":')[1].split('"')[1]
            for line in open(f"{base_dir}/relevance.jsonl")
            if '"doc_id":' in line
        }
    )

    metadata = {
        "version": "1.0.0",
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_queries": len(queries),
        "domains": {k: {"count": v, "pct": round(v / len(queries) * 100, 1)} for k, v in sorted(domain_counts.items())},
        "total_relevance_judgments": total_rel,
        "unique_documents": unique_docs,
        "source": "generated from URA codebase knowledge",
        "seed": 42,
    }
    with open(f"{base_dir}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Corpus generado: {len(queries)} queries, {total_rel} relevance judgments, {unique_docs} docs")
    for d, info in sorted(metadata["domains"].items()):
        print(f"  {d}: {info['count']} queries ({info['pct']}%)")


if __name__ == "__main__":
    generate_corpus()
