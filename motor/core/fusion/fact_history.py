"""FactHistory — historial de versiones de un Fact (R07, F25-B6).

Agregado raíz del modelo de versionado. Todo acceso de escritura
a FactVersion debe pasar por FactHistory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.models import FactVersion, VersionState

if TYPE_CHECKING:
    from motor.core.fusion.models import Fact, FactTombstone


class FactHistory:
    """Agregado raíz del versionado de un Fact.

    Responsabilidad única: gestionar el ciclo de vida completo de las
    versiones de un Fact: crear, actualizar, rollback, tombstone, delete.

    Reglas (IMP-01 a IMP-10):
    - Es el agregado raíz: nunca permitir acceso de escritura directo a FactVersion.
    - Toda mutación preserva los invariantes de ADR-025-02/03/04.
    - Toda operación de modificación es transaccional (no hay estados intermedios).
    - FactIndex indexa solo la versión vigente; el histórico se accede vía FactHistory.
    - No hay referencias circulares: FactHistory → FactVersion (no al revés).
    - version_id y fact_id nunca se reutilizan.
    - Rollback: operación de navegación, no altera el pasado.
    """

    def __init__(self, fact: Fact, initial_version: FactVersion) -> None:
        if fact.fact_id != initial_version.fact_id:
            msg = f"Fact fact_id '{fact.fact_id}' != FactVersion fact_id '{initial_version.fact_id}'"
            raise ValueError(msg)
        if initial_version.state != VersionState.CURRENT:
            msg = "Initial version must have state=CURRENT"
            raise ValueError(msg)

        self._fact_id: str = fact.fact_id
        self._current: str = initial_version.version_id
        self._versions: dict[str, FactVersion] = {
            initial_version.version_id: initial_version,
        }
        self._tombstones: dict[str, FactTombstone] = {}
        self._created: float = initial_version.created_at
        self._updated: float = initial_version.created_at

    # ── API pública ──────────────────────────────────

    @property
    def fact_id(self) -> str:
        return self._fact_id

    @property
    def current(self) -> FactVersion:
        v = self._versions.get(self._current)
        if v is None:
            msg = f"Current version '{self._current}' not found"
            raise RuntimeError(msg)
        return v

    @property
    def current_version_id(self) -> str:
        return self._current

    @property
    def created(self) -> float:
        return self._created

    @property
    def updated(self) -> float:
        return self._updated

    @property
    def version_count(self) -> int:
        return len(self._versions)

    @property
    def has_tombstone(self) -> bool:
        return any(v.state == VersionState.TOMBSTONE for v in self._versions.values())

    def get_version(self, version_id: str) -> FactVersion | None:
        return self._versions.get(version_id)

    def timeline(self) -> list[FactVersion]:
        return sorted(self._versions.values(), key=lambda v: v.created_at)

    def version_at(self, timestamp: float) -> FactVersion | None:
        """Retorna la versión vigente en el instante dado.

        Si current se creó antes o en el timestamp, es la respuesta
        (era vigente en ese momento). Si current se creó después,
        recorre supersedes hacia atrás hasta encontrar la primera
        versión con created_at <= timestamp.
        """
        v = self.current
        if v.created_at <= timestamp:
            return v

        best: FactVersion | None = None
        while v.supersedes is not None:
            v = self._versions.get(v.supersedes)
            if v is None:
                break
            if v.created_at <= timestamp:
                return v
        return best

    def add_version(self, version: FactVersion) -> None:
        """Añade una nueva versión como vigente.

        Transaccional: o se completa correctamente o no hay cambios visibles.
        """
        if version.fact_id != self._fact_id:
            msg = f"Version fact_id '{version.fact_id}' != history fact_id '{self._fact_id}'"
            raise ValueError(msg)
        if version.version_id in self._versions:
            msg = f"Version '{version.version_id}' already exists"
            raise KeyError(msg)
        if version.created_at < self._created:
            msg = "Version created_at cannot be before history creation"
            raise ValueError(msg)

        # Marcar la versión anterior como SUPERSEDED
        old_current = self._versions.get(self._current)
        if old_current is not None and old_current.state == VersionState.CURRENT:
            old_superseded = FactVersion(
                version_id=old_current.version_id,
                fact_id=old_current.fact_id,
                confidence=old_current.confidence,
                evidence_ids=old_current.evidence_ids,
                provenance=old_current.provenance,
                created_at=old_current.created_at,
                supersedes=old_current.supersedes,
                state=VersionState.SUPERSEDED,
            )
            self._versions[old_current.version_id] = old_superseded

        # Vincular la nueva versión a la que reemplaza
        new_version = FactVersion(
            version_id=version.version_id,
            fact_id=version.fact_id,
            confidence=version.confidence,
            evidence_ids=version.evidence_ids,
            provenance=version.provenance,
            created_at=version.created_at,
            supersedes=self._current if old_current is not None and version.supersedes is None else version.supersedes,
            state=version.state,
        )

        self._versions[new_version.version_id] = new_version
        self._current = new_version.version_id
        self._updated = new_version.created_at

    def rollback(self, version_id: str) -> FactVersion:
        """Reasigna current a una versión anterior. NO altera el pasado.

        La versión restaurada pasa a CURRENT.
        La versión que era current pasa a ROLLED_BACK.
        """
        target = self._versions.get(version_id)
        if target is None:
            msg = f"Version '{version_id}' not found"
            raise KeyError(msg)
        if target.state == VersionState.TOMBSTONE:
            msg = "Cannot rollback to a tombstone version"
            raise ValueError(msg)

        old_current = self.current
        old_rolled = FactVersion(
            version_id=old_current.version_id,
            fact_id=old_current.fact_id,
            confidence=old_current.confidence,
            evidence_ids=old_current.evidence_ids,
            provenance=old_current.provenance,
            created_at=old_current.created_at,
            supersedes=old_current.supersedes,
            state=VersionState.ROLLED_BACK,
        )
        self._versions[old_current.version_id] = old_rolled

        restored = FactVersion(
            version_id=target.version_id,
            fact_id=target.fact_id,
            confidence=target.confidence,
            evidence_ids=target.evidence_ids,
            provenance=target.provenance,
            created_at=target.created_at,
            supersedes=target.supersedes,
            state=VersionState.CURRENT,
        )
        self._versions[target.version_id] = restored
        self._current = target.version_id
        self._updated = target.created_at
        return restored

    def tombstone(self, version: FactVersion) -> None:
        """Marca el hecho como obsoleto (DELETE lógico)."""
        if version.fact_id != self._fact_id:
            msg = "Version fact_id mismatch"
            raise ValueError(msg)
        if version.version_id in self._versions:
            msg = f"Version '{version.version_id}' already exists"
            raise KeyError(msg)

        old_current = self._versions.get(self._current)
        if old_current is not None and old_current.state == VersionState.CURRENT:
            old_superseded = FactVersion(
                version_id=old_current.version_id,
                fact_id=old_current.fact_id,
                confidence=old_current.confidence,
                evidence_ids=old_current.evidence_ids,
                provenance=old_current.provenance,
                created_at=old_current.created_at,
                supersedes=old_current.supersedes,
                state=VersionState.SUPERSEDED,
            )
            self._versions[old_current.version_id] = old_superseded

        self._versions[version.version_id] = version
        self._current = version.version_id
        self._updated = version.created_at

    def versions(self) -> dict[str, FactVersion]:
        return dict(self._versions)

    # ── Factory ──────────────────────────────────────

    @classmethod
    def create(cls, fact: Fact, version: FactVersion) -> FactHistory:
        return cls(fact, version)

    # ── Serialización (para pruebas) ─────────────────

    def to_dict(self) -> dict:
        """Serialización canónica.

        Orden determinado: versiones ordenadas por created_at,
        tombstones ordenadas por removed_at. Esto garantiza que
        el mismo historial → mismo dict → mismo checksum,
        independientemente del orden de inserción en memoria.
        """
        sorted_versions = sorted(self._versions.values(), key=lambda v: v.created_at)
        sorted_tombstones = sorted(self._tombstones.values(), key=lambda t: t.removed_at)

        return {
            "schema_version": "1",
            "fact_id": self._fact_id,
            "current": self._current,
            "versions": [
                {
                    "version_id": v.version_id,
                    "fact_id": v.fact_id,
                    "confidence": v.confidence,
                    "evidence_ids": list(v.evidence_ids),
                    "provenance": list(v.provenance),
                    "created_at": v.created_at,
                    "supersedes": v.supersedes,
                    "state": v.state.value,
                }
                for v in sorted_versions
            ],
            "tombstones": [
                {
                    "fact_id": t.fact_id,
                    "removed_at": t.removed_at,
                    "reason": t.reason,
                    "version_id": t.version_id,
                }
                for t in sorted_tombstones
            ],
            "created": self._created,
            "updated": self._updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FactHistory:
        from motor.core.fusion.models import Fact, FactTombstone, FactVersion, VersionState

        raw_versions = data.get("versions", {})
        if isinstance(raw_versions, list):
            versions = {
                v["version_id"]: FactVersion(
                    version_id=v["version_id"],
                    fact_id=v["fact_id"],
                    confidence=v["confidence"],
                    evidence_ids=tuple(v.get("evidence_ids", [])),
                    provenance=tuple(v.get("provenance", [])),
                    created_at=v["created_at"],
                    supersedes=v.get("supersedes"),
                    state=VersionState(v.get("state", "current")),
                )
                for v in raw_versions
            }
        else:
            # formato legacy: dict de version_id -> version
            versions = {
                vid: FactVersion(
                    version_id=v["version_id"],
                    fact_id=v["fact_id"],
                    confidence=v["confidence"],
                    evidence_ids=tuple(v.get("evidence_ids", [])),
                    provenance=tuple(v.get("provenance", [])),
                    created_at=v["created_at"],
                    supersedes=v.get("supersedes"),
                    state=VersionState(v.get("state", "current")),
                )
                for vid, v in raw_versions.items()
            }
        first_vid = min(versions.keys(), key=lambda k: versions[k].created_at)
        first_v = versions[first_vid]

        # Construir historia sin pasar por el constructor (que exige CURRENT)
        fact = Fact(fact_id=data["fact_id"], subject="", predicate="", object="")
        history = cls.__new__(cls)
        history._fact_id = fact.fact_id
        history._current = first_v.version_id
        history._versions = {}
        history._tombstones = {}
        history._created = data.get("created", first_v.created_at)
        history._updated = data.get("updated", first_v.created_at)

        # Añadir versiones preservando estados originales
        # current es: 1) la única CURRENT, o 2) la TOMBSTONE, o 3) la más reciente
        for vid, v in sorted(versions.items(), key=lambda kv: kv[1].created_at):
            history._versions[vid] = v
            if v.state == VersionState.CURRENT:
                history._current = v.version_id
        # Si ninguna versión tiene CURRENT, buscar TOMBSTONE
        if history._current == first_v.version_id:
            for _vid, v in sorted(versions.items(), key=lambda kv: kv[1].created_at):
                if v.state == VersionState.TOMBSTONE:
                    history._current = v.version_id
                    break

        raw_tombstones = data.get("tombstones", {})
        if isinstance(raw_tombstones, list):
            history._tombstones = {
                t["version_id"] or f"ts_{i}": FactTombstone(**t) for i, t in enumerate(raw_tombstones)
            }
        else:
            history._tombstones = {tid: FactTombstone(**t) for tid, t in raw_tombstones.items()}
        return history
