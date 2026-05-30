#!/bin/bash
# laia_bridge.sh — Puente desde Tuneladora hacia Laia API
# Permite que cualquier buzo o el bibliotecario envíen comandos a Laia.
# Uso: source orquestador/laia_bridge.sh

LAIA_URL="${LAIA_URL:-http://localhost:8000}"
URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"

function laia_command() {
    local cmd="$1"
    curl -s -X POST "$LAIA_URL/command" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$cmd\"}" | jq .
}

function laia_plan_and_execute() {
    local goal="$1"
    curl -s -X POST "$LAIA_URL/plan/execute" \
        -H "Content-Type: application/json" \
        -d "{\"goal\": \"$goal\"}" | jq .
}

function laia_plan() {
    local goal="$1"
    curl -s -X POST "$LAIA_URL/plan" \
        -H "Content-Type: application/json" \
        -d "{\"goal\": \"$goal\"}" | jq .
}

function laia_macro_learn() {
    local name="$1"
    local goal="$2"
    curl -s -X POST "$LAIA_URL/macro/learn" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$name\", \"goal\": \"$goal\"}" | jq .
}

function laia_macro_run() {
    local name="$1"
    curl -s -X POST "$LAIA_URL/macro/run" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$name\"}" | jq .
}

function laia_macro_list() {
    curl -s "$LAIA_URL/macro/list" | jq .
}

function laia_frigate_query() {
    local label="${1:-person}"
    local after="${2:-}"
    local before="${3:-}"
    local zone="${4:-}"
    local payload="{\"label\": \"$label\""
    [[ -n "$after" ]] && payload+=", \"after\": $after"
    [[ -n "$before" ]] && payload+=", \"before\": $before"
    [[ -n "$zone" ]] && payload+=", \"zone\": \"$zone\""
    payload+="}"
    curl -s -X POST "$LAIA_URL/frigate/query" \
        -H "Content-Type: application/json" \
        -d "$payload" | jq .
}

function laia_health() {
    curl -s "$LAIA_URL/health" | jq .
}

export -f laia_command
export -f laia_plan_and_execute
export -f laia_plan
export -f laia_macro_learn
export -f laia_macro_run
export -f laia_macro_list
export -f laia_frigate_query
export -f laia_health
