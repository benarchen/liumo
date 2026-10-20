"""Default-off C22: unchanged baseline gates plus fixed public match counts."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation import comment_baseline as baseline
from validation.comment_addon import CommentBaselineAddon


class CommentRefreshAddon(CommentBaselineAddon):
    def select_runtime(self):
        baseline.select_refresh_mode()
        baseline.select_runtime()

    def observe_shape(self, flow, phase):
        if self.session is None:
            return
        self.capture_disabled()
        if self.session.summary()['status'] != 'open':
            return
        category = baseline.comment_match_category(flow.request.url, flow.request.method)
        if category is not None:
            key = 'comment_' + phase + '_' + category
            self.diagnostics[key] = self.diagnostics.get(key, 0) + 1
            self.publish()
        return category

    def requestheaders(self, flow):
        super().requestheaders(flow)
        self.observe_shape(flow, 'requests')

    def responseheaders(self, flow):
        category = self.observe_shape(flow, 'responses')
        if self.session is None:
            return
        flow.response.stream = True
        if self.session.summary()['status'] != 'open':
            return
        if category != 'public_shape_matches':
            self.observe_target_http(flow.request.url, 'responses')
            self.publish()
            return
        super().responseheaders(flow)


addons = [CommentRefreshAddon()]
