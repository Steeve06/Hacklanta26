import os


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def load_dotenv_file() -> None:
    """Read the repo-root .env for commands run outside Docker. Real environment variables win.
    Tests never read it, so a local .env can't point them at another database."""
    import sys
    from pathlib import Path

    if "pytest" in sys.modules:
        return

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
