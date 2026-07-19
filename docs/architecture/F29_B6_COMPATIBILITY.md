# F29 B6 — Compatibilidad y Evolución

## Principio
Zero compatibility breaks. No API changes since F28.1.

## Rolling Upgrade
```bash
# 1. Backup state
python3 scripts/pro/backup_f26_memory.py backup

# 2. Stop services
systemctl stop ura-api

# 3. Deploy new wheel
pip install --upgrade ura-0.29.0-py3-none-any.whl

# 4. Start services
systemctl start ura-api

# 5. Verify health
curl -f http://localhost:8000/health
```

## Mixed-Version Compatibility
| Component Version | F26 Journal | F27 Protocol | F28 Envelope |
|-------------------|-------------|--------------|--------------|
| v0.28.x → v0.29.x | Same format | Same schema | Same headers |
| Forward | ✅ Journal format unchanged | ✅ Schema backward compat | ✅ New fields optional |
| Backward | ✅ Snapshot loadable | ✅ Old messages accepted | ✅ Old headers parsed |

## Downgrade Procedure
```bash
pip install ura==0.28.3
python3 scripts/pro/backup_f26_memory.py restore --path /opt/ura/backups/pre_upgrade.json
```

## Compatibility Constraints
- C01: No new required fields in ProtocolEnvelope
- C02: Journal format frozen (v1)
- C03: Snapshot format frozen (v1)
- C04: All ADR-028 health endpoints preserved
- C05: All metrics names preserved
