# URA Assistant — Future Roadmap

**Author:** AI systems architect
**Date:** 2026-07-20
**Context:** Post-F29 stabilization, deployed on GX10 (port 8003), 19 active files, 130+ tests
**Baseline:** Bearer auth, SQLite persistence, es/en LLM, regex intent/sentiment, PromptSanitizer, StyleEngine wired
**Unresolved baseline issues:** token-by-token streaming, user identity, context dedup, output moderation, tool execution

---

## Phase Selection Criteria

Each phase is scored on three axes:
- **User value** — how much a real user benefits
- **Effort-to-impact ratio** — value delivered per engineering hour
- **Risk** — likelihood of introducing regressions or requiring rework

Phases are ordered by composite priority, not by sequence. Some can run in parallel.

---

## Phase A: Streaming & User Identity (Weeks 1–2)

### A1 — Real Token-by-Token Streaming

**What:** Replace the current facade (`generate_stream` returns a complete string wrapped in one SSE event) with genuine chunked generation from Ollama's `/api/generate` (stream=True), yielding individual tokens as SSE `data:` events.

**Why it matters:** Users perceive a 2-second-first-token latency as "fast" even if total generation takes 10s. A synchronous 10s wait feels broken. This is table stakes for any conversational AI in 2026.

**Implementation sketch:**
- Add `generate_stream` to `OllamaProvider` that yields chunks via httpx streaming
- Wire `StreamManager.stream_response()` into the API streaming path
- Send `event: token` for each chunk + `event: done` when complete
- Support cancellation via `asyncio.Task.cancel()` when client disconnects

| Item | Value |
|------|-------|
| Effort | 4–6h |
| Dependencies | OllamaProvider must support async iteration; HTTPX streaming |
| Risk | Medium — changes hot path, async error handling |
| User value | HIGH — perceived speed improvement 10x |
| Effort/impact | Excellent |

### A2 — User Identity Propagation

**What:** Add `user_id` to `ChatRequest`, propagate through `ConversationEngine` to all subsystems that need it (learning, episodic memory, proactive memory, corrective learning, implicit feedback).

**Why it matters:** Without this, every personalization subsystem is permanently dead. The system cannot distinguish between users, cannot learn preferences, cannot maintain per-user conversation history, cannot audit who said what.

| Item | Value |
|------|-------|
| Effort | 1–2h |
| Dependencies | Requires updaing MessageStore schema to include `user_id` |
| Risk | Low — additive change, all existing code continues to work with empty user_id |
| User value | CRITICAL — unlocks personalization, per-user memory, analytics |
| Effort/impact | Best in class |

### A3 — Output Content Moderation

**What:** Add `OutputSanitizer` (mirror of `PromptSanitizer`) that filters LLM responses for PII leakage, toxic content, prompt injection leakage, and hallucinated credentials before returning to the user.

**Why it matters:** The system has input protection but zero output protection. An LLM that generates code with embedded API keys, or that suddenly produces harmful content, has no safety net.

| Item | Value |
|------|-------|
| Effort | 2–3h |
| Dependencies | PromptSanitizer patterns can be reused with reversed polarity |
| Risk | Low — additive filter in the response pipeline |
| User value | HIGH — safety-critical for production |
| Effort/impact | Good |

---

## Phase B: Memory & Context (Weeks 2–4)

### B1 — Unify SQLite Databases

**What:** Merge the 5+ separate SQLite databases (`conversations.db`, `corrections.db`, `feedback.db`, `proactive.db`, `learning.db`) into a single SQLite file with separate tables. This enables atomic cross-subsystem transactions, simplifies backup, reduces page cache overhead.

**Why it matters:** Currently cleaning one database does not roll back related state in another. Backups must capture 5 files atomically. Each connection is a separate WAL. This is technical debt that grows with every new subsystem.

| Item | Value |
|------|-------|
| Effort | 4–6h |
| Dependencies | Migration script, schema consolidation, connection pooling |
| Risk | Medium — migration must not lose data; rollback path required |
| User value | LOW (invisible to users) — purely operational |
| Effort/impact | Low for users, high for operators |

### B2 — Vector Conversation Memory

**What:** Replace the current SQLite-based FTS/ token-overlap conversation search with a lightweight vector store (Qdrant already in the project) for semantic conversation retrieval. Store conversation embeddings on each turn; retrieve semantically similar past conversations when building context.

**Why it matters:** "Recuérdame qué hablamos sobre X" currently does naive keyword matching. Vector retrieval would find conceptually related conversations even when keywords don't overlap — the difference between "remember what we said about deployment" finding a conversation about "putting things in production" vs. finding nothing.

**Implementation sketch:**
- Generate embeddings for each conversation via `nomic-embed-text` (already deployed)
- Store in a dedicated Qdrant collection
- On context assembly, query top-3 semantically similar conversations
- Hybrid score: vector similarity + recency boost

| Item | Value |
|------|-------|
| Effort | 8–12h |
| Dependencies | Qdrant must be available; embedding model must be loaded |
| Risk | Medium — changes context assembly, could degrade response quality if retrieval is noisy |
| User value | HIGH — conversations feel coherent across sessions |
| Effort/impact | Good |

### B3 — Context Deduplication Fix

**What:** Replace `id(m)`-based deduplication (broken — Python object identity never matches across SQLite `fetchall` calls) with a proper dedup by `(content, role, timestamp)` tuple.

**Why it matters:** Every response currently includes duplicate messages in context, wasting ~20–30% of the token budget. For deep reasoning models (32B+) at $ per token, this is measurable cost. For response quality, it dilutes the signal-to-noise ratio.

| Item | Value |
|------|-------|
| Effort | 15 min |
| Dependencies | None |
| Risk | Very Low |
| User value | LOW-MEDIUM (improves token efficiency, reduces cost) |
| Effort/impact | Trivially worth doing |

### B4 — Episodic Memory Eviction

**What:** Add TTL-based eviction and summary consolidation to `episodic_memory.py`. Currently summaries accumulate forever. Add: max count (500), TTL (30 days), summary-of-summaries for old entries.

| Item | Value |
|------|-------|
| Effort | 1–2h |
| Dependencies | None |
| Risk | Low |
| User value | Low (prevents unbounded growth, stabilizes memory) |
| Effort/impact | Good — prevents production incident |

---

## Phase C: Web & Tools (Weeks 3–6)

### C1 — Web Search Integration

**What:** Wire a real web search capability. When `trends.py` detects a time-sensitive query or `intent.py` detects a search intent, call a search API (DuckDuckGo, or preferably a self-hosted SearXNG instance) and inject results into the LLM context.

**Why it matters:** The single most common failure mode of LLMs is outdated knowledge. Users asking "what's the latest version of Python" get wrong answers. Web search is the highest-impact reliability improvement.

**Implementation sketch:**
- Add `WebSearchIntegration` (was removed in the dead code cleanup but should be reimplemented properly)
- Rate-limit to 10 queries/hour per user
- Cache identical queries for 15 minutes
- Inject results as a tool-call-style context block: `[Web: Python 3.14 released June 2026]`

| Item | Value |
|------|-------|
| Effort | 4–8h |
| Dependencies | Search API key or self-hosted SearXNG; rate limit infrastructure |
| Risk | Low — additive, graceful degradation on API failure |
| User value | VERY HIGH — solves the knowledge-cutoff problem |
| Effort/impact | Excellent |

### C2 — Tool Execution Framework

**What:** Implement a controlled tool execution system. Start with read-only tools (file read, git log, system info), then add write tools with confirmation gates. Each tool requires explicit user approval before execution.

**Why it matters:** "URA, ¿cuántos archivos hay en mi proyecto?" or "URA, muéstrame el git log" are natural questions that the LLM currently invents answers for. Actual tool execution turns the assistant from a chatbot into a useful work tool.

**Safety architecture:**
- Tool registry with explicit allowlist per user
- Read tools auto-execute; write tools require `tool_confirmation.py`
- Sandboxed execution via subprocess with timeout and resource limits
- All tool calls logged with full input/output for audit

| Item | Value |
|------|-------|
| Effort | 8–12h |
| Dependencies | Phase A2 (user identity) for per-user allowlists; empty `tools/` dir needs populating |
| Risk | HIGH — tool execution is the highest-risk feature (RCE by design) |
| User value | HIGH — transforms assistant from chatbot to work tool |
| Effort/impact | Good if done safely |

### C3 — Source Citation

**What:** When the LLM retrieves information from any source (web search, vector memory, knowledge base), include inline citations in the response. Users see `[1]` markers with a citations object at the end.

**Why it matters:** Without citations, users cannot distinguish between "URA knows this" and "URA guessed this". Citations build trust, enable verification, and reduce hallucination impact.

| Item | Value |
|------|-------|
| Effort | 2–4h |
| Dependencies | C1 (web search), B2 (vector memory) |
| Risk | Low — additive, structured metadata |
| User value | HIGH — trust and verifiability |
| Effort/impact | Good |

---

## Phase D: Advanced Intelligence (Weeks 5–10)

### D1 — Advanced RAG / Knowledge Base

**What:** Connect the assistant to URA's existing Knowledge Engine (Fases 0–6, FTS5, Qdrant vector store). When the user asks a factual question, retrieve relevant document fragments from the knowledge base, rerank, and inject as context.

**Why it matters:** The project has invested heavily in knowledge ingestion (146 scripts, pipelines, vectorization). The assistant should be the primary consumer of this knowledge. Currently the knowledge engine exists but the assistant never queries it.

**Implementation sketch:**
- Add `KnowledgeRetriever` that calls `knowledge.engine` APIs
- Hybrid search (FTS5 + vector) with configurable top-k
- Inject results as context blocks with citations
- Cache results to avoid repeated vector queries

| Item | Value |
|------|-------|
| Effort | 10–16h |
| Dependencies | Knowledge Engine must expose a simple query API; embedding model must be loaded |
| Risk | Medium — noisy retrieval degrades response quality; tuning required |
| User value | VERY HIGH — turns URA into an expert on its own codebase |
| Effort/impact | Good (high value, high effort) |

### D2 — Intent Classification Upgrade

**What:** Replace or augment the regex-based `intent.py` with a lightweight classifier. Options:
- Distilled BERT (fastest, ~5ms inference)
- Few-shot LLM classification via `qwen2.5:7b` (most flexible, ~500ms)
- Regex as fast-path + LLM as fallback for ambiguous cases (hybrid)

**Why it matters:** Regex intent detection has ~70% accuracy on edge cases. Users saying "could you help me understand..." (question) vs. "help me write code" (command) are often misclassified. Better intent detection unlocks better mode selection, tool routing, and response quality.

| Item | Value |
|------|-------|
| Effort | 4–8h |
| Dependencies | LLM endpoint or classifier model |
| Risk | Low — additive, existing regex stays as fallback |
| User value | MEDIUM — improves response relevance |
| Effort/impact | Good |

### D3 — Preference Learning (Real)

**What:** Make `ConversationalLearning` actually work. With user identity (A2), track implicit signals (correction frequency, rephrase rate, response acceptance, mode overrides) and explicit signals (thumbs up/down, "más corto" requests). Build a per-user preference profile that adjusts response length, formality, technical depth, and verbosity.

**Why it matters:** The single biggest differentiator between a generic chatbot and a personal assistant is adaptation. A system that learns "this user prefers short answers with code examples" vs. "this user wants detailed explanations" feels intelligent. Without it, every interaction starts from zero.

| Item | Value |
|------|-------|
| Effort | 6–10h |
| Dependencies | Phase A2 (user identity), implicit_feedback.py already has the signal collection |
| Risk | Low-Medium — preferences can be wrong; need reset mechanism |
| User value | HIGH — personalization is the core promise of "assistant" vs "chatbot" |
| Effort/impact | Good |

---

## Phase E: Voice & Multi-Modal (Weeks 8–14)

### E1 — Speech-to-Text Integration

**What:** Add a `/api/v1/chat/voice` endpoint that accepts audio (WAV/MP3), transcribes it via Whisper (already deployed on GX10 for URA Voice), and processes the resulting text through the normal conversation pipeline.

**Why it matters:** Voice is the primary input modality for hands-free use. GX10 already runs Whisper + Piper TTS for URA Voice. The assistant is already on the same machine — the integration path exists but was never built.

**Implementation sketch:**
- Accept `multipart/form-data` with audio file
- Call Whisper via subprocess or the running Whisper service
- Use existing `chat` pipeline with the transcribed text
- Return transcribed text + reply (for the client to handle TTS)

| Item | Value |
|------|-------|
| Effort | 3–5h |
| Dependencies | Whisper must be accessible (already deployed); audio format handling |
| Risk | Low — standalone endpoint, no changes to existing chat flow |
| User value | MEDIUM-HIGH — voice is transformative for mobile/ hands-free |
| Effort/impact | Excellent (leverages existing infrastructure) |

### E2 — Text-to-Speech Integration

**What:** Add a `tts` flag to `ChatRequest`. When true, include the response audio (MP3/Opus) alongside the text reply. Use Piper TTS (already deployed) or a streaming TTS approach.

**Why it matters:** Voice output completes the voice loop. Without it, voice input requires separate client-side TTS.

| Item | Value |
|------|-------|
| Effort | 3–5h |
| Dependencies | Piper TTS (already deployed on GX10); audio streaming to client |
| Risk | Low — standalone feature |
| User value | MEDIUM — completes voice I/O |
| Effort/impact | Good |

### E3 — Multi-Modal (Image Understanding)

**What:** Accept image attachments in chat requests. Route to a vision-capable model (llama3.2-vision:11b or qwen2-vl, already deployed on GX10). Enable questions about images: "¿Qué hay en esta foto?", "Describe este diagrama".

**Why it matters:** Image understanding is the single most requested feature after web search. Users want to upload screenshots of errors, photos of objects, diagrams from documentation.

| Item | Value |
|------|-------|
| Effort | 6–10h |
| Dependencies | Vision model in Ollama (already deployed); image preprocessing; multimodal prompt format |
| Risk | Medium — vision models are slower, context window management is different |
| User value | VERY HIGH — unlocks screenshot analysis, visual Q&A |
| Effort/impact | Good (leverages deployed models) |

### E4 — Multi-Modal (Image Generation)

**What:** When the user asks "draw / generate an image of...", route to a diffusion model (Stable Diffusion via Ollama or external API) and return the image URL/base64.

**Why it matters:** Image generation is visually impressive but lower practical utility than image understanding. Users ask for it frequently but actual use cases are limited.

| Item | Value |
|------|-------|
| Effort | 4–8h |
| Dependencies | Diffusion model or API; image storage; async generation queue |
| Risk | Medium — slow generation ties up resources; expensive |
| User value | MEDIUM — cool, intermittent use |
| Effort/impact | Fair — more "cool" than "useful" |

---

## Phase F: Quality & Operations (Weeks 6–12, parallel)

### F1 — Evaluation Framework

**What:** Build an automated conversation quality testing system. Define a corpus of 50–100 representative queries across all intents and modes. For each query, define expected behaviors (not exact strings). Run the full pipeline against a fixed LLM version and score: response time, refusal rate, hallucination markers, citation accuracy, language consistency.

**Why it matters:** There is currently no way to know whether a code change improves or degrades response quality. Manual testing finds the obvious bugs. An eval framework catches regressions in tone, accuracy, and behavior.

**Implementation sketch:**
- YAML corpus with query + expected behaviors (assertions)
- Run pipeline (minus auth/rate-limit) against eval corpus
- Assertions: `response_contains`, `response_not_contains`, `latency_under`, `language_matches`, `no_refusal_patterns`
- Track deltas from baseline on every deploy

| Item | Value |
|------|-------|
| Effort | 10–16h |
| Dependencies | Deterministic LLM routing (same model, same params); corpus curation |
| Risk | Low — auxiliary tool, no production impact |
| User value | INDIRECT — improves quality of all other phases |
| Effort/impact | High ROI — prevents regression in every future change |

### F2 — Analytics Dashboard

**What:** Expose conversation metrics via a `/api/v1/chat/metrics` endpoint and optionally a web dashboard: queries/day, active users, average latency, intent distribution, language distribution, error rate, top topics, satisfaction proxy (rephrase rate, correction rate).

**Why it matters:** Without metrics, the team operates blind. Is the system getting better or worse? Which intents are failing? Which users are churning?

| Item | Value |
|------|-------|
| Effort | 6–10h |
| Dependencies | User identity (A2) for per-user metrics; structured logging for event collection |
| Risk | Low — read-only endpoint |
| User value | LOW (operators, not end users) |
| Effort/impact | Good — essential for operational maturity |

### F3 — Asynchronous / Background Processing

**What:** Move non-critical processing (episodic memory summarization, trend analysis, preference learning, implicit feedback batch analysis) out of the sync hot path into a background task queue. Use `asyncio.create_task` or a simple in-process queue.

**Why it matters:** `process_user_message()` currently orchestrates 13 subsystems synchronously. Even with `to_thread`, each one adds latency. Background processing keeps response times under 100ms for everything except the LLM call.

| Item | Value |
|------|-------|
| Effort | 6–8h |
| Dependencies | Understanding of which subsystems are latency-critical vs. deferrable |
| Risk | Medium — state consistency; deferred processing must not lose events |
| User value | MEDIUM — faster responses, lower p95 latency |
| Effort/impact | Good |

---

## Phase G: Scale & Isolation (Months 3–6)

### G1 — Multi-Tenant Isolation

**What:** Full tenant isolation with separate databases, separate embedding spaces, separate conversation stores per tenant. Tenant identified via API key or JWT claim.

**Why it matters:** If URA serves multiple teams or clients, isolation is non-negotiable. Currently everything is global.

| Item | Value |
|------|-------|
| Effort | 12–20h |
| Dependencies | Phase A2 (user identity); Phase B1 (single DB per tenant or partitioned tables) |
| Risk | HIGH — data isolation boundaries must be perfect |
| User value | LOW (only if multi-tenant deployment is needed) |
| Effort/impact | Depends on business model |

### G2 — Web / Mobile UI

**What:** Build a minimal web chat UI (React, Svelte, or plain HTML/JS) and/or a mobile wrapper. Display streaming responses, mode selector, conversation history sidebar, settings panel.

**Why it matters:** The API is useless without a client. Currently users must use curl, OpenCode, or a custom integration. A web UI makes the assistant accessible to non-technical users.

| Item | Value |
|------|-------|
| Effort | 20–40h (full UI) |
| Dependencies | Phase A1 (real streaming) is essential for good UX |
| Risk | Low-Medium — no backend changes |
| User value | VERY HIGH — makes the system accessible |
| Effort/impact | Depends on UI sophistication; a minimal "Open Web UI" clone is ~20h |

### G3 — Plugin System (Tool/MCP)

**What:** Formalize the plugin/tool system so third parties can register new capabilities without modifying core code. Each plugin declares: trigger patterns, required permissions, execution sandbox. Use the project's existing `PluginRegistry` from Fase 11.

**Why it matters:** The project already has `PluginRegistry`, `plugin.yaml` manifest format, and EventBus. The assistant is a natural consumer. A plugin for "search Jira tickets" or "query PostgreSQL" or "check server health" extends URA from chatbot to platform.

| Item | Value |
|------|-------|
| Effort | 16–24h |
| Dependencies | Phase C2 (tool execution); Fase 11 PluginRegistry |
| Risk | HIGH — third-party code execution; sandboxing required |
| User value | MEDIUM — powerful but niche (platform play) |
| Effort/impact | Fair — high effort, delayed value |

### G4 — Continuous Learning (RLHF Lite)

**What:** Implement a lightweight preference learning loop. Collect implicit feedback signals (rephrase, correction, abandonment) and explicit feedback (thumbs, corrections). Periodically fine-tune a LoRA adapter on the LLM using preference pairs.

**Why it matters:** The system gets better over time without manual prompt engineering. This is the closest thing to "self-improving AI" that is practical today.

**Implementation sketch:**
- Collect preference pairs: (good_response, bad_response) from implicit/explicit signals
- Store in SQLite preference database
- Weekly batch: run DPO or preference optimization on a small LoRA adapter
- Swap adapter in the model router

| Item | Value |
|------|-------|
| Effort | 20–30h |
| Dependencies | Phase D3 (preference learning); LoRA infrastructure; significant ML expertise |
| Risk | HIGH — bad training data degrades quality; requires monitoring and rollback |
| User value | MEDIUM-HIGH — system improves autonomously |
| Effort/impact | Fair — high effort, high risk, but transformative if it works |

---

## Summary Roadmap

```
WEEK 1-2      WEEK 3-4      WEEK 5-8      WEEK 8-12     MONTH 3-6
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ A1 Stream│   │ B1 DB    │   │ C1 Web  │   │ E1 STT  │   │ G1 Multi │
│ A2 UserID│   │   Unify  │   │  Search │   │ E2 TTS  │   │  Tenant  │
│ A3 Output│   │ B2 Vector│   │ C2 Tools│   │ E3 Vision│   │ G2 UI    │
│   Mod    │   │  Memory  │   │ C3 Cit  │   │ E4 Gen   │   │ G3 Plugin│
└─────────┘   │ B3 Dedup │   │   ation │   └─────────┘   │   System  │
              │ B4 Evict │   └─────────┘   ┌─────────┐   │ G4 RLHF  │
              └─────────┘   ┌─────────┐   │ F1 Eval  │   └─────────┘
                            │ D1 RAG  │   │   Frame  │
                            │ D2 Intent│   │ F2 Dash  │
                            │ D3 Pref │   │   board  │
                            │   Learn  │   │ F3 Async │
                            └─────────┘   │   Proc   │
                                           └─────────┘
```

### Parallelization Strategy

| Track | Phases | Est. Effort | Team |
|-------|--------|-------------|------|
| Core UX | A1, A2, A3, B3, B4 | ~10h | 1 dev |
| Intelligence | B2, C1, C3, D1, D2, D3 | ~40h | 1-2 devs |
| Voice/Vision | E1, E2, E3, E4 | ~20h | 1 dev |
| Quality | F1, F2, F3 | ~24h | 1 dev |
| Scale | G1, G2, G3, G4 | ~80h | 2 devs |

Tracks are independent and can run in parallel with up to 3 devs.

---

## What NOT to Do (Honest Assessment)

These items are **genuinely cool but low-priority** relative to the above:

| Feature | Why Not Now |
|---------|-------------|
| **Real-time multi-user chatrooms** | URA is a personal assistant, not a chat platform. Zero demand signal. |
| **Blockchain / decentralized memory** | No practical use case. Adds complexity without user benefit. |
| **Custom fine-tuned base model** | Requires expensive GPU time, data curation, MLOps. LoRA/RAG achieves 80% of the value at 5% of the cost. |
| **3D avatar / digital human** | Visually impressive, zero utility for the current use case. |
| **Autonomous agent loops** | The F27 AgentOrchestrator exists but the assistant is a conversational interface, not an autonomous agent. Mixing paradigms creates confusing UX. |
| **Blockchain auth / DIDs** | Overengineered. Bearer token + JWT is sufficient for the deployment scale. |

---

## Recommended Priority (If You Can Only Do 5 Things)

1. **Real streaming** — biggest UX improvement per engineering hour
2. **User identity** — unlocks everything else (personalization, analytics, multi-tenant)
3. **Web search** — solves knowledge cutoff, highest reliability improvement
4. **Output moderation** — safety requirement for production
5. **RAG / Knowledge base** — leverages URA's biggest investment

These 5 capabilities deliver ~80% of the user value with ~20% of the total estimated effort.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Streaming introduces async bugs | Medium | High — broken responses | Staged rollout, canary endpoint |
| Vector memory retrieves irrelevant context | Medium | Medium — degrades quality | Score threshold, fallback to SQLite |
| Tool execution enables RCE | Low | Critical | Read-only by default, confirmation gate for writes, sandboxing |
| RLHF degrades quality | Medium | High — hard to detect | A/B test every adapter, automated eval before deploy |
| Multi-tenant data leak | Low | Critical | Independent DBs per tenant, strict boundary tests |
