"""Entropy AI - Agentic Operating System & Desktop Interface for Antigravity."""

from pathlib import Path as _Path

__app_name__ = "Entropy AI"

#: Kurulum yoksa (kaynaktan/`.exe` içinden koşum) `pyproject.toml` okunur;
#: o da yoksa bu yedek kullanılır. Sürümün TEK kaynağı `pyproject.toml`dur.
_FALLBACK_VERSION = "0.10.3"


def _read_pyproject_version() -> str | None:
    """Depo kökündeki `pyproject.toml`dan `[project] version` okur."""
    root = _Path(__file__).resolve().parents[2]
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        try:
            import tomllib  # Python 3.11+
        except ModuleNotFoundError:  # pragma: no cover
            return None
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        version = ((data.get("project") or {}).get("version") or "").strip()
        return version or None
    except Exception:  # pragma: no cover - bozuk/okunamayan dosya yedeğe düşer
        return None


def _resolve_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version as _dist_version

        try:
            return _dist_version("entropy-ai")
        except PackageNotFoundError:
            pass
    except Exception:  # pragma: no cover
        pass
    return _read_pyproject_version() or _FALLBACK_VERSION


__version__ = _resolve_version()
