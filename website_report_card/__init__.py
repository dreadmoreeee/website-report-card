"""One client-friendly website report card built from eight small website checks."""

__version__ = "1.0.0"

from .report import build_report, render_json, render_markdown, render_text  # noqa: E402
from .tools import TOOLS, load_raw, make_target, run_all, save_raw  # noqa: E402

__all__ = ["TOOLS", "build_report", "load_raw", "make_target", "render_json",
           "render_markdown", "render_text", "run_all", "save_raw", "__version__"]
