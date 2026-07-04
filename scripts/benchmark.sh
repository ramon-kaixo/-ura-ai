#!/usr/bin/env bash
# Benchmark oficial del Knowledge Engine
# Mide: compile 100 docs, 1000 searches, 100 archives, 10000 audit events
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
DB="$TMP/knowledge.db"
SRC="$TMP/source"
ARCHIVE="$TMP/archives"
mkdir -p "$SRC" "$ARCHIVE"

echo "=== Benchmark: Knowledge Engine ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Engine: $(PYTHONPATH=. python3 -c 'from knowledge.engine.migrations import ENGINE_VERSION; print(ENGINE_VERSION)')"
echo "Schema: $(PYTHONPATH=. python3 -c 'from knowledge.engine.migrations import SCHEMA_VERSION; print(SCHEMA_VERSION)')"
echo ""

# Init
PYTHONPATH=. python3 knowledge/engine/cli.py --db-path "$DB" init
echo "DB initialized"

# Create 100 documents
for i in $(seq 1 100); do
    cat > "$SRC/doc_$(printf '%04d' $i).md" <<EOF
---
title: Document $i
type: doc
tags: [benchmark]
---
Body of document $i with some content for benchmarking.
EOF
done

cd "$TMP"
git init -q
git config user.email "b@m"
git config user.name "Benchmark"
git add source/
git commit -m "benchmark" -q
cd - > /dev/null

# Compile
echo ""
echo "--- Compile 100 docs ---"
START=$(date +%s%N)
PYTHONPATH=. python3 knowledge/engine/cli.py --db-path "$DB" compile --source-dir "$SRC"
END=$(date +%s%N)
COMPILE_MS=$(( (END - START) / 1000000 ))
echo "  Time: ${COMPILE_MS}ms"

# Searches
echo ""
echo "--- 1000 searches ---"
START=$(date +%s%N)
for i in $(seq 1 1000); do
    PYTHONPATH=. python3 knowledge/engine/cli.py --db-path "$DB" search "Document" >/dev/null 2>/dev/null
done
END=$(date +%s%N)
SEARCH_MS=$(( (END - START) / 1000000 ))
echo "  Time: ${SEARCH_MS}ms (avg $((SEARCH_MS / 1000))ms/search)"

# Archives
echo ""
echo "--- 100 archives ---"
START=$(date +%s%N)
for i in $(seq 1 100); do
    PYTHONPATH=. python3 knowledge/engine/cli.py --db-path "$DB" archive source --source-dir "$SRC" --archive-dir "$ARCHIVE" >/dev/null 2>/dev/null
done
END=$(date +%s%N)
ARCHIVE_MS=$(( (END - START) / 1000000 ))
echo "  Time: ${ARCHIVE_MS}ms (avg $((ARCHIVE_MS / 100))ms/archive)"

# DB size
SIZE=$(stat --format=%s "$DB" 2>/dev/null || echo 0)
WAL=$(stat --format=%s "$DB-wal" 2>/dev/null || echo 0)
echo ""
echo "--- Resource usage ---"
echo "  DB size: $((SIZE / 1024)) KB"
echo "  WAL size: $((WAL / 1024)) KB"

# Summary
echo ""
echo "=== RESULTS ==="
echo "compile_100: ${COMPILE_MS}ms"
echo "search_1000: ${SEARCH_MS}ms"
echo "archive_100: ${ARCHIVE_MS}ms"
echo "db_size_kb: $((SIZE / 1024))"
echo "wal_size_kb: $((WAL / 1024))"

rm -rf "$TMP"
