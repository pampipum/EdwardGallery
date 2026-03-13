import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
STATE_ROOT = Path(os.getenv("ALPHAARENA_STATE_DIR", WORKSPACE_ROOT / "state"))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir(*parts: str) -> Path:
    path = STATE_ROOT.joinpath(*parts)
    return ensure_dir(path)


def state_file(*parts: str) -> Path:
    parent_parts = parts[:-1]
    if parent_parts:
        ensure_dir(STATE_ROOT.joinpath(*parent_parts))
    return STATE_ROOT.joinpath(*parts)


def config_path() -> Path:
    return Path(os.getenv("ALPHAARENA_CONFIG_PATH", BACKEND_ROOT / "config.json"))


def paper_only_mode() -> bool:
    return os.getenv("ALPHAARENA_PAPER_ONLY", "true").lower() != "false"


def internal_scheduler_enabled() -> bool:
    return os.getenv("ALPHAARENA_ENABLE_INTERNAL_SCHEDULER", "false").lower() == "true"


def auto_resume_enabled() -> bool:
    return os.getenv("ALPHAARENA_ENABLE_AUTO_RESUME", "false").lower() == "true"


def startup_analysis_enabled() -> bool:
    return os.getenv("ALPHAARENA_RUN_STARTUP_ANALYSIS", "false").lower() == "true"
