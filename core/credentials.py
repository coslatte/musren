"""OS-backed credentials shared by musren's command-line interfaces."""

from typing import Optional, Protocol


class CredentialStoreError(OSError):
    """Report an unavailable, unsupported, or locked system credential store."""


class CredentialStore(Protocol):
    """Small credential interface used by configuration and job adapters."""

    def get_password(self, name: str) -> Optional[str]: ...

    def set_password(self, name: str, value: str) -> None: ...

    def delete_password(self, name: str) -> bool: ...


class KeyringCredentialStore:
    """Use only the native OS keychain or desktop secret service backends."""

    service_name = "musren"
    allowed_backend_modules = {
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
    }

    def _keyring(self):
        try:
            import keyring

            backend = keyring.get_keyring()
            priority = backend.priority
        except Exception as error:
            raise CredentialStoreError(
                "The OS credential store is unavailable or locked. On Linux, "
                "start and unlock Secret Service or KWallet."
            ) from error

        if (
            priority <= 0
            or type(backend).__module__ not in self.allowed_backend_modules
        ):
            raise CredentialStoreError(
                "No supported OS credential store is available. On Linux, "
                "start and unlock Secret Service or KWallet."
            )
        return keyring

    def get_password(self, name: str) -> Optional[str]:
        keyring = self._keyring()
        try:
            return keyring.get_password(self.service_name, name)
        except Exception as error:
            raise CredentialStoreError(
                "Could not read the credential from the OS credential store."
            ) from error

    def set_password(self, name: str, value: str) -> None:
        keyring = self._keyring()
        try:
            keyring.set_password(self.service_name, name, value)
            if keyring.get_password(self.service_name, name) != value:
                raise CredentialStoreError(
                    "The OS credential store did not verify the saved credential."
                )
        except CredentialStoreError:
            raise
        except Exception as error:
            raise CredentialStoreError(
                "Could not save the credential in the OS credential store."
            ) from error

    def delete_password(self, name: str) -> bool:
        keyring = self._keyring()
        try:
            if keyring.get_password(self.service_name, name) is None:
                return False
            keyring.delete_password(self.service_name, name)
            if keyring.get_password(self.service_name, name) is not None:
                raise CredentialStoreError(
                    "The OS credential store did not verify credential removal."
                )
            return True
        except CredentialStoreError:
            raise
        except Exception as error:
            raise CredentialStoreError(
                "Could not remove the credential from the OS credential store."
            ) from error
