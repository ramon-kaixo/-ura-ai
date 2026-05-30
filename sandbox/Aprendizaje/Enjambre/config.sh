#!/bin/bash
export OLLAMA_URL="${OLLAMA_URL:-http://10.164.1.99:11434/api/chat}"
export MODEL="${OLLAMA_MODEL:-qwen3:32b}"
export PROXY="${PROXY:-http://localhost:3128}"
export REPO="${HOME}/URA/ura_ia_1972"
