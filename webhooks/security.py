"""
SSRF protection for outgoing webhooks.

Webhook URLs (and custom headers) are user-controlled. Without a guard, a board
editor could point a webhook at internal-only addresses — cloud metadata
(169.254.169.254), loopback, or private/internal services — and read the
response back from the delivery log. validate_webhook_target() rejects such
targets at save time (nice field error) and again immediately before delivery
(authoritative enforcement, after DNS resolution).

Self-hosted deployments that legitimately deliver to LAN addresses can set
WEBHOOK_ALLOW_PRIVATE_TARGETS = True in settings to bypass the IP checks
(the http/https scheme requirement is always enforced).
"""
import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_SCHEMES = {'http', 'https'}


def _ip_is_internal(ip_str):
    """True if the address is loopback/private/link-local/reserved/etc."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Unparseable address — treat as unsafe.
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_webhook_target(url):
    """
    Raise django.core.exceptions.ValidationError if ``url`` is not a safe
    outbound webhook target. Returns None on success.
    """
    parsed = urlparse(url or '')
    scheme = (parsed.scheme or '').lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            "Webhook URL must use http or https (got '%(scheme)s')." % {'scheme': scheme or 'none'}
        )

    # Scheme is always enforced; IP checks can be disabled for trusted LAN setups.
    if getattr(settings, 'WEBHOOK_ALLOW_PRIVATE_TARGETS', False):
        return

    host = parsed.hostname
    if not host:
        raise ValidationError("Webhook URL has no host.")

    port = parsed.port or (443 if scheme == 'https' else 80)
    try:
        addrinfo = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValidationError("Webhook host '%(host)s' could not be resolved." % {'host': host})

    # Block if ANY resolved address is internal (defends against a hostname that
    # maps to both a public and a private address).
    for *_unused, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if _ip_is_internal(ip_str):
            raise ValidationError(
                "Webhook host '%(host)s' resolves to a private/internal address "
                "(%(ip)s), which is not allowed." % {'host': host, 'ip': ip_str}
            )
