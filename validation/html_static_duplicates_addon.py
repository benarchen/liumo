"""C26 fixed selector; only matching declarations may be compared in memory."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation import html_static_session as runtime
from validation.html_static_addon import HtmlStaticAddon


class HtmlStaticDuplicatesAddon(HtmlStaticAddon):
    def select_runtime(self):
        runtime.select_duplicate_mode()
        runtime.select_runtime()


addons = [HtmlStaticDuplicatesAddon()]
