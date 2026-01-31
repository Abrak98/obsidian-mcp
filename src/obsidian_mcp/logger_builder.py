import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root by walking up to pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()
_LOG_BASE_DIR = _PROJECT_ROOT / "logs"


def get_logger(name: str) -> logging.Logger:
    """Create and return a configured logger.

    Log directory: logs/{LOG_DIR_NAME}/.
    LOG_DIR_NAME is read from env. Set it in your entrypoint before imports:
        os.environ["LOG_DIR_NAME"] = "my_script"
        os.environ["LOG_DIR_NAME"] = "evolution/20260202_182653_abc123"
    If not set, falls back to "default".

    In test mode (pytest): StreamHandler only.
    In normal mode: module log + common.log + errors.log + console.

    Args:
        name: Logger name (typically __name__).
    """
    py_logger = logging.getLogger(name)
    if py_logger.handlers:
        return py_logger

    py_logger.setLevel(logging.INFO)
    is_test = "pytest" in sys.modules

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if is_test:
        handler: logging.Handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        py_logger.addHandler(handler)
        return py_logger

    dir_name = os.environ.get("LOG_DIR_NAME", "default")
    log_dir = _LOG_BASE_DIR / dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    # Module-specific log
    module_log = log_dir / f"{name.replace('.', '_')}.log"
    module_handler = logging.handlers.RotatingFileHandler(
        str(module_log),
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    module_handler.setFormatter(formatter)
    py_logger.addHandler(module_handler)

    # Common log (all modules write here)
    common_handler = logging.handlers.RotatingFileHandler(
        str(log_dir / "common.log"),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    common_handler.setFormatter(formatter)
    py_logger.addHandler(common_handler)

    # Error-only log
    error_handler = logging.handlers.RotatingFileHandler(
        str(log_dir / "errors.log"),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    py_logger.addHandler(error_handler)

    # Console (critical for Docker/terminal visibility, skip in Jupyter)
    is_jupyter = "ipykernel" in sys.modules
    if not is_jupyter:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        py_logger.addHandler(console_handler)

    return py_logger
