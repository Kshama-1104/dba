import ipaddress
import os
import socket
from typing import List
from urllib.parse import urlsplit


class SSRFProtectionError(Exception):
    """Raised when a URL violates SSRF security boundaries."""
    pass


# Private, link-local, loopback, and cloud metadata network blocks
BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),      # Carrier-Grade NAT
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local / Cloud Metadata (AWS/GCP/Azure)
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),      # Network Benchmark Tests
    ipaddress.ip_network("198.51.100.0/24"),    # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),     # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
]

BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("fc00::/7"),           # Unique Local (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("ff00::/8"),           # Multicast
]


def validate_destination_url(url: str, allow_insecure_http: bool = False) -> str:
    """
    Validate a destination URL against SSRF threats.
    
    Ensures:
    1. Scheme is https (or http if allow_insecure_http=True).
    2. No embedded userinfo (e.g. user:pass@domain).
    3. Hostname exists.
    4. Hostname resolves to public IP addresses only (blocking loopback, RFC1918, metadata).
    5. Handles IPv4-mapped IPv6 addresses.
    
    Returns normalized clean base URL string (without trailing slash).
    Raises SSRFProtectionError on any security violation.
    """
    if not url or not isinstance(url, str):
        raise SSRFProtectionError("Destination URL cannot be empty.")

    clean_url = url.strip()
    try:
        parsed = urlsplit(clean_url)
    except Exception as exc:
        raise SSRFProtectionError(f"Malformed URL: {exc}") from exc

    # 1. Scheme check
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SSRFProtectionError(f"Invalid URL scheme '{scheme}'. Only HTTP/HTTPS allowed.")

    if scheme == "http" and not allow_insecure_http:
        # Check environment flag for dev/testing
        env_allow = os.getenv("ALLOW_INSECURE_HTTP_FOR_DEV", "").lower() in ("true", "1", "yes")
        if not env_allow:
            raise SSRFProtectionError("Insecure HTTP is forbidden. Destination must use HTTPS.")

    # 2. Userinfo check
    if parsed.username or parsed.password:
        raise SSRFProtectionError("Embedded userinfo (user:pass@) in destination URL is forbidden.")

    # 3. Hostname check
    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("Destination URL missing valid hostname.")

    hostname = hostname.strip().lower()

    # Reject known loopback keywords directly
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if not (scheme == "http" and allow_insecure_http):
            raise SSRFProtectionError(f"Direct connection to loopback host '{hostname}' is blocked.")

    # 4. Resolve DNS and validate all returned IP addresses
    port = parsed.port or (443 if scheme == "https" else 80)
    
    # If hostname is already an IP address literal, validate directly
    try:
        ip_obj = ipaddress.ip_address(hostname)
        _validate_ip_address(ip_obj, allow_insecure_http)
        return clean_url.rstrip("/")
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # Resolve all A / AAAA records
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFProtectionError(f"DNS resolution failed for host '{hostname}': {exc}") from exc

    if not addr_info:
        raise SSRFProtectionError(f"No IP addresses resolved for host '{hostname}'.")

    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            _validate_ip_address(ip_obj, allow_insecure_http)
        except ValueError as exc:
            raise SSRFProtectionError(f"Invalid IP address resolved '{ip_str}': {exc}") from exc

    return clean_url.rstrip("/")


def _validate_ip_address(ip_obj: ipaddress._BaseAddress, allow_insecure_http: bool = False) -> None:
    """Validate a single IP address against blocked networks."""
    # Check IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped

    if allow_insecure_http and ip_obj.is_loopback:
        return  # Permitted in explicit test/dev mode

    # Check loopback
    if ip_obj.is_loopback:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} is a loopback address and blocked.")

    # Check IPv4 blocks
    if isinstance(ip_obj, ipaddress.IPv4Address):
        for net in BLOCKED_IPV4_NETWORKS:
            if ip_obj in net:
                raise SSRFProtectionError(f"Resolved IP {ip_obj} falls in blocked network {net}.")

    # Check IPv6 blocks
    elif isinstance(ip_obj, ipaddress.IPv6Address):
        for net in BLOCKED_IPV6_NETWORKS:
            if ip_obj in net:
                raise SSRFProtectionError(f"Resolved IP {ip_obj} falls in blocked network {net}.")

    # General properties
    if ip_obj.is_private and not allow_insecure_http:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} is a private network address and blocked.")

    if ip_obj.is_link_local:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} is a link-local address and blocked.")

    if ip_obj.is_multicast:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} is a multicast address and blocked.")
