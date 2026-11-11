"""Smoke-test native credential persistence with a disposable secret."""

import secrets

from musren.core.credentials import KeyringCredentialStore


def main() -> None:
    """Write, read, and remove one temporary system credential."""
    store = KeyringCredentialStore()
    name = f"phase6-smoke-{secrets.token_urlsafe(12)}"
    value = secrets.token_urlsafe(32)

    try:
        store.set_password(name, value)
        if store.get_password(name) != value:
            raise RuntimeError("The OS credential store returned a different value.")
    finally:
        store.delete_password(name)

    print("Native credential store smoke passed.")


if __name__ == "__main__":
    main()
