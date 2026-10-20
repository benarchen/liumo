"""Default-disabled C17 adapter, one target and one candidate only."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation.compat_addon import CompatibilityAddon
from validation.functional_capture import ArticleCandidateSession, select_runtime


class FunctionalAddon(CompatibilityAddon):
    def select_runtime(self):
        select_runtime()

    def make_session(self):
        return ArticleCandidateSession()


addons = [FunctionalAddon()]
