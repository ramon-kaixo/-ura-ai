import logging

log = logging.getLogger("ura.diagnostico.correlacion")

DEPENDENCIAS = {
    "docker": ["container_searxng", "container_n8n", "container_qdrant"],
    "sshd": ["red"],
    "qdrant": ["diagnostico"],
    "exit_node_offline": ["red", "internet"],
}


def agrupar_incidentes(tags: list, hw_ok: bool = True, hw_issues: list | None = None) -> list:
    """Agrupa tags en correlaciones con causa raíz y servicios afectados."""
    grupos = []
    procesados = set()
    if not hw_ok and hw_issues:
        grupos.append(
            {
                "causa_raiz": "hardware",
                "sintomas": hw_issues,
                "servicios_afectados": ["sshd", "docker"],
            },
        )
        procesados.add("hw_issue")
    for tag in tags:
        if tag in procesados:
            continue
        if tag in DEPENDENCIAS:
            grupos.append(
                {
                    "causa_raiz": tag,
                    "sintomas": [f"{tag} afectado"],
                    "servicios_afectados": DEPENDENCIAS[tag],
                },
            )
        elif tag != "hw_issue":
            grupos.append(
                {
                    "causa_raiz": tag,
                    "sintomas": [f"{tag} detectado"],
                    "servicios_afectados": [tag],
                },
            )
        procesados.add(tag)
    return grupos


def resumir_incidentes(incidentes: list) -> str:
    """Genera resumen textual de una lista de incidentes."""
    if not incidentes:
        return "Sin incidencias activas"
    tipos = {i.get("tipo", "Unknown") for i in incidentes}
    subs = [i.get("subtipo", "") for i in incidentes if i.get("subtipo")]
    resumen = f"{len(incidentes)} incidencia(s): {', '.join(tipos)}"
    if subs:
        resumen += f" [{', '.join(subs[:5])}]"
    return resumen
