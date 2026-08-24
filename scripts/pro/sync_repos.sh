#!/bin/bash
# sync_repos.sh — alinea Mac <-> GX10 con main remoto evitando divergencias (2026-08-25)
set -u
echo "=== Sync Mac ==="
cd "$HOME/URA" && git pull --ff-only origin main && git push origin main || echo "Mac: revisar manualmente"
echo "=== Sync GX10 ==="
ssh -o BatchMode=yes ramon@100.72.103.12 "cd ~/URA/ura_ia_1972 && git pull --ff-only origin main" || echo "GX10: revisar manualmente (WIP local o divergencia)"
echo "=== Verificación ==="
git log --oneline -1
ssh -o BatchMode=yes ramon@100.72.103.12 "cd ~/URA/ura_ia_1972 && git log --oneline -1"
