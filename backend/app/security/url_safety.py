"""SSRF defenses for outbound HTTP fetches (web research).

Default: https:// only, public hosts, no private/link-local/metadata IPs,
no file:// / ftp://, and redirects that leave the allowlist are blocked.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Cloud / instance metadata hosts commonly targeted for SSRF.
_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
        "kubernetes.default",
        "kubernetes.default.svc",
    }
)

# Render / AWS / Azure / GCP metadata IPs (and localhost variants).
_BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT / carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6 (check mapped below too)
)


class UnsafeURLError(ValueError):
    """Raised when a URL must not be fetched."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Unwrap IPv4-mapped IPv6 (::ffff:a.b.c.d) so private v4 cannot sneak in.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def assert_safe_public_https_url(
    url: str,
    *,
    allowed_hostnames: frozenset[str] | None = None,
) -> str:
    """Validate `url` for outbound fetch. Returns the normalized URL string.

    Raises UnsafeURLError on any blocked scheme/host/IP.
    """
    raw = (url or "").strip()
    if not raw:
        raise UnsafeURLError("Empty URL")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        raise UnsafeURLError(f"Only https:// URLs are allowed (got {scheme or 'none'})")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeURLError("URL missing hostname")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
        raise UnsafeURLError(f"Blocked hostname: {host}")
    if allowed_hostnames is not None and host not in allowed_hostnames:
        raise UnsafeURLError(f"Hostname not on allowlist: {host}")

    # Literal IP in the URL (e.g. https://127.0.0.1/...).
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_blocked_ip(literal_ip):
        raise UnsafeURLError(f"Blocked IP address: {host}")

    # Resolve DNS and reject private answers (defense against DNS rebinding
    # at fetch time; still check again after connect if needed).
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host: {host}") from exc

    if not infos:
        raise UnsafeURLError(f"Could not resolve host: {host}")

    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"Host resolves to blocked address: {addr}")

    return raw
