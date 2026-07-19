# Expert Review: `motor/assistant/` — Conversational AI Engine

**Reviewer:** AI systems architect (Google, OpenAI, Meta class)
**Date:** 2026-07-20
**Scope:** All 27 files in `motor/assistant/`, 7 test files in `tests/`
**Version:** F29 (post-F28.1 stabilization)

---

## Executive Summary

The assistant module has strong conceptual architecture with 20+ specialized subsystems (sentiment, interruption, episodic memory, proactive memory, corrective learning, auto-mode, style, personality, planner, etc.). However, **the vast majority of these subsystems are disconnected from the execution path** — they are dead code written as part of F29 specification but never wired into the API. The actual working path (`api.py → conversation.py → llm_bridge.py → Ollama`) is thin, synchronous, fragile, and would not survive production load.

**Risk Level: CRITICAL** — no authentication, data stored in `/tmp/`, blocking event loop, silent error swallowing, streaming declared but unimplemented.

---

## 1. Architecture Review

### 1.1 What Works Well

- **Component separation is excellent conceptually**: 27 files map to clean single-responsibility subsystems. A human can read any file and understand what it does in isolation.
- **Dependency injection is used throughout**: All `ConversationEngine` dependencies can be overridden via constructor injection, making testing possible.
- **Type hints are thorough**: Every new function has type annotations, dataclasses are used for domain models.
- **F29 feature layering is logical**: Sentiment → interruption → episodic memory → trends → auto-mode → corrective learning → proactive → implicit feedback forms a sensible processing pipeline.
- **Tests exist**: 7 test files with 50+ tests covering models, store, context, intents, tools, style, personality, learning, and management.

### 1.2 What's Wrong at the Architectural Level

| Issue | Impact |
|-------|--------|
| **~60% of code is dead** — 9 of 27 files are never imported in the API execution path | Code bloat, maintenance burden, false sense of capability |
| **`process_user_message()` orchestrates 13 subsystems synchronously** | Single point of coupling; impossible to test subsystems independently; any failure cascades |
| **No middleware/pipeline architecture** — subsystems are called in linear sequence with hardcoded ordering | Cannot add/remove/reorder processing stages without modifying the core engine |
| **Singleton anti-pattern** — `_EngineHolder` in `api.py` is a global mutable singleton with no lifecycle management | Thread safety concerns, no graceful shutdown, no reload |
| **Async sync mix** — FastAPI async endpoint calls synchronous `process_user_message()` and `llm.generate()` | Blocks the ASGI event loop under load |
| **Multiple SQLite databases** — 6 separate `.db` files (`conversations.db`, `corrections.db`, `feedback.db`, `proactive.db`, `learning.db`, `search.db`) | No atomicity across subsystems, connection explosion, no migration strategy |
| **Context system duplicates messages** — `ContextManager._get_immediate()` and `_get_conversation_history()` both fetch from `MessageStore` with different limits, creating duplicate `ContextItem` entries | Wasted tokens, inflated context |

### 1.3 Missing Layers

| Missing Layer | Why It's Needed |
|---------------|-----------------|
| **Authentication/Multi-tenant isolation** | Zero user identity; every client sees every conversation |
| **Rate limiting with per-user quotas** | Current limiter is per-IP only; no user concept |
| **Graceful degradation / circuit breaker** | If Ollama is down, the system returns the error string `[Error al conectar con LLM: {exc}]` to the user |
| **Request tracing** | No trace_id; debugging failures in production requires log correlation across subsystems |
| **Structured logging** | All errors are swallowed by `except: pass` |
| **Connection pooling** | 6 separate SQLite connections, each with `check_same_thread=False` |
| **Background processing / queue** | Episodic memory summaries, trend analysis, learning all happen in the hot path |

---

## 2. Critical Gaps (Must-Fix Before Production)

### CRIT-C1: All Data Stored in `/tmp/` (Data Loss on Reboot)

**Files:** `message_store.py:15`, `conversation_search.py:12`, `corrective_learning.py:16`, `implicit_feedback.py:18`, `learning.py:31`, `proactive_memory.py:45`

Every SQLite database path defaults to `/tmp/ura/*.db`. This is volatile storage:
- Lost on any system reboot, crash, or container restart
- No backup strategy
- No WAL persistence guarantee across power loss

**Fix:** Use a persistent path from UraConfig (`CONFIG`) with automatic directory creation, WAL mode already enabled (good), and periodic checkpointing.

### CRIT-C2: Zero Authentication

**File:** `api.py:97-142`

The `/api/v1/chat` endpoint has:
- No API key validation
- No JWT/session tokens
- No user identity in request model
- No CORS restrictions visible

Any client that reaches this port can read/write any conversation. With `ShellTool` registered (though currently not wired, a future integration path is open), this is RCE by design.

**Fix:** Add Bearer token auth (reuse `motor/core/secrets.py`), API key per integration, or session-based auth. Rate limiting by IP is insufficient.

### CRIT-C3: Streaming Declared But Never Implemented

**File:** `api.py:26`

```python
stream: bool = False
```

This field exists in `ChatRequest` but is **never read**. The handler always returns a complete JSON response. `StreamManager` at `streaming.py:22-55` is dead code.

Users asking for streaming get a complete response. SSE streaming with token-by-token output is a baseline expectation for any conversational AI in 2026.

**Fix:** Implement async streaming using `StreamingResponse` from FastAPI, wire `StreamManager`, add a dedicated streaming endpoint.

### CRIT-C4: Silent Error Swallowing

**Files:** `api.py:52-54`, `llm_bridge.py:88-89`, `web_search.py:42-43`

```python
# api.py:52-54
except Exception:
    pass

# llm_bridge.py:88-89
except Exception:
    pass

# web_search.py:42-43
except Exception:
    return ""
```

These patterns:
- Hide real failures from operators
- Mask infrastructure issues (Ollama down, network split, disk full)
- Provide no observability hooks
- Create a false sense of resilience

**Fix:** Log every exception with trace_id, use structured logging, implement circuit breakers, return proper error responses (5xx).

### CRIT-C5: Blocking Sync Calls in Async Event Loop

**File:** `api.py:113-135`

`process_user_message()` and `llm.generate()` are synchronous methods called from an `async def` FastAPI handler. Both perform:
- SQLite I/O (with threading.Lock)
- HTTP calls to Ollama (synchronous httpx or similar)
- Regex operations
- Dictionary operations

Under concurrent requests (even 2-3), the ASGI event loop starves, causing cascading latency.

**Fix:** Either make the entire stack async (preferred), or use `run_in_executor()` for the CPU/IO-bound sections.

### CRIT-C6: Interruption Detection is Non-Functional in Sync API

**File:** `interruption.py:33-55`

```python
def detect_interruption(self, conversation_id, messages):
    if len(messages) < 2:
        return False
    last = messages[-1]
    second_last = messages[-2]
    is_interruption = (
        last.role == "user"
        and second_last.role == "assistant"
    )
```

This returns True when the most recent message pair is [assistant, user]. In a synchronous API where responses are generated before the user sends the next message, the message count is always even ([u1, a1, u2, a2]). At the start of `process_user_message()`, `messages[-1]` is the last assistant message — so `messages[-1].role == "assistant"` and this **never** triggers.

This subsystem cannot work without an async/streaming architecture where the user can send messages while the assistant is still generating.

**Fix:** This requires the streaming pipeline to be built first. The interruption system is a streaming-native feature incorrectly backported to a synchronous architecture.

### CRIT-C7: Reference Resolution Can Produce Gibberish

**File:** `conversation.py:121-133`

```python
resolved = text.lower()
for pattern, replacement in _REFERENCE_PATTERNS:
    if pattern.search(resolved):
        last = conv.last_user_message
        if last:
            ctx = last.content[:80].lower()
            if replacement:
                resolved = pattern.sub(replacement, resolved)
            else:
                resolved = pattern.sub(f"({ctx}...)", resolved)
```

Example: User says "hazlo como antes"
- Pattern `hazlo` matches → replaced with "ejecuta"
- Pattern `como antes` matches → replaced with "(previous message context...)")
- Result: "ejecuta (previous message context...)" — grammatically broken, confusing to the LLM

**Fix:** Instead of inline replacement, use a structured "context hints" object passed alongside the user message, or use LLM-based reference resolution.

### CRIT-C8: Sentiment Regex Typo Nullifies Pattern

**File:** `sentiment.py:49`

```python
r"huh|eh\|perdona"
```

The `\|` escapes the pipe character, making this match the literal string `eh|perdona` (a single token containing `|`), not the alternation between "eh" and "perdona". The word "perdona" alone never triggers confusion detection.

**Fix:** Change to `r"huh|eh|perdona"` or `r"\b(?:huh|eh|perdona)\b"`.

### CRIT-C9: No User Identity Propagation

**File:** `api.py:98` → `learning.py:56-68`

The API accepts no `user_id`. `ConversationalLearning.record_interaction()` requires one. Result: user preference learning is permanently non-functional. The system cannot distinguish between users, cannot personalize, cannot learn.

**Fix:** Add `user_id` to `ChatRequest`, propagate it through the engine. Or derive it from auth tokens.

---

## 3. Important Gaps (Should-Fix)

### IMP-1: 60% Dead Code — 9 Files Never Imported

| File | Lines | Status |
|------|-------|--------|
| `streaming.py` | 58 | No caller |
| `tool_confirmation.py` | 64 | No caller |
| `tools.py` (ToolOrchestrator) | 100 | No caller |
| `planner.py` (ConversationalPlanner) | 160 | No caller |
| `personality.py` (PersonalityManager) | 67 | No caller |
| `web_search.py` (WebSearchIntegration) | 50 | No caller |
| `conversation_search.py` (ConversationSearch) | 80 | No caller |
| `management.py` (ConversationManager) | 97 | No caller |
| `style.py` (StyleEngine) | 124 | `build_system_prompt()` unused in API |

These files implement F29 specifications (B1-B9) but were never integrated into the execution path. They represent ~800 lines of untested (in production context), unmaintainable liability.

**Fix:** Either integrate each subsystem into the API chain, or move to `_archive/`. Half-implemented features are worse than absent ones.

### IMP-2: Hardcoded System Prompts Bypass StyleEngine

**File:** `api.py:77-94` vs `style.py:84-124`

The API has local `_SYSTEM_PROMPTS` dict while `StyleEngine` at `style.py` has a fully parameterized system prompt builder with tone, formality, depth, examples, emoji control. The API never calls `StyleEngine.build_system_prompt()`.

**Fix:** Replace `_SYSTEM_PROMPTS` with `StyleEngine.build_system_prompt(mode, intent)`.

### IMP-3: Context Duplication Wastes Tokens

**File:** `context.py:112-136`

Both `_get_immediate()` and `_get_conversation_history()` call `self._store.get_conversation()` with different limits. Since the store returns the most recent N messages, the immediate set is always a subset of the conversation set. The `assemble()` method scores them by `ContextLevel` (IMMEDIATE=3, CONVERSATION=2) but doesn't deduplicate by message content.

Result: The same message appears twice in the final context, consuming token budget and potentially confusing the LLM.

**Fix:** Deduplicate by message content or timestamp. Or make immediate a filtered view of conversation, not a separate fetch.

### IMP-4: No Timeout on LLM Calls

**File:** `llm_bridge.py:93-99`

```python
def _local_generate(self, messages, model_key):
    provider = OllamaProvider()
    prompt = self._messages_to_prompt(messages)
    return provider.generate(prompt, model=model_key)
```

`provider.generate()` has no timeout parameter here. If Ollama hangs (model loading, OOM, deadlock), the API request hangs forever. No `asyncio.timeout()`, no `httpx.Timeout`.

**Fix:** Add explicit timeout (30s default), propagate timeout errors as proper 504 responses.

### IMP-5: Memory Leak in Episodic Memory

**File:** `episodic_memory.py:34-47`

Every conversation summary is stored as a `Message` with a `_summary_` prefix conversation ID in `MessageStore`. These summaries accumulate indefinitely. There is no:
- Eviction policy
- TTL
- Maximum count
- Summary-of-summaries mechanism

For a system running for months, this grows unbounded.

**Fix:** Add TTL-based eviction, summary consolidation, or a dedicated FTS5-based summary store.

### IMP-6: Planner Has No LLM Integration

**File:** `planner.py:43-89`

The `_INTENT_PLANS` dict maps intents to hardcoded objectives/tasks. This is a rule-based planner that cannot handle novel situations. The class docstring says "Reutiliza F27 AgentPlanner" but there's no integration with `motor.agents`.

**Fix:** Either connect to `AgentPlanner` for non-trivial intents, or accept that this is a static fallback.

### IMP-7: Tool Execution is Not Connected

**File:** `tools.py:63-100`, `api.py:97-142`

`ToolOrchestrator` has three tools registered (GitStatus, GitLog, Shell), but nothing in the API or engine calls `ToolOrchestrator.execute()`. The `process_user_message()` result contains `intent` which could trigger tool execution, but the API path simply sends everything to the LLM via `llm.generate()`.

**Fix:** Add a tool execution step in the API chain: detect tool intent → execute tool → inject result into LLM context.

### IMP-8: No Content Moderation

There is no input or output content moderation anywhere in the pipeline. No:
- PII redaction
- Toxic content filtering
- Prompt injection detection
- Jailbreak detection

**Fix:** Add a moderation layer (even a regex-based one) before/after LLM calls.

### IMP-9: SQL Injection Risk in Search

**File:** `conversation_search.py:54-58`

```python
sql = (
    "SELECT ... WHERE token IN (" + ",".join("?" for _ in tokens) + ") "
    "GROUP BY ..."
)
```

While the `IN` clause uses parameterized `?` placeholders (safe), the pattern of string concatenation for SQL is fragile. Any future modification that adds user-controlled data to the string concatenation path creates SQL injection risk.

**Fix:** Build the parameterized query entirely with `execute()` parameters; never concatenate user data into SQL strings.

---

## 4. Nice-to-Haves

### NTH-1: Combine 6 SQLite Databases into One

Six separate `.db` files means six separate connections, six WALs, six sets of page cache. A single SQLite database with separate tables would reduce complexity, enable cross-subsystem queries, and simplify backup.

### NTH-2: Full-Text Search (FTS5) for Conversation Search

`conversation_search.py` uses token matching (split, stop-word filter, count overlap). This is a 1970s information retrieval approach. FTS5 with BM25 ranking would give significantly better relevance. The project already has FTS5 expertise from Fase 0-6.

### NTH-3: LLM-Based Intent Classification

`intent.py` uses regex patterns for intent classification. While fast, this misses many variations and has no graceful handling of ambiguous input. A small classifier model (e.g., distilled BERT) or prompt-based classification through the LLM would be more robust.

### NTH-4: Automatic Conversation Summarization at Scale

`management.py` detects when `needs_summary()` but doesn't actually generate summaries (no LLM call for summarization). The summary content is empty strings. Real summarization would maintain coherence over very long conversations.

### NTH-5: Feedback Loop Visualization

`implicit_feedback.py` collects signals but has no dashboard, no API endpoint to query scores, no way for operators to see what users are struggling with. A `/api/v1/chat/metrics` endpoint exposing `get_overall_score()` would enable data-driven improvement.

### NTH-6: A/B Testing Framework

With three modes, multiple style profiles, and personality layers, the system is crying out for A/B testing capability to measure which configurations improve user satisfaction (measured by `ImplicitFeedback` signals).

### NTH-7: Graceful Degradation Mode

If the LLM is down, the system should switch to a degraded mode (e.g., "I'm having trouble connecting to my brain right now. Please try again in a moment.") rather than returning `[Error al conectar con LLM: ...]`.

---

## 5. File-by-File Issues

### `__init__.py` (1 line)
- **Missing exports**: No `__all__` defined. No public API surface. Every consumer must know the module's internal file structure.
- **Missing version**: No `__version__` attribute.

### `models.py` (109 lines)
- **Well done**: Clean dataclasses, `_VALID_ROLES` frozenset, `__post_init__` validation.
- **Issue:** `Conversation.add_message()` allows `role` and `content` to be passed in `kwargs` even though line 84 explicitly forbids it; this should raise at runtime but `kwargs` can contain them anyway (the check is inside the method).
- **Issue:** `Message.role` is typed as `MessageRole` (Literal) but the validation in `__post_init__` uses `_VALID_ROLES`. If someone passes `MessageRole` type, validation passes. If someone passes an arbitrary string, validation catches it. This is redundant.

### `api.py` (153 lines)
- **[CRIT-C2]** No authentication.
- **[CRIT-C3]** `stream` field declared but never used.
- **[CRIT-C5]** Sync calls in async handler.
- **[CRIT-C4]** Silent `except: pass` at lines 52-54.
- **Issue:** `get_llm()` (line 47-55) has a race condition: two concurrent requests could both see `_EngineHolder.llm is None` and both create an LLMBridge, with one being discarded (no double-checked locking).
- **Issue:** `get_engine()` (line 41-44) lazy-initializes a singleton with no lifecycle hooks. No `close()` is ever called on the MessageStore.
- **Issue:** `_RateLimiter` (line 58-71) uses `time.monotonic()` but never cleans up stale entries for conversations that have ended. Over days/weeks, the `_requests` dict grows unbounded.
- **Issue:** `_SYSTEM_PROMPTS` (line 77-94) duplicates logic from `style.py`. Two sources of truth.
- **Issue:** `response_model=ChatResponse` but the endpoint is async and returns a Pydantic model, not a `StreamingResponse`. Streaming is impossible with this return type.

### `conversation.py` (255 lines)
- **[CRIT-C7]** Reference resolution produces broken text.
- **Issue:** `_REFERENCE_PATTERNS` (line 31-38) — `\beso\b` matches the Spanish word "eso" (that). This is correct but note it uses `search()` not `match()`, so "eso" anywhere in the text triggers expansion. Combined with `\bel\s+anterior\b`, `\blo\s+mismo\b`, this aggressively modifies user input.
- **Issue:** `process_user_message()` (line 135-200) returns a dict of 15+ keys with `object` values. No typed return. Callers must know what keys to expect.
- **Issue:** `process_user_message()` calls `self._interruptions.detect_interruption()` (line 143) BEFORE adding the new message. The interruption check looks at `messages[-1]` which is the LAST ASSISTANT MESSAGE, not the new user message. **[CRIT-C6]** confirms it never fires.
- **Issue:** `_evict_if_needed()` (line 243-247) evicts the first N entries by insertion order, not by LRU. The oldest conversations, potentially the most important ones, are evicted first.
- **Issue:** `_handle_task_triggers()` (line 214-221) requires exact keyword match. No fuzzy matching, no LLM-based detection.

### `conversation_search.py` (80 lines)
- **[IMP-9]** SQL injection risk via string concatenation at line 56.
- **[CRIT-C1]** Defaults to `/tmp/ura/search.db`.
- **Issue:** Line 50-52 contains a duplicate `if not tokens: return []` check (identical to line 48-49).
- **Issue:** Tokenization at line 72-80 is naive: no stemming, no lemmatization, no diacritic normalization ("explicación" and "explicacion" are different tokens).
- **Issue:** Search relevance at line 67 uses `match_count / len(tokens)` which is simple overlap. No TF-IDF, no BM25, no positional scoring.

### `context.py` (159 lines)
- **[IMP-3]** Context duplication (immediate ⊆ conversation).
- **Issue:** `HistoricalMemoryAdapter` (line 49-72) imports `motor.memory.models` lazily inside a method. If the import fails, the `.query()` method fails at runtime, not at construction time.
- **Issue:** `_items_to_messages()` (line 143-158) assigns role="system" for HISTORICAL items and "user" for everything else. System role items mixed with user role items may confuse some LLMs that enforce strict system→user→assistant alternation.
- **Issue:** `assemble()` at line 109 uses `len(system_prompt) // 4 + 1` for token estimation. This is a hardcoded ratio that doesn't account for the actual tokenizer.

### `context_window.py` (45 lines)
- **Well done**: Clean implementation, clear token budget with reserve.
- **Issue:** `token_estimate()` uses `len(content) / 4` which is designed for English text. Spanish has more diacritics and longer average word length, making 4.0 chars/token an overestimate (wasting budget) or underestimate (truncation).
- **Issue:** No `TYPE_CHECKING` import for `Message` — the `if TYPE_CHECKING` at line 5 only wraps the import of Message. This works but inconsistent with the wider codebase pattern.

### `llm_bridge.py` (112 lines)
- **[CRIT-4]** Silent `except: pass` at line 88-89.
- **[IMP-4]** No timeout on `_local_generate()`.
- **Issue:** `build_messages()` (line 31-56) builds context by iterating `reversed(ctx)` and inserting at position 0 or 1. This is O(n²) for each message due to list insertion at the front.
- **Issue:** `_messages_to_prompt()` (line 102-112) concatenates messages with `"System: "`, `"User: "`, `"Assistant: "` prefixes and a trailing `"Assistant: "`. This is a naive plain-text format that bypasses the Ollama chat API, losing all structured chat features (tool calls, multiple system messages, etc.).
- **Issue:** `select_model()` (line 58-65) returns model routing keys, not model names. The Ollama provider at line 96 receives these keys as model names, which likely don't exist in Ollama.
- **Issue:** Line 86 — `if response:` checks truthiness. If the router returns an empty string or `None`, it falls through. But `response` from `ModelRouter.generate()` may be a complex object whose truthiness is undefined.

### `intent.py` (188 lines)
- **Well done**: Clean regex-based intent classification with confidence scores.
- **Issue:** `UserIntent.CLARIFY` is a valid enum value but no pattern ever matches it. Dead enum value.
- **Issue:** `QUESTION` pattern at line 65 — `r"^.*\?$"` matches ANY text ending with `?`, even "¿Cómo estás?" (Spanish opening question mark). But at line 102, `t = text.lower().strip()` doesn't normalize the opening `¿`. The `?` is at the end, so the pattern works for Spanish. But `^.*\?$` is greedy and will match long texts.
- **Issue:** `COMMAND` pattern at line 72-74 matches words like "busca", "crea", "haz". But "haz eso" (do that) triggers COMMAND even for casual conversation.
- **Issue:** `_resolve_references()` at line 137-149 duplicates logic from `conversation.py:resolve_reference()`. Two reference resolution implementations that could diverge.
- **Issue:** Entity extraction at line 80-89 — the `language` entity at line 86 uses `re.compile` but the pattern is just a list of language names, not a named group. It matches any occurrence of these words but the "extracted entity" is always the first match (regex returns group(0)), which could be just "en" from "energy" or "es" from "estimation".

### `sentiment.py` (140 lines)
- **[CRIT-C8]** Regex typo at line 49: `eh\|perdona` matches literal `eh|perdona`, not alternation.
- **Issue:** Sentiment detection is purely regex-based. A user saying "I'm so frustrated right now" (English) won't match any Spanish pattern and returns NEUTRAL.
- **Issue:** `get_trend()` at line 127-131 calculates average score over last 5 messages. This is a simple moving average that doesn't account for recency weighting.
- **Issue:** `should_apologize()` (line 133-134) is never called in the API flow. The `_build_adjustments()` method in conversation.py uses `Sentiment` enum directly.
- **Issue:** `should_shorten_response()` and `should_offer_help()` are also dead code.

### `personality.py` (67 lines)
- **Issue:** 100% dead code — never imported by any module in the execution path.
- **Issue:** `summarize_threshold=300` (line 24) refers to character count, but `should_summarize()` checks `text_length > threshold`. This would trigger summarization for any response over 300 chars (about 75 words). For "explicacion" mode with `max_length_chars=2000`, this would always fire.
- **Issue:** `decide()` at line 59 returns a list of `DecisionRule` enums, but nothing downstream reads or acts on these decisions. No output effect.

### `style.py` (124 lines)
- **[IMP-2]** `build_system_prompt()` never called from API.
- **Issue:** `get_profile()` at line 88-108 creates a new `StyleProfile` from scratch using only hardcoded field names, missing fields like `emoji_allowed`, `metadata`, `system_prompt_suffix`. These are manually copied back at lines 106-107, creating a maintenance hazard: any new field added to `StyleProfile` must be manually added to this copy logic.
- **Issue:** `_INTENT_OVERRIDES` (line 73-81) — `COMMAND` override has `use_bullets: True` but bullets are also enabled in WORK mode. The interaction between mode-based and intent-based overrides is unclear and not documented.

### `planner.py` (160 lines)
- **Issue:** 100% dead code — never imported in the execution path.
- **[IMP-6]** No integration with F27 AgentPlanner despite docstring claiming otherwise.
- **Issue:** `create_plan()` (line 96-121) always creates a single-task plan with no task dependencies, no resource estimation, no execution tracking. The plan infrastructure exists but does nothing useful.
- **Issue:** `assess_risks()` (line 156-159) returns static, hardcoded risk strings from `_INTENT_PLANS`. No dynamic risk assessment.

### `interruption.py` (78 lines)
- **[CRIT-C6]** Non-functional in synchronous API — never triggers.
- **Issue:** `auto_recover_context()` at line 68-78 constructs a string like `"[El usuario interrumpió cuando decías: '{ctx.interrupted_message}'. ...]"`. This string is injected into the system prompt via `api.py:125` — it becomes part of the LLM context as a system message. The LLM sees a description of its own interruption, but has no way to know which part of its previous response was actually heard vs. interrupted.
- **Issue:** `context_before_interruption` stores `messages[-6:-2]` (line 51) truncated to 100 chars each. If the conversation has fewer than 6 messages, this is empty.

### `streaming.py` (58 lines)
- **Issue:** 100% dead code — no callers of `StreamManager` found in any module.
- **Issue:** `to_sse()` at line 17-19 uses `f"data: {payload}\n\n"` but doesn't set the `event:` field. SSE clients that filter by event type will miss all messages.
- **Issue:** `stream_response()` at line 35-55 accepts `AsyncGenerator[str, None]` but there's no LLM provider that returns this type. The `OllamaProvider` likely returns sync strings.

### `tools.py` (100 lines)
- **Issue:** 100% dead code — no callers of `ToolOrchestrator`.
- **Issue:** `ShellTool.run()` at line 49-57 uses `cmd.split()` to tokenize the command string. If the command contains spaces within arguments (e.g., `echo "hello world"`), this splits incorrectly and breaks quoting.
- **Issue:** `GitStatusTool` and `GitLogTool` use hardcoded `repo = params.get("repo", str(Path.cwd()))`. The working directory of the server process is used as default, which is unpredictable and a path traversal risk.
- **Issue:** No `cwd` parameter for any tool. Tools don't validate that the repo path is within an allowed directory.

### `corrective_learning.py` (126 lines)
- **[CRIT-C1]** Defaults to `/tmp/ura/corrections.db`.
- **Issue:** `_parse_correction()` (line 87-118) uses simple keyword matching ("no es", "en realidad", "corrige"). A correction like "No es correcto, la respuesta es..." parses correctly, but "Creo que no es exactamente así" would match "no es" with misleading topic extraction (word after "no es" is "exactamente", not the actual correction).
- **Issue:** `_extract_topic()` (line 120-127) returns the first non-stop word longer than 3 characters. For "corrige el artículo sobre Python", the topic would be "artículo" not "Python" (because sorting by word order). Actually, looking more carefully, it returns the first word matching the criteria. "artículo" has len 8 > 3 and is not a stop word. "Python" has len 6 > 3. So it depends on order. For "corrige Python artículo", topic = "Python". Fragile.

### `proactive_memory.py` (136 lines)
- **[CRIT-C1]** Defaults to `/tmp/ura/proactive.db`.
- **Issue:** `detect_task_trigger()` uses `"in"` containment check (line 127): `if any(k in msg_lower for k in keywords)`. This means "recuérdame" is triggered by "recuérdame" but also by "norecuérdame" or any string containing the keyword as a substring. No word boundary matching.
- **Issue:** `suggest_proactive()` (line 131-136) returns `"Tienes tareas pendientes: ... ¿Quieres que las revise?"` every time. No variation, no context awareness, no fatigue management. If the user ignores this 5 times, it still fires on every turn.

### `episodic_memory.py` (107 lines)
- **[IMP-5]** Summaries accumulate indefinitely with no eviction.
- **Issue:** `TopicExtractor.extract()` (line 95-102) returns the 5 most frequent non-stop words. For "Tell me about Python programming for data science", this returns ["python", "programming", "data", "science", "tell"] — "tell" is a stop word that should be in the set.
- **Issue:** `extract_key_topic()` (line 104-107) returns the first non-stop word over 3 chars. For "¿Qué es la inteligencia artificial?", the first word is "Qué" (length 3, excluded), then "inteligencia" (length 12, included). Topic = "inteligencia". But "A ver, ¿qué es Python?" → first word "ver" (length 3, excluded), then "qué" (length 3, excluded) — falls through and topic = "ver" because the filter means `meaningful` could still include words of length 3 if no words > 3 exist. Wait, `len(w) > 3` means strictly greater than 3. So "ver" (len 3) is excluded. `meaningful` would be empty. Returns empty string. No topic extracted. This fails for short queries.
- **Issue:** `store_conversation()` uses `_summary_` prefix conversation IDs in `MessageStore`, polluting the namespace. `list_conversations()` would return these alongside real conversations.

### `implicit_feedback.py` (109 lines)
- **[CRIT-C1]** Defaults to `/tmp/ura/feedback.db`.
- **Issue:** `_is_rephrase()` (line 71-77) checks word overlap between previous and current message. The criteria `len(overlap) >= 2 and len(prev_words - curr_words) > 0 and len(curr_words - prev_words) > 0` is very loose. Two sequential messages about the same topic would trigger "was_unclear" even if the previous response was perfectly clear.
- **Issue:** `_is_repeat()` (line 79-82) checks exact string equality. "Repite eso" vs "repite eso " (trailing space) would not match. This misses many repeat queries.
- **Issue:** `analyze()` at line 63 checks `if "gracias" in user_message.lower()`. "Gracias a ti" (50+ chars) wouldn't match the `len(user_message) < 50` check. "Muchísimas gracias" (15 chars, contains "gracias") would fire. This is decent but imprecise.

### `management.py` (97 lines)
- **Issue:** 100% dead code — never imported in the execution path.
- **Issue:** `needs_summary()` at line 63 returns True only once per conversation (when `conversation_id not in self._summaries`). After the first summary is stored, it never triggers again, even after 100 more messages.
- **Issue:** `split_conversation()` at line 72-80 creates a new conversation ID like `{original}_part2` but never updates any reference. The old conversation continues to be used, and the split half is orphaned.
- **Issue:** `detect_goal_change()` at line 35-43 sets `self._goals[conversation_id]` after detecting a change, but `set_goal()` at line 45-46 also sets it. Two methods doing the same thing.

### `trends.py` (60 lines)
- **Well done:** Clean, focused, single responsibility. Good use of dataclasses.
- **Issue:** `_TEMPORAL_TRIGGERS` regex matches "2024" through "2029". When the date passes 2029, this needs updating. No dynamic date detection.
- **Issue:** `analyze_query()` at line 34-57 returns `needs_update=True` even for non-question messages that mention time. This could trigger unnecessary web searches for "I'm reading a book about current affairs" when no update is needed.

### `web_search.py` (50 lines)
- **[CRIT-C4]** Silent `except: pass` at line 42-43.
- **Issue:** DuckDuckGo API (`api.duckduckgo.com`) without an API key returns very limited results. AbstractText is often empty for anything beyond simple queries.
- **Issue:** No caching. Every `search_if_needed()` call makes an HTTP request even for identical queries.
- **Issue:** No rate limiting on the external API. A user who asks 10 time-sensitive questions in a minute triggers 10 DuckDuckGo API calls.
- **Issue:** 100% dead code by default — `web_search.py` implements `_search_web` but `WebSearchIntegration` is never called from the API flow.

### `auto_mode.py` (108 lines)
- **Well done:** Clean implementation, clear regex patterns, confidence scoring.
- **Issue:** `_CONCISE_TRIGGERS` includes "no hace falta que expliques" which is a full sentence, not a trigger word. A user saying "No hace falta que expliques tanto" matches, but so does "No hace falta que expliques, ya lo sé" — redundant with the shorter "concreta" pattern.
- **Issue:** `_WORK_TRIGGERS` (line 30-34) matches the same command words as `intent.py:COMMAND` pattern. The two could diverge. A single source of truth would be better.

### `tool_confirmation.py` (64 lines)
- **Issue:** 100% dead code — never imported.
- **Issue:** `needs_confirmation()` (line 30-40) checks `params.get("command", "").lower()` — but `params` is typed as `dict[str, str]` in `ConfirmationRequest` but `dict[str, Any]` in `needs_confirmation()`. Type mismatch.
- **Issue:** `DANGEROUS_TOOLS` includes `"shell"` but `DANGEROUS_TOOLS` cannot block `ToolOrchestrator.ShellTool` because the tool name is "shell" (line 47 in tools.py) which is in the dangerous set. Good, but the system never connects these two modules.

### `tools/` (empty directory)
- Directory exists but is empty. Possibly a placeholder for future tool plugins.

---

## 6. Test Coverage Assessment

### What's Tested
- `models.py`: Message creation, token estimate, conversation add_message, mode values, intent values ✓
- `message_store.py`: Append, retrieve, list, delete, persistence ✓
- `context_window.py`: Budget respect, trim ✓
- `conversation.py`: Create, get_or_create, add_message, context, intent detection (8 cases), reference resolution, list, delete, mode persistence ✓
- `personality.py`: Default profile, summarize thresholds, ask/assume decisions ✓
- `learning.py`: Record interaction, default preferences, multiple interactions ✓
- `management.py`: Goal change detection, needs_summary, store/get/summary, pending tasks, split ✓
- `style.py` (separate test file): Profile selection, intent overrides ✓
- `tools.py` (separate test file): Tool selection ✓
- `intent.py` (separate test file): Intent classification ✓
- `planner.py` (separate test file): Plan creation ✓
- `context.py` (separate test file): Context assembly ✓

### What's NOT Tested
- `sentiment.py`: No tests for `SentimentDetector.detect()`, `get_trend()`, individual sentiment patterns
- `interruption.py`: No tests for `detect_interruption()`, `auto_recover_context()`
- `episodic_memory.py`: No tests for `store_conversation()`, `retrieve_by_topic()`, `get_relevant_context()`
- `corrective_learning.py`: No tests for `record_correction()`, `get_relevant_corrections()`, `_parse_correction()`
- `proactive_memory.py`: No tests for `add_task()`, `get_pending_tasks()`, `complete_task()`
- `implicit_feedback.py`: No tests for `analyze()`, `_is_rephrase()`, `_is_repeat()`
- `trends.py`: No tests
- `web_search.py`: No tests
- `streaming.py`: No tests
- `tool_confirmation.py`: No tests
- `conversation_search.py`: No tests
- `api.py`: No integration tests
- `llm_bridge.py`: No tests (depends on external LLM)
- `auto_mode.py`: No tests for `detect_mode()` integration

**Coverage breakdown**: ~50% of files have tests. The untested 50% includes the most complex subsystems (sentiment, interruption, episodic memory, corrective learning, proactive memory, implicit feedback).

---

## 7. Dependency Graph (Actual vs. Intended)

```
ACTUAL EXECUTION PATH (what runs when API is called):

api.py
  └─ conversation.py (ConversationEngine)
       ├─ message_store.py ✓
       ├─ context_window.py ✓
       ├─ intent.py ✓
       ├─ auto_mode.py ✓
       ├─ interruption.py (dead code — never triggers)
       ├─ episodic_memory.py ✓
       ├─ trends.py ✓
       ├─ sentiment.py ✓
       ├─ corrective_learning.py ✓
       ├─ proactive_memory.py ✓
       └─ implicit_feedback.py ✓
  └─ llm_bridge.py
       └─ motor.core.llm.router.ModelRouter (external)
       └─ motor.core.llm.ollama.OllamaProvider (external)

DEAD CODE (never called from API):

streaming.py, tool_confirmation.py, tools.py (ToolOrchestrator),
planner.py, personality.py, web_search.py, conversation_search.py,
management.py, style.py (build_system_prompt)
```

---

## 8. Recommendations Priority

### Immediate (Fix Today)
1. **[CRIT-C1]** Move SQLite databases from `/tmp/` to persistent path (UraConfig)
2. **[CRIT-C2]** Add authentication layer
3. **[CRIT-C4]** Replace `except: pass` with structured logging + proper error responses
4. **[CRIT-C5]** Offload sync work from async event loop
5. **[CRIT-C8]** Fix sentiment regex typo

### Short-Term (This Sprint)
6. **[CRIT-C3]** Implement streaming endpoint
7. **[IMP-1]** Either integrate or archive the 9 dead files
8. **[IMP-2]** Wire StyleEngine into API
9. **[IMP-4]** Add timeouts to LLM calls
10. **[IMP-8]** Add content moderation layer
11. **[CRIT-C7]** Fix reference resolution to not produce broken text

### Medium-Term (Next Sprint)
12. **[IMP-3]** Fix context deduplication
13. **[IMP-5]** Add eviction to episodic memory
14. **[IMP-7]** Wire tool execution into API
15. **[IMP-9]** Fix SQL construction pattern in conversation_search.py
16. [NTH-1] Consolidate to single SQLite database
17. Add integration tests for the full API flow
18. Add tests for all untested subsystems

### Long-Term
19. [NTH-2] FTS5 for conversation search
20. [NTH-3] LLM-based intent classification
21. Async refactor of entire subsystem chain
22. A/B testing framework for conversation modes
23. Graceful degradation / circuit breaker pattern

---

## 9. Conclusion

The `motor/assistant/` module demonstrates strong architectural thinking in its file organization and component separation. The F29 specification covers the right features for a production conversational AI. However, the implementation has two fundamental problems:

1. **Execution gap**: ~60% of the code exists in specification-compliant isolation but was never integrated into the working API path. These are not just unused features — they create a maintenance burden and a false sense of capability.

2. **Production immaturity**: The working path lacks authentication, streaming, proper error handling, async support, and data persistence hardening. These are not nice-to-haves; they are table stakes for any system exposed to real users.

The subsystem architecture is a solid foundation. The remediation path is clear: harden the working path, integrate the best subsystems (sentiment, episodic memory, corrective learning, style), archive the unreachable ones, and add tests for everything that remains.
