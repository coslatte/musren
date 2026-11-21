"""Network connectivity checks used by remote audio providers."""


def check_internet_connection(timeout: float = 2) -> bool:
    """Return whether a connection to a public HTTPS port is available."""
    import socket

    hosts = (
        ("one.one.one.one", 443),
        ("google.com", 443),
        ("cloudflare.com", 443),
    )
    for host, port in hosts:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (OSError, socket.gaierror):
            continue
    return False
