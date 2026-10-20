"""Offline regressions for source boundaries; no account or network access."""

import json
import unittest
from unittest.mock import Mock, patch

from validation.source import BASE, login, parse_weread, review_plan, scan_weread, session_stamp, validate_target, wait_for_session


def payload(*ids, **extra):
    return {"reviews": [{"createTime": 1792160400, "subReviews": [
        {"review": {"reviewId": identity, "mpInfo": {
            "title": "Constructed article", "originalId": "x" * 75, "time": 1792160400}}}
        for identity in ids]}], **extra}


class WeReadDiscoveryTests(unittest.TestCase):
    def test_session_observation_only_uses_owned_origin_cookies(self):
        context = Mock()
        context.cookies.return_value = [{"name": "wr_skey", "value": "private"}]
        self.assertIsNone(session_stamp(context))
        context.cookies.assert_called_once_with(BASE)
        context.cookies.return_value.append({"name": "wr_vid", "value": "other_private"})
        stamp = session_stamp(context)
        self.assertIsInstance(stamp, bytes)
        context.cookies.return_value[0]["value"] = "changed_private"
        self.assertNotEqual(stamp, session_stamp(context))

    def test_session_wait_reports_update_without_claiming_authentication(self):
        context, page = Mock(), Mock()
        page.is_closed.return_value = False
        with patch("validation.source.session_stamp", return_value=b"changed"):
            self.assertEqual(wait_for_session(context, page, b"old"), "session_cookie_updated")
        page.wait_for_timeout.assert_not_called()

    def test_session_timeout_and_window_close_do_not_trigger_api_requests(self):
        context, page = Mock(), Mock()
        page.is_closed.return_value = False
        with patch("validation.source.time.monotonic", side_effect=[0, 0, 2]), \
                patch("validation.source.session_stamp", return_value=None):
            self.assertEqual(wait_for_session(context, page, None, timeout=1), "session_wait_timeout")
        page.wait_for_timeout.assert_called_once_with(500)
        page.is_closed.return_value = True
        self.assertEqual(wait_for_session(context, page, None), "session_window_closed")
        context.request.get.assert_not_called()

    def test_automatic_session_wait_rejects_other_site_before_opening_profile(self):
        with patch("validation.source.profile_path") as profile:
            with self.assertRaises(ValueError):
                login("article", auto_wait=True)
            profile.assert_not_called()

    def test_opaque_id_is_never_promoted_to_a_public_link(self):
        items, count = parse_weread(payload("a", "b"), "MP_WXS_test", "test")
        self.assertEqual((count, len(items)), (1, 2))
        for item in items:
            self.assertIsNone(item["url"])
            self.assertFalse(item["url_verified"])
            self.assertFalse(item["time_verified"])
            self.assertEqual(len(item["original_id"]), 75)

    def test_review_id_is_retained_without_original_id(self):
        data = payload("a")
        del data["reviews"][0]["subReviews"][0]["review"]["mpInfo"]["originalId"]
        items, _ = parse_weread(data, "MP_WXS_test", "test")
        self.assertEqual(items[0]["id"], "a")
        self.assertIsNone(items[0]["original_id"])
        self.assertIsNone(items[0]["url"])

    def test_cross_page_failure_keeps_prior_articles_and_incomplete_coverage(self):
        cursors = []
        def fetch(offset):
            cursors.append(offset)
            return payload("a", "b") if offset == 0 else {"errCode": -2041, "errMsg": "private"}
        result = scan_weread(fetch, "MP_WXS_test", "test")
        self.assertEqual(cursors, [0, 1])
        self.assertEqual(len(result["pages"][0]["items"]), 2)
        self.assertEqual(result["business_code"], -2041)
        self.assertFalse(result["coverage_complete"])
        self.assertNotIn("private", json.dumps(result))

    def test_repeated_page_stops_without_claiming_a_terminal_page(self):
        calls = []
        def fetch(offset):
            calls.append(offset)
            return payload("same")
        result = scan_weread(fetch, "MP_WXS_test", "test")
        self.assertEqual(calls, [0, 1])
        self.assertEqual(result["reason"], "source_repeated_article")
        self.assertEqual(len(result["pages"]), 1)
        self.assertFalse(result["source_terminal_observed"])

    def test_duplicate_id_inside_group_is_not_accepted_as_two_articles(self):
        result = scan_weread(lambda _: payload("same", "same"), "MP_WXS_test", "test")
        self.assertEqual(result["reason"], "source_repeated_article")
        self.assertEqual(result["pages"], [])

    def test_budget_reached_is_not_a_complete_scan(self):
        result = scan_weread(lambda i: payload(str(i)), "MP_WXS_test", "test", max_pages=2)
        self.assertEqual([p["cursor"] for p in result["pages"]], ["0", "1"])
        self.assertFalse(result["source_terminal_observed"])
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(result["reason"], "sample_page_limit_not_complete_coverage")

    def test_empty_page_does_not_prove_identity_or_publication_coverage(self):
        result = scan_weread(lambda _: {"reviews": []}, "MP_WXS_test", "test")
        self.assertTrue(result["source_terminal_observed"])
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["account_identity_verified"])
        self.assertEqual(result["status"], "list_observed_times_unverified")

    def test_clear_all_is_only_an_observed_terminal_signal(self):
        result = scan_weread(lambda _: payload("a", clearAll=1), "MP_WXS_test", "test")
        self.assertTrue(result["source_terminal_observed"])
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["publication_times_verified"])

    def test_unknown_terminal_signals_fail_closed(self):
        for value in ("1", True, None, -1, 2):
            with self.subTest(value=value):
                result = scan_weread(lambda _: payload("a", clearAll=value), "MP_WXS_test", "test")
                self.assertEqual(result["reason"], "source_shape_changed")
                self.assertEqual(result["pages"], [])

    def test_malformed_groups_are_not_empty_success(self):
        for data in ({"reviews": [None]}, {"reviews": [{"subReviews": []}]},
                     {"reviews": [{"subReviews": ["private"]}]},
                     {"reviews": [{"subReviews": [{"review": {"mpInfo": []}}]}]}):
            with self.subTest(data=data):
                result = scan_weread(lambda _: data, "MP_WXS_test", "test")
                self.assertEqual(result["reason"], "source_shape_changed")
                self.assertFalse(result["coverage_complete"])
                self.assertNotIn("private", json.dumps(result))

    def test_transport_exception_text_is_not_logged(self):
        def fetch(_):
            raise RuntimeError("cookie=private")
        result = scan_weread(fetch, "MP_WXS_test", "test")
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(result["pages"], [])

    def test_target_and_budget_rejected_before_profile_or_browser(self):
        from validation.source import discover
        for book, account, pages in [("MP_WXS_1", "猫笔刀", 3),
                                     ("MP_WXS_3198966508", "stormzhang", 3),
                                     ("MP_WXS_3198966508", "猫笔刀", True)]:
            with patch("validation.source.profile_path") as profile, \
                    patch("validation.source.sync_playwright") as browser:
                with self.assertRaises(ValueError):
                    discover(book, account, pages)
                profile.assert_not_called()
                browser.assert_not_called()

    def test_plan_derives_only_two_public_candidates_without_io(self):
        with patch("validation.source.profile_path") as profile, \
                patch("validation.source.sync_playwright") as browser:
            plan = review_plan()
        self.assertEqual({row["account"]: row["book_id"] for row in plan["targets"]},
                         {"猫笔刀": "MP_WXS_3198966508", "stormzhang": "MP_WXS_3085404720"})
        self.assertEqual(plan["live_requests"], 0)
        self.assertFalse(plan["credentials_read"])
        self.assertTrue(all(not row["live_identity_verified"] for row in plan["targets"]))
        validate_target("MP_WXS_3198966508", "猫笔刀", 3)
        profile.assert_not_called()
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
