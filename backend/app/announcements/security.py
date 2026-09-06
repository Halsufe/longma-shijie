from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


class FetchSecurityError(ValueError):
    pass


def validate_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or parts.username or parts.password or not parts.hostname:
        raise FetchSecurityError("unsafe URL")
    host = parts.hostname.rstrip(".").lower()
    if allowed_hosts and host not in {item.rstrip(".").lower() for item in allowed_hosts}:
        raise FetchSecurityError("host is not allow-listed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise FetchSecurityError("DNS resolution failed") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FetchSecurityError("private or reserved address rejected")
    return url


@dataclass(slots=True)
class FetchConfig:
    timeout_seconds: float = 15
    max_retries: int = 2
    max_redirects: int = 3
    max_bytes: int = 5 * 1024 * 1024
    user_agent: str = "LongmaAnnouncementWorker/1.0"


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int
    content: bytes
    content_type: str


class SecureFetcher:
    def __init__(self, config: FetchConfig | None = None, transport=None):
        self.config = config or FetchConfig()
        self.transport = transport

    async def fetch(self, url: str, *, allowed_hosts: set[str] | None = None) -> FetchResult:
        import httpx

        current = validate_url(url, allowed_hosts)
        timeout = httpx.Timeout(self.config.timeout_seconds)
        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={"User-Agent": self.config.user_agent}, transport=self.transport) as client:
                    for _ in range(self.config.max_redirects + 1):
                        response = await client.get(current)
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                break
                            current = validate_url(str(response.url.join(location)), allowed_hosts)
                            continue
                        if response.status_code >= 500 and attempt < self.config.max_retries:
                            break
                        if response.status_code >= 400:
                            raise FetchSecurityError(f"HTTP {response.status_code}")
                        content = response.content
                        if len(content) > self.config.max_bytes:
                            raise FetchSecurityError("response too large")
                        return FetchResult(str(response.url), response.status_code, content, response.headers.get("content-type", ""))
                    else:
                        raise FetchSecurityError("too many redirects")
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt >= self.config.max_retries:
                    raise
                await asyncio.sleep(0)
        raise FetchSecurityError("fetch failed")

