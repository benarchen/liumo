"""C28 fixed, default-disabled selector; no active requests or raw source logs."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation import html_static_session as runtime
from validation.html_static_addon import HtmlStaticAddon


class HtmlInlineAddon(HtmlStaticAddon):
    def select_runtime(self):
        runtime.select_inline_mode()
        runtime.select_runtime()


addons = [HtmlInlineAddon()]
