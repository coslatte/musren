import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.credentials import CredentialStore, KeyringCredentialStore

CONFIG_DIR = Path.home() / ".musren"
CONFIG_FILE = CONFIG_DIR / "config.json"

VALID_KEYS = {
    "acoustid": "AcoustID API key for audio recognition",
    "shazam": "Shazam API credentials (future)",
    "musicbrainz": "MusicBrainz credentials (future)",
    "lastfm": "Last.fm API key (future)",
}

DEFAULT_SETTINGS = {
    "theme": "dark",
    "auto_confirm": False,
    "recursive": False,
}


class ConfigManager:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        credential_store: Optional[CredentialStore] = None,
    ):
        self.config_path = config_path or CONFIG_FILE
        self.config_dir = self.config_path.parent
        self.credential_store = credential_store or KeyringCredentialStore()
        self._config: Dict[str, Any] = {}
        self._load_error: Optional[str] = None
        self._load()

    def _load(self) -> None:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            self._config = {}
            return
        except json.JSONDecodeError as error:
            self._config = {}
            self._load_error = f"Invalid JSON ({error})"
            return
        except OSError as error:
            self._config = {}
            self._load_error = f"Could not read the file ({error})"
            return

        if (
            not isinstance(config, dict)
            or not isinstance(config.get("keys", {}), dict)
            or not isinstance(config.get("settings", {}), dict)
        ):
            self._config = {}
            self._load_error = (
                "Expected a JSON object with object-valued 'keys' and 'settings'"
            )
            return

        self._config = config

    def _ensure_writable(self) -> None:
        if self._load_error:
            raise OSError(
                f"Cannot update configuration at {self.config_path}: "
                f"{self._load_error}. Repair the file or explicitly clear the configuration."
            )

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _save(self) -> None:
        self._ensure_writable()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        if key in VALID_KEYS:
            legacy_keys = self._config.get("keys", {})
            if key in legacy_keys and legacy_keys[key] is not None:
                # 2026-11-09: migra credenciales legadas solo tras verificar el llavero.
                value = legacy_keys[key]
                if not isinstance(value, str):
                    raise OSError(f"Legacy credential '{key}' is not text.")
                self.credential_store.set_password(key, value)
                del legacy_keys[key]
                if not legacy_keys:
                    self._config.pop("keys", None)
                try:
                    self._save()
                except OSError as error:
                    legacy_keys[key] = value
                    self._config["keys"] = legacy_keys
                    raise OSError(
                        f"Credential '{key}' was stored securely, but its legacy "
                        "plaintext copy could not be removed."
                    ) from error
                return value
            return self.credential_store.get_password(key) or default
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        self._ensure_writable()
        if key in VALID_KEYS:
            self.credential_store.set_password(key, value)
            legacy_keys = self._config.get("keys", {})
            if key in legacy_keys:
                previous = legacy_keys.pop(key)
                if not legacy_keys:
                    self._config.pop("keys", None)
                try:
                    self._save()
                except OSError:
                    legacy_keys[key] = previous
                    self._config["keys"] = legacy_keys
                    raise
        else:
            self._config[key] = value
        self._save()
        return True

    def delete(self, key: str) -> bool:
        self._ensure_writable()
        if key in VALID_KEYS:
            deleted = self.credential_store.delete_password(key)
            legacy_keys = self._config.get("keys", {})
            if key in legacy_keys:
                previous = legacy_keys.pop(key)
                if not legacy_keys:
                    self._config.pop("keys", None)
                try:
                    self._save()
                except OSError:
                    legacy_keys[key] = previous
                    self._config["keys"] = legacy_keys
                    raise
                deleted = True
            return deleted
        if key in self._config:
            del self._config[key]
            self._save()
            return True
        return False

    def list_keys(self) -> Dict[str, str]:
        return {key: "Configured" for key in VALID_KEYS if self.get(key) is not None}

    def list_all(self) -> Dict[str, Any]:
        result = dict(self._config)
        result.pop("keys", None)
        result["configured_keys"] = list(self.list_keys())
        result["_valid_keys"] = list(VALID_KEYS.keys())
        return result

    def clear(self) -> bool:
        for key in VALID_KEYS:
            self.credential_store.delete_password(key)
        try:
            self.config_path.unlink()
        except FileNotFoundError:
            pass
        self._config = {}
        self._load_error = None
        return True

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._config.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> bool:
        self._ensure_writable()
        if "settings" not in self._config:
            self._config["settings"] = {}
        self._config["settings"][key] = value
        self._save()
        return True


_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
