from pathlib import Path

import magic

MIME_TO_EXTRACTOR: dict[str, str] = {
    "text/html": "html",
    "text/xml": "html",
    "application/pdf": "pdf",
    "image/jpeg": "imagen",
    "image/png": "imagen",
    "image/gif": "imagen",
    "image/webp": "imagen",
    "image/tiff": "imagen",
    "image/svg+xml": "imagen",
    "video/mp4": "video",
    "video/x-matroska": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "video/x-msvideo": "video",
    "audio/mpeg": "audio",
    "audio/ogg": "audio",
    "audio/wav": "audio",
    "audio/flac": "audio",
    "audio/aac": "audio",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "office",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "office",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "office",
    "application/msword": "office",
    "application/vnd.ms-excel": "office",
    "application/vnd.ms-powerpoint": "office",
    "application/vnd.oasis.opendocument.text": "office",
    "text/plain": "texto",
    "text/csv": "texto",
    "application/json": "texto",
    "application/zip": "office",  # docx/xlsx/pptx son ZIP internamente
}

TIPO_EXTRACTORES = sorted(set(MIME_TO_EXTRACTOR.values()))


def detectar_tipo(ruta: Path) -> str:
    if not ruta.exists() or not ruta.is_file():
        return "desconocido"
    mime = magic.from_file(str(ruta), mime=True)
    for prefix, extractor in MIME_TO_EXTRACTOR.items():
        if mime == prefix or mime.startswith(prefix):
            return extractor
    return "desconocido"


def detectar_mime(ruta: Path) -> str:
    if not ruta.exists() or not ruta.is_file():
        return "application/octet-stream"
    return magic.from_file(str(ruta), mime=True)
