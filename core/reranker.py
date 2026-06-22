import logging
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MODEL_DIR = Path(__file__).parent.parent / "models" / "reranker"
ONNX_PATH = MODEL_DIR / "model.onnx"
MAX_LENGTH = 512
COMPOSITE_ALPHA = 0.7

_tokenizer = None
_session = None
_init_lock = threading.Lock()


def _ensure_model():
    global _tokenizer, _session
    if _session is not None and _tokenizer is not None:
        return
    with _init_lock:
        if _session is not None and _tokenizer is not None:
            return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not ONNX_PATH.exists():
        log.info("Exportando cross-encoder a ONNX (primera carga)...")
        _export_to_onnx()
    else:
        log.info("Cargando cross-encoder ONNX desde cache...")

    from transformers import AutoTokenizer

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=str(MODEL_DIR))

    import onnxruntime

    opts = onnxruntime.SessionOptions()
    opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.intra_op_num_threads = 4
    _session = onnxruntime.InferenceSession(
        str(ONNX_PATH),
        sess_options=opts,
        providers=["CPUExecutionProvider"],
    )


def _export_to_onnx():
    from huggingface_hub import hf_hub_download
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.save_pretrained(str(MODEL_DIR))

    # Usar modelo ONNX pre-exportado optimizado para ARM64 si esta disponible
    onnx_remote = "onnx/model_qint8_arm64.onnx"
    try:
        onnx_path = hf_hub_download(
            repo_id=MODEL_NAME,
            filename=onnx_remote,
            local_dir=str(MODEL_DIR / "hf_onnx"),
            local_dir_use_symlinks=False,
        )
        import shutil

        shutil.copy(onnx_path, ONNX_PATH)
        log.info(f"Modelo ONNX ARM64 descargado a {ONNX_PATH}")
    except Exception:
        log.info("Fallback a modelo ONNX generico...")
        onnx_remote = "onnx/model.onnx"
        onnx_path = hf_hub_download(
            repo_id=MODEL_NAME,
            filename=onnx_remote,
            local_dir=str(MODEL_DIR / "hf_onnx"),
            local_dir_use_symlinks=False,
        )
        import shutil

        shutil.copy(onnx_path, ONNX_PATH)
        log.info(f"Modelo ONNX gen descargado a {ONNX_PATH}")

    import onnx

    onnx_model = onnx.load(str(ONNX_PATH))
    onnx.checker.check_model(onnx_model)
    log.info("Modelo ONNX valido")


def _tokenize(query: str, documents: list[str]) -> dict:
    _ensure_model()
    encoded = _tokenizer(
        [query] * len(documents),
        documents,
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="np",
    )
    if "token_type_ids" not in encoded:
        encoded["token_type_ids"] = np.zeros_like(encoded["input_ids"])
    return {k: v.astype(np.int64) for k, v in encoded.items() if k in ("input_ids", "attention_mask", "token_type_ids")}


def rerank(query: str, documents: list[str], scores: list[float] | None = None) -> list[dict]:
    if not documents:
        return []
    _ensure_model()
    inputs = _tokenize(query, documents)
    logits = _session.run(None, inputs)[0]
    cross_scores = 1.0 / (1.0 + np.exp(-logits[:, 0]))
    if scores is None:
        scores = [0.5] * len(documents)
    combined = []
    for i, doc in enumerate(documents):
        composite = COMPOSITE_ALPHA * float(cross_scores[i]) + (1 - COMPOSITE_ALPHA) * float(scores[i])
        combined.append(
            {
                "text": doc,
                "score_dense": float(scores[i]),
                "score_cross": float(cross_scores[i]),
                "score_composite": round(composite, 4),
                "rank": 0,
            },
        )
    combined.sort(key=lambda x: x["score_composite"], reverse=True)
    for i, item in enumerate(combined):
        item["rank"] = i
    return combined


def rerank_payloads(query: str, results: list[dict]) -> list[dict]:
    texts = [r.get("payload", r).get("texto", "") for r in results]
    scores = [r.get("score", 0.5) for r in results]
    reranked = rerank(query, texts, scores)
    output = []
    for i, item in enumerate(reranked):
        if i < len(results):
            entry = dict(results[i])
            if "payload" in entry:
                entry["payload"] = dict(entry["payload"])
            entry["score_dense"] = item["score_dense"]
            entry["score_cross"] = item["score_cross"]
            entry["score_composite"] = item["score_composite"]
            entry["rank"] = item["rank"]
            output.append(entry)
    return output
