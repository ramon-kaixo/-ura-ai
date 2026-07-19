# Second Expert Review: `motor/assistant/` — Follow-up Assessment

**Reviewer:** AI systems architect
**Date:** 2026-07-20
**Scope:** All 19 active files in `motor/assistant/`, 6 test files
**Previous review:** `docs/architecture/EXPERT_REVIEW_ASSISTANT.md`

---

## Executive Summary

The team addressed 10 of 23 actionable items from the first review. Of the 10 CRIT-flagged issues: 1 is fully resolved, 5 are partially addressed (with 2 having broken fixes), and 4 remain untouched. The dead code problem is substantially reduced (6 files archived), but the new code adds surface area that reintroduces some of the same patterns.

The module is healthier than before but is **NOT production-ready**. The core vulnerability (data in `/tmp/`, zero auth) remains open.

---

## 1. What Was Fixed — Scorecard

| # | Issue | Status | Assessment |
|---|-------|--------|------------|
| CRIT-C8 | Sentiment regex `\|` typo | **✅ FIXED** | `"huh|eh|perdona"` — correct alternation |
| IMP-1 | 9 dead files | **✅ SIGNIFICANTLY REDUCED** | 6 files removed from active tree. `tools.py`, `personality.py`, `planner.py`, `management.py`, `web_search.py`, `conversation_search.py` gone |
| CRIT-C4 | Silent `except: pass` in api.py | **✅ FIXED** | Replaced with graceful fallback replies |
| CRIT-C5 | Sync-in-async (streaming path) | **🟡 PARTIAL** | `generate_async` uses `to_thread`. But `_process()` is still sync on both paths |
| CRIT-C3 | Streaming declared but unused | **🟡 PARTIAL** | `stream=True` now triggers SSE response. But it sends the *entire* response as one event — not token-by-token streaming |
| IMP-8 | Content moderation | **🟡 PARTIAL** | `PromptSanitizer` added for input. No output moderation |
| IMP-3 | Context duplication | **🔴 BROKEN FIX** | Deduplicates by `id(m)` — Python object identity. Each DB `fetchall()` creates new objects, so `id()` never matches. Duplicate entries remain |
| CRIT-C5 | Sync-in-async (non-streaming path) | **🔴 NOT FIXED** | `chat()` is async but calls sync `llm.generate()` directly with no `await` or `to_thread` |

---

## 2. What Was NOT Fixed

| # | Issue | Impact | Why It Matters |
|---|-------|--------|----------------|
| **CRIT-C1** | All data in `/tmp/` | **DATA LOSS ON REBOOT** | 5 DBs still default to `/tmp/ura/`. Lost on any restart |
| **CRIT-C2** | Zero authentication | **RCE BY DESIGN** | No API key, no JWT, no user concept |
| CRIT-C6 | Interruption detection | **NEVER TRIGGERS** | Same architectural mismatch — sync API + even message count |
| CRIT-C7 | Reference resolution gibberish | **CONFUSES LLM** | Same broken `(ctx...)` injection patterns |
| CRIT-C9 | No user identity | **NO PERSONALIZATION** | `ChatRequest` has no `user_id`. Learning/per-user state is dead on arrival |
| IMP-2 | StyleEngine not wired | **DUPLICATE LOGIC** | `api.py` has its own `_SYSTEM_PROMPTS` dict. `style.py:build_system_prompt` is still unreferenced in API |
| IMP-4 | No timeout on LLM calls | **HANG FOREVER** | `_local_generate` has no timeout. If Ollama hangs, the request hangs |
| IMP-5 | Episodic memory eviction | **UNBOUNDED GROWTH** | Summaries accumulate indefinitely in MessageStore |

---

## 3. NEW Issues Introduced

### N1: `generate_stream()` is a facade (CRITICAL)

**File:** `llm_bridge.py:81-93`

```python
async def generate_stream(self, ...) -> str:
    return await asyncio.to_thread(self.generate, ...)
```

This is identical to `generate_async`. It returns a complete string, not an `AsyncGenerator[str]`. The `StreamManager.stream_response()` at `streaming.py:35` expects `AsyncGenerator[str, None]`. Since `generate_stream` returns `str`, calling `async for chunk in response_gen` would fail at runtime.

The API at `api.py:173-196` doesn't call `generate_stream` at all — it calls `generate_async` and packages the complete response as a single SSE event. There is no real token-by-token streaming path anywhere.

**Fix:** Either implement actual chunked generation through Ollama's `/api/generate` (stream=True) or remove the `stream` flag and acknowledge that streaming is future work.

### N2: Context deduplication fix is broken (CRITICAL)

**File:** `context.py:124-128`

```python
immediate_messages = self._store.get_conversation(conversation_id, limit=self._max_immediate)
immediate_ids = {id(m) for m in immediate_messages}
history = [m for m in messages if id(m) not in immediate_ids]
```

`id(m)` returns the Python object's memory address. Each `get_conversation()` call constructs new `Message` objects from fresh SQLite rows. The `id()` values will never collide, so `history` is always identical to `messages`. No deduplication actually occurs.

**Fix:** Deduplicate by `(m.timestamp, m.content, m.role)` tuple, not by Python object identity. Or pass a `last_n` parameter to skip the tail.

### N3: Non-streaming path is still sync-blocking (HIGH)

**File:** `api.py:198-214`

```python
# async def chat() — but this path has no await:
reply = llm.generate(...)  # synchronous, blocks event loop
```

The streaming path wraps generation in `asyncio.to_thread`. The non-streaming path (default!) calls `llm.generate()` directly from an `async def`. A single concurrent request blocks the ASGI worker. Two concurrent requests serialize.

**Fix:** Always route through `generate_async` + `await`, even for non-streaming.

### N4: `tools.py` deleted, empty `tools/` preserved (MEDIUM)

`ToolOrchestrator`, `ShellTool`, `GitStatusTool`, `GitLogTool` were removed. The `tools/` directory is empty. The F29 spec document at `F29_ASISTENTE_CONVERSACIONAL.md:190` still references `from motor.assistant.tools import ToolOrchestrator` — a broken import.

The module lost its tool execution capability entirely. This is either a regression or an undocumented architectural decision.

**Fix:** Either implement tool execution properly (even a stub), or update the F29 doc and remove the empty `tools/` directory.

### N5: `style.py` kept but still unreferenced (MEDIUM)

`StyleEngine.build_system_prompt()` is still not called anywhere in the API path. The API has its own `_SYSTEM_PROMPTS` dict and `_build_system_prompt()` function. `style.py` lives on only through test imports. This is dead code in the runtime.

**Fix:** Either wire `StyleEngine.build_system_prompt()` into `_build_system_prompt()` in `api.py`, or archive `style.py`.

### N6: `LanguageDetector` is fragile (LOW)

**File:** `language.py:37-57`

Works by counting token matches in two hardcoded lexicons. Will fail for:
- Short messages ("Sí" = 2 chars, only matches "sí" in Spanish lexicon → es_ratio = 1.0, correct but fragile)
- Messages without function words ("javascript async await" → no matches → defaults to Spanish)
- Mixed language where the function words are English but content is Spanish

The 0.15 threshold means messages like "the" (3 words, 1 match = 0.33 ratio) would classify as English — but "the x y z" (4 words, 1 match = 0.25) also English. This is okay for a heuristic but should be documented as best-effort.

### N7: `PromptSanitizer` lacks output path (LOW)

Input injection is handled. Output injection (LLM generating harmful content, PII leakage) has zero protection. For a system exposed to real users without auth, this is risky.

---

## 4. Remaining Issues from Review 1 (Unchanged)

| Issue | File | Notes |
|-------|------|-------|
| Singleton race | `api.py:43-56` | `get_engine()` / `get_llm()` still have no locking |
| Rate limiter leak | `api.py:62-73` | `_requests` dict grows without cleanup |
| O(n²) context build | `llm_bridge.py:48` | `insert(0, ...)` in loop |
| Naive prompt format | `llm_bridge.py:130-140` | Plain text, not Ollama chat API |
| Model key vs name | `llm_bridge.py:58-65` | Router keys used as Ollama model names |
| Interruption never fires | `interruption.py:33-54` | Architectural (sync API + even message count) |
| Reference resolution broken | `conversation.py:125-137` | Same as review 1 |
| Eviction is FIFO not LRU | `conversation.py:251-255` | Evicts oldest creation first |
| No __all__ / __version__ | `__init__.py` | Still 1 line, no exports |
| Token estimate hardcoded at 4.0 | `context_window.py:18` | Doesn't account for Spanish diacritics |
| `IntentEngine._resolve_references` duplicates | `intent.py:137-150` | Second reference resolver (duplicates conversation.py) |
| Topic extraction fragile | `episodic_memory.py:104-107` | Fails for short queries |
| Proactive suggestion has no fatigue | `proactive_memory.py:131-136` | Fires every turn |
| `_is_rephrase` very loose | `implicit_feedback.py:71-77` | Sequential same-topic messages trigger "unclear" |
| Interruption context empty for <6 msgs | `interruption.py:51` | `messages[-6:-2]` is empty for short conversations |

---

## 5. What's Actually Better Than Before

1. **PromptSanitizer** — clean implementation, well-tested. Anti-jailbreak patterns are reasonable.
2. **LanguageDetector** — simple but effective for the es/en use case. Good addition for bilingual support.
3. **Graceful fallback** — returning user-friendly messages instead of raw error strings is the right pattern.
4. **API tests** — 7 tests for `_build_system_prompt`, `_FALLBACK_REPLIES`. Good coverage of the prompt construction logic.
5. **Security tests** — 11 tests for sanitizer + language detector. Good.
6. **Dead code removal** — 6 files gone from active tree. Codebase is 22% smaller by file count.
7. **`generate_async`** — the `to_thread` wrapper pattern is correct, even if the sync path bypasses it.

---

## 6. Dependency Graph (Updated)

```
ACTUAL EXECUTION PATH (what runs when API is called):

api.py (async)
  └─ _process()  (SYNC — blocks event loop)
       └─ conversation.py (ConversationEngine)
            ├─ message_store.py ✓
            ├─ context_window.py ✓
            ├─ intent.py ✓
            ├─ auto_mode.py ✓
            ├─ language.py ✓ (NEW)
            ├─ prompt_sanitizer.py ✓ (NEW)
            ├─ interruption.py (dead code — never triggers) ⚠️
            ├─ episodic_memory.py ✓
            ├─ trends.py ✓
            ├─ sentiment.py ✓
            ├─ corrective_learning.py ✓
            ├─ proactive_memory.py ✓
            └─ implicit_feedback.py ✓
  └─ llm_bridge.py
       └─ generate_async() → to_thread → generate() → router or Ollama

DEAD OR BROKEN CODE:
  streaming.py:StreamManager — stream_response() never called
  style.py:StyleEngine.build_system_prompt() — never called from API
  context.py:_get_conversation_history() — deduplication broken
  llm_bridge.py:generate_stream() — facade, identical to generate_async
  tools/ — empty directory
```

---

## 7. Recommendations Priority

### Must-Fix Before Any Real Deployment

1. **CRIT-C1: `/tmp/` → persistent path** — 30-minute task. Use `CONFIG` or `motor/core/config.py`.
2. **CRIT-C2: Authentication** — minimal viable: Bearer token via `motor/core/secrets.py`. 1-hour task.
3. **N2: Fix context deduplication** — change `id(m)` to `(m.timestamp, m.content, m.role)` tuple. 15-minute task.
4. **N3: Make non-streaming path async** — always await `generate_async`. 15-minute task.
5. **CRIT-C4 residual: `llm_bridge.py:116`** — replace `except: pass` with logging + proper error. 10-minute task.

### Should-Fix This Sprint

6. **N5: Wire StyleEngine or archive it** — either integrate or move to `.nervioso/`. 30 minutes.
7. **IMP-4: Add timeout to LLM calls** — 30s default, propagate as 504. 20 minutes.
8. **N4: Fix `tools/` or remove it** — update F29 doc, remove empty dir. 10 minutes.
9. **N1: Either implement real streaming or remove the facade** — token-by-token SSE or honest single-response. 2-3 hours for real streaming.
10. **IMP-5: Add eviction to episodic memory** — 20-minute task.
11. **Rate limiter cleanup** — periodic stale entry eviction. 15 minutes.

### Next Sprint

12. **CRIT-C7: Fix reference resolution** — use structured context hints instead of inline injection.
13. **Singleton locking** — add threading lock to `get_engine()`/`get_llm()`.
14. **Interruption detection** — requires real streaming to function. Defer to streaming rework.
15. **Output moderation** — add `PromptSanitizer`-equivalent for LLM output.
16. **`__init__.py` exports** — define `__all__`, export public symbols.

---

## 8. Conclusion

The module is **healthier but not healthy**. The team correctly prioritized the dead code problem and the most egregious silent error swallowing. The new additions (PromptSanitizer, LanguageDetector, graceful fallback, API tests) are well-executed.

However, the fixes have a concerning pattern: 2 of the 5 attempted fixes are broken (context dedup by `id()`, streaming facade). This suggests insufficient integration testing — the streaming path was never actually exercised end-to-end.

The core production blockers (data persistence, authentication) remain untouched from the first review. These are not architectural debates — they are binary gates. Without them, the system cannot be deployed to any environment where data matters or where untrusted clients can reach the endpoint.

**Readiness: DEVELOPMENT ONLY.** Do not expose to any real user or external network without at minimum fixing items 1-2 from the priority list.
