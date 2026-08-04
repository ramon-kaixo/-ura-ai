"""Crawler HTTP basado en httpx.

Obtiene documentos web con validaciones de seguridad:
  - Solo http/https
  - Protección SSRF (bloqueo de IPs privadas por defecto)
  - Límite de tamaño, timeouts, redirects controlados
  - Validación de Content-Type y Content-Length

Retorna metadatos + bytes. Sin parsing del contenido.
"""

from __future__ import annotations

import ipaddress
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx

from motor.core.web.base import Crawler

log = logging.getLogger(__name__)

# Bloques de IP privadas para protección SSRF
_PRIVATE_NETWORKS: list[str] = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "::1/128",
]

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; URA/1.0; +https://github.com/anomalyco/ura) Web Crawler"

_MAX_REDIRECTS = 10
_DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
_DEFAULT_TIMEOUT = 30


@dataclass
class CrawledDocument:
    """Documento bruto obtenido por el crawler.

    Contiene únicamente metadatos + bytes. Sin interpretación.
    """

    url: str
    final_url: str = ""
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    charset: str = ""
    content: bytes = b""
    content_length: int = 0
    elapsed_ms: float = 0.0
    fetch_time: float = field(default_factory=time.time)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "charset": self.charset,
            "content_length": self.content_length,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "error": self.error,
        }


def _is_private_url(url: str) -> bool:
    """Verifica si una URL apunta a una IP privada (protección SSRF)."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if host is None:
            return True
        # Resolver si es nombre de host
        import socket

        try:
            addr = socket.getaddrinfo(host, None)[0][4][0]
        except (socket.gaierror, IndexError, OSError):
            # No se puede resolver — permitir (el error vendrá después)
            return False
        ip = ipaddress.ip_address(addr)
        return any(ip in ipaddress.ip_network(net) for net in _PRIVATE_NETWORKS)
    except Exception:
        return False


def _validate_url(url: str) -> None:
    """Valida que la URL sea segura para crawling."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        msg = f"Scheme '{parsed.scheme}' not allowed. Only http/https."
        raise ValueError(msg)
    if _is_private_url(url):
        msg = f"URL '{url}' points to a private network (SSRF protection). Set allow_private=True to override."
        raise ValueError(
            msg,
        )


class HttpCrawler(Crawler):
    """Crawler HTTP basado en httpx.

    Args:
        timeout: Timeout en segundos (default: 30).
        max_size: Tamaño máximo de respuesta en bytes (default: 10MB).
        max_redirects: Número máximo de redirecciones (default: 10).
        user_agent: User-Agent header.
        allow_private: Permitir IPs privadas (SSRF protection, default: False).
        allowed_content_types: Lista de Content-Type permitidos (default: todos).

    """

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        max_size: int = _DEFAULT_MAX_SIZE,
        max_redirects: int = _MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
        *,
        allow_private: bool = False,
        allowed_content_types: list[str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_size = max_size
        self._max_redirects = max_redirects
        self._user_agent = user_agent
        self._allow_private = allow_private
        self._allowed_content_types = allowed_content_types

    @property
    def name(self) -> str:
        return "httpx"

    def fetch(self, url: str, timeout: int | None = None) -> str:
        """Obtiene el contenido textual de una URL.

        Retorna el texto (decodificado desde content).
        Para acceso a los bytes/metadatos completos, usar fetch_raw().
        """
        doc = self.fetch_raw(url, timeout=timeout)
        if doc.error:
            msg = f"Crawler error: {doc.error}"
            raise RuntimeError(msg)
        try:
            return doc.content.decode(doc.charset or "utf-8", errors="replace")
        except Exception:
            return doc.content.decode("utf-8", errors="replace")

    def fetch_raw(
        self,
        url: str,
        timeout: int | None = None,
    ) -> CrawledDocument:
        """Obtiene una URL y retorna CrawledDocument con metadatos + bytes."""
        if not self._allow_private:
            _validate_url(url)

        t0 = time.monotonic()
        doc = CrawledDocument(url=url, final_url=url)

        try:
            client = httpx.Client(
                timeout=httpx.Timeout(timeout or self._timeout),
                follow_redirects=True,
                max_redirects=self._max_redirects,
                headers={"User-Agent": self._user_agent},
            )

            # HEAD request primero para validar
            head = client.head(url)
            doc.status_code = head.status_code
            doc.headers = dict(head.headers)
            doc.content_type = head.headers.get("content-type", "").split(";")[0].strip()
            doc.charset = _extract_charset(head.headers.get("content-type", ""))

            # Validar Content-Type
            ct = doc.content_type
            if self._allowed_content_types and ct not in self._allowed_content_types:
                doc.error = f"Content-Type '{ct}' not in allowed list"
                doc.elapsed_ms = (time.monotonic() - t0) * 1000
                return doc

            # Validar Content-Length
            cl = head.headers.get("content-length")
            if cl:
                try:
                    if int(cl) > self._max_size:
                        doc.error = f"Content-Length {cl} exceeds max_size {self._max_size}"
                        doc.elapsed_ms = (time.monotonic() - t0) * 1000
                        return doc
                except ValueError:
                    pass

            # GET request para contenido
            r = client.get(url)
            doc.final_url = str(r.url)
            doc.status_code = r.status_code
            doc.headers = dict(r.headers)
            doc.content_type = r.headers.get("content-type", "").split(";")[0].strip()
            doc.charset = _extract_charset(r.headers.get("content-type", ""))
            doc.content = r.content
            doc.content_length = len(r.content)

            if len(r.content) > self._max_size:
                doc.error = f"Response size {len(r.content)} exceeds max_size {self._max_size}"
                doc.content = b""
                doc.content_length = 0

        except httpx.TimeoutException:
            doc.error = "timeout"
        except httpx.TooManyRedirects:
            doc.error = "too_many_redirects"
        except httpx.RequestError as e:
            doc.error = f"request_error: {e}"
        except ValueError as e:
            doc.error = str(e)
        except Exception as e:
            doc.error = f"unexpected: {e}"
            log.warning("crawler unexpected error for %s: %s", url, e)

        doc.elapsed_ms = (time.monotonic() - t0) * 1000
        return doc


def _extract_charset(content_type: str) -> str:
    """Extrae el charset del header Content-Type."""
    for raw in content_type.split(";"):
        token = raw.strip()
        if token.lower().startswith("charset="):
            return token.split("=", 1)[1].strip().lower()
    return ""
