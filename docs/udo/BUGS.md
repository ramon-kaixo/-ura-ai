# BUGS conocidos

## BUG-001 — pre-commit/stash vs archivos chattr +i (GX10)
**Síntoma**: cualquier `git commit`, `git stash push` o rebase que dispare el mecanismo
stash/checkout interno de pre-commit falla con `unable to unlink old '<archivo>': Operación no permitida`
si hay cambios sin commitear en archivos con `chattr +i`. Puede dejar el worktree parcialmente
revertido y el stash SIN restaurar (parche huérfano en ~/.cache/pre-commit/patch*).

**Archivos inmutables conocidos (2026-08-25)**: config/{system_config,reglas_builtin,settings,
dispositivos,infra_config,schema}.json · deploy/{lildax_config,sync_to_asus.sh,estado_alemania.json} · core/debate/committee_config.json

**Workaround**: antes de operar git en GX10 con árbol sucio:
1. `lsattr -R . | grep -- '-i-'` para inventariar.
2. Pedir a Ramón `sudo chattr -i <los que estén dirty>`.
3. Operar. Restaurar `+i` después.
4. Si hay parche huérfano: `git apply ~/.cache/pre-commit/patch<id>` selectivo por archivo
   y verificar con `git apply --reverse --check`.

**Estado**: abierto — requiere decisión de diseño (¿skip-worktree en vez de chattr?).
