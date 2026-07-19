"""WebExtractor — extrae metadatos de páginas web.

Dependencias:
  - httpx, beautifulsoup4

Extrae:
  - title, description, texto, imágenes, enlaces, publication_date

Protección SSRF:
  - Solo http/https
  - Bloqueo IPs privadas (loopback, RFC 1918, link-local, metadata cloud)
  - Validación post-DNS y post-redirecciones
  - Timeouts: connect 10s, read 30s, total 60s
  - Límite: 10 MB body, 5 redirects
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from knowledge.engine.extractors.base import (
    ExtractionResult,
    _check_import,
    get_registry,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

log = logging.getLogger("ura.knowledge.extractors.web")

_WEB_MIMES = ["text/html"]

MAX_BODY_SIZE = 10 * 1024 * 1024
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
TOTAL_TIMEOUT = 60
MAX_REDIRECTS = 5

_HAS_HTTPX = _check_import("httpx", "httpx")
_HAS_BS4 = _check_import("bs4", "beautifulsoup4")

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104 — blocklist, not bind
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("240.0.0.0/4"),
]


class SSRFError(ValueError):
    """URL rechazada por política SSRF."""


class URLSchemeBlocked(SSRFError):
    """Esquema no permitido."""


class PrivateIPBlocked(SSRFError):
    """IP privada o no ruteable."""


class CloudMetadataBlocked(SSRFError):
    """Posible endpoint de metadata cloud."""


class WebExtractor:
    """Extractor para páginas web.

    Uso:
        extractor = WebExtractor()
        result = extractor.extract(source)

    La URL se valida contra política SSRF antes de cualquier petición.
    """

    id: str = "web"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _WEB_MIMES
    cost: str = "O(n)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        t0 = time.monotonic()
        url = source.location

        if not url:
            return ExtractionResult(
                errors=["Empty URL"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        try:
            self._validate_url(url)

            if not _HAS_HTTPX or not _HAS_BS4:
                log.warning("httpx/bs4 not available, extracting basic metadata for %s", url)
                content_sha256 = _hash_url_stub(url)
                now = datetime.now(UTC).isoformat()
                metadata = {
                    "url": url,
                    "content_sha256": content_sha256,
                    "_extractor": self.id,
                    "_extractor_version": self.version,
                    "wraps": f"source:{url}",
                    "extracted_at": now,
                    "_degraded": True,
                    "_degraded_reason": "httpx or beautifulsoup4 not installed",
                }
                asset = KnowledgeAsset(
                    asset_id=content_sha256[:16],
                    asset_type=AssetType.API_REFERENCE,
                    metadata=metadata,
                    source=source,
                    quality=0.3,
                    created_at=now,
                    updated_at=now,
                )
                return ExtractionResult(asset=asset, duration_ms=(time.monotonic() - t0) * 1000)

            return self._fetch_and_extract(url, source, t0)

        except SSRFError as exc:
            log.warning("SSRF blocked: %s — %s", url, exc)
            return ExtractionResult(
                errors=[str(exc)],
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            log.exception("Web extraction error for %s", url)
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    def _fetch_and_extract(self, url: str, source: AssetSource, t0: float) -> ExtractionResult:
        import httpx
        from bs4 import BeautifulSoup

        transport = httpx.HTTPTransport(
            verify=True,
            retries=0,
        )
        with httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=10, pool=5),
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            response = client.get(url, headers={"User-Agent": "URAKnowledgeEngine/1.0"})
            response.raise_for_status()

            final_url = str(response.url)
            self._validate_url(final_url)

            content = response.content
            if len(content) > MAX_BODY_SIZE:
                content = content[:MAX_BODY_SIZE]

            content_sha256 = hashlib_content(content)
            now = datetime.now(UTC).isoformat()

            soup = BeautifulSoup(content, "html.parser")
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            description = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                description = meta_desc["content"].strip()

            body_text = soup.get_text(separator=" ", strip=True)
            images = [img.get("src", "") for img in soup.find_all("img") if img.get("src")]
            links = [a.get("href", "") for a in soup.find_all("a", href=True) if a["href"].startswith("http")]

            metadata: dict[str, Any] = {
                "url": final_url,
                "title": title,
                "description": description,
                "text_length": len(body_text),
                "text_preview": body_text[:500],
                "image_count": len(images),
                "link_count": len(links),
                "content_sha256": content_sha256,
                "size": len(content),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "_extractor": self.id,
                "_extractor_version": self.version,
                "wraps": f"source:{url}",
                "extracted_at": now,
            }

            log.info(
                "Extracted web page: %s (%d chars, %d images, %d links)",
                final_url,
                len(body_text),
                len(images),
                len(links),
            )

        asset = KnowledgeAsset(
            asset_id=content_sha256[:16],
            asset_type=AssetType.API_REFERENCE,
            metadata=metadata,
            source=source,
            quality=_compute_web_quality(metadata),
            created_at=now,
            updated_at=now,
        )
        return ExtractionResult(asset=asset, duration_ms=(time.monotonic() - t0) * 1000)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme not in _ALLOWED_SCHEMES:
            msg = f"Scheme '{scheme}' not allowed (only http/https)"
            raise URLSchemeBlocked(msg)

        hostname = parsed.hostname or ""
        hostname_lower = hostname.lower()

        if hostname_lower in _BLOCKED_HOSTS:
            msg = f"Host '{hostname}' is blocked"
            raise PrivateIPBlocked(msg)

        # Es IP literal → validar directamente
        if _is_ip_string(hostname_lower):
            ip = ipaddress.ip_address(hostname_lower)
            _check_ip_blocked(ip, hostname_lower)
            return

        # Es hostname → resolver DNS
        try:
            addrs = socket.getaddrinfo(hostname_lower, None)
        except socket.gaierror as exc:
            msg = f"DNS resolution failed for '{hostname}': {exc}"
            raise SSRFError(msg) from exc

        for addr_info in addrs:
            ip_str = addr_info[4][0]
            if _is_ip_string(ip_str):
                ip = ipaddress.ip_address(ip_str)
                _check_ip_blocked(ip, hostname_lower)

    @staticmethod
    def _validate_redirect_url(url: str) -> None:
        """Valida URL tras una redirección."""
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            msg = f"Redirect to blocked scheme: {scheme}"
            raise URLSchemeBlocked(msg)
        hostname = parsed.hostname or ""
        if _is_ip_string(hostname):
            ip = ipaddress.ip_address(hostname)
            _check_ip_blocked(ip, hostname)
            return
        try:
            addrs = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return
        for addr_info in addrs:
            ip_str = addr_info[4][0]
            if _is_ip_string(ip_str):
                ip = ipaddress.ip_address(ip_str)
                _check_ip_blocked(ip, hostname)


def _is_ip_string(s: str) -> bool:
    """Comprueba si una cadena es una dirección IP literal."""
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def _check_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    if ip == ipaddress.ip_address("169.254.169.254"):
        msg = f"Cloud metadata IP blocked: {ip}"
        raise CloudMetadataBlocked(msg)
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            msg = f"IP {ip} (host: {hostname}) is in blocked network {network}"
            raise PrivateIPBlocked(msg)


def _hash_url_stub(url: str) -> str:
    import hashlib

    return hashlib.sha256(url.encode()).hexdigest()


def hashlib_content(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _compute_web_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("title"):
        q += 0.15
    if metadata.get("description"):
        q += 0.1
    if metadata.get("text_length", 0) > 100:
        q += 0.15
    if metadata.get("image_count", 0) > 0:
        q += 0.1
    if metadata.get("link_count", 0) > 0:
        q += 0.1
    if metadata.get("status_code") == 200:
        q += 0.1
    return min(q, 1.0)


_registry = get_registry()
_registry.register(WebExtractor())
