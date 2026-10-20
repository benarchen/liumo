import copy
import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from unittest.mock import patch

from validation.archive import archive, await_manual_readiness, comment_status, image_extension, render_markdown, watch_comment_requests
from validation.common import ROOT, article_key, article_url, parse_time
from validation.schedule import decide, latest_slot, next_slot, render_plist
from validation.notify import notify, render_event
from validation.source import parse_weread
from validation.state import archive_result, empty_state, ingest, pending


class LocalTest(unittest.TestCase):
    def setUp(self):
        base = ROOT / ".tmp/feasibility/tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()


def item(identity="a", when="2026-10-16T22:00:00+08:00"):
    return {"id": identity, "account": "test", "title": "相同标题", "url": f"https://mp.weixin.qq.com/s/{identity}",
            "published_at": when, "time_verified": True}


class IncrementalTests(LocalTest):
    def setUp(self):
        super().setUp()
        self.state = empty_state()
        self.start = "2026-10-16T22:00:00+08:00"

    def ingest(self, items, more=False):
        return ingest(self.state, [{"cursor": "0", "items": items, "has_more": more}], self.start, "check-1")

    def test_before_equal_after_and_multiple_group_items(self):
        result = self.ingest([item("before", "2026-10-16T21:59:59+08:00"), item("equal"),
                              item("after", "2026-10-16T22:00:01+08:00")])
        self.assertEqual(len(result["found"]), 2)
        self.assertTrue(result["complete_scan"])

    def test_same_title_different_articles_survive(self):
        self.ingest([item("a"), item("b")])
        self.assertEqual(len(pending(self.state)), 2)

    def test_multiple_daily_publications_and_pages(self):
        pages = [{"cursor": "0", "items": [item("late", "2026-10-16T23:10:00+08:00")], "has_more": True},
                 {"cursor": "1", "items": [item("early")], "has_more": False}]
        result = ingest(self.state, pages, self.start)
        self.assertTrue(result["complete_scan"])
        self.assertEqual(len(pending(self.state)), 2)

    def test_partial_page_failure_keeps_discoveries_and_watermark(self):
        self.state["last_complete_check"] = "old"
        pages = [{"cursor": "0", "items": [item()], "has_more": True}, {"cursor": "1", "error": "network"}]
        result = ingest(self.state, pages, self.start)
        self.assertFalse(result["complete_scan"])
        self.assertEqual(self.state["last_complete_check"], "old")
        self.assertEqual(len(pending(self.state)), 1)

    def test_repeat_run_and_failure_recovery_keep_independent_queue(self):
        key = self.ingest([item()])["found"][0]
        archive_result(self.state, key, "partial")
        self.assertEqual(self.ingest([item()])["found"], [])
        self.assertIn(key, pending(self.state))
        archive_result(self.state, key, "failed")
        archive_result(self.state, key, "complete")
        self.assertEqual(pending(self.state), [])
        self.assertEqual(self.state["tasks"][key]["attempts"], 3)
        with self.assertRaises(ValueError):
            archive_result(self.state, key, "partial")

    def test_seen_article_does_not_stop_pending_or_older_scan(self):
        first = self.ingest([item("a")])["found"][0]
        archive_result(self.state, first, "complete")
        result = self.ingest([item("a"), item("b")])
        self.assertEqual(len(result["found"]), 1)

    def test_unverified_and_missing_time_do_not_advance(self):
        unverified = item(); unverified["time_verified"] = False
        invalid = item("b"); invalid["published_at"] = "2026-10-16T22:00:00"
        result = self.ingest([unverified, invalid])
        self.assertFalse(result["complete_scan"])
        self.assertEqual(self.state["tasks"], {})

    def test_missing_tail_and_repeated_cursor_fail(self):
        self.assertFalse(self.ingest([item()], True)["complete_scan"])
        page = {"cursor": "0", "items": [], "has_more": True}
        result = ingest(self.state, [page, page], self.start)
        self.assertIn("repeated_cursor", result["issues"])

    def test_identity_changes_reported_without_overwriting(self):
        self.ingest([item()]); before = copy.deepcopy(self.state["tasks"])
        result = self.ingest([item("a", "2026-10-16T23:00:00+08:00")])
        self.assertIn("identity_or_time_changed", result["issues"])
        self.assertEqual(before, self.state["tasks"])

    def test_invalid_page_and_empty_scan_not_success(self):
        self.assertFalse(ingest(self.state, [], self.start)["complete_scan"])
        self.assertFalse(ingest(self.state, [{"cursor": "0", "has_more": False}], self.start)["complete_scan"])

    def test_long_url_tracking_dedup_and_public_identity_preserved(self):
        original = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=2&sn=xyz"
        self.assertEqual(article_url(original), article_url(original + "&scene=1&token=secret&key=secret"))
        self.assertNotIn("secret", article_url(original + "&token=secret"))
        self.assertNotEqual(article_key(original), article_key(original.replace("idx=2", "idx=3")))

    def test_short_long_identity_alias_requires_source_id(self):
        short = "https://mp.weixin.qq.com/s/short"
        long = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=1&sn=xyz"
        self.assertEqual(article_key(short, "source-id", "test"), article_key(long, "source-id", "test"))
        self.assertNotEqual(article_key(short), article_key(long))

    def test_stable_source_identity_url_alias_preserves_archive_and_scan(self):
        short = "https://mp.weixin.qq.com/s/short"
        long = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=1&sn=xyz"
        for status in ("pending", "partial", "complete"):
            with self.subTest(status=status):
                self.state = empty_state()
                original = {**item("same-source-id"), "url": short}
                key = self.ingest([original])["found"][0]
                if status != "pending":
                    archive_result(self.state, key, status)
                before = copy.deepcopy(self.state["tasks"])
                alias = {**original, "url": long}
                result = self.ingest([alias])
                self.assertTrue(result["complete_scan"], result)
                self.assertEqual(result["found"], [])
                self.assertEqual(result["issues"], [])
                self.assertEqual(self.state["tasks"], before)
                self.assertEqual(pending(self.state), [] if status == "complete" else [key])


class ScheduleTests(LocalTest):
    def test_all_four_beijing_slots(self):
        for hour, minute in ((22, 0), (22, 30), (23, 0), (23, 30)):
            now = parse_time(f"2026-10-16T{hour}:{minute:02}:00+08:00")
            self.assertTrue(decide(now, now - timedelta(seconds=1), True)["run"])
            self.assertFalse(decide(now, now, True)["run"])

    def test_next_day_and_225_hour_gap(self):
        now = parse_time("2026-10-16T23:30:00+08:00")
        self.assertEqual((next_slot(now) - now).total_seconds(), 22.5 * 3600)
        self.assertEqual(next_slot(now), parse_time("2026-10-17T22:00:00+08:00"))

    def test_offline_recovery_outside_window_coalesces(self):
        last = parse_time("2026-10-14T22:00:00+08:00")
        now = parse_time("2026-10-17T10:00:00+08:00")
        self.assertFalse(decide(now, last, False)["run"])
        self.assertTrue(decide(now, last, True, False)["run"])
        self.assertFalse(decide(now, now, True, True)["run"])

    def test_short_offline_recovery_without_missed_slot(self):
        now = parse_time("2026-10-17T10:00:00+08:00")
        last = parse_time("2026-10-17T09:50:00+08:00")
        self.assertEqual(decide(now, last, True, False)["reason"], "recovery_coalesced")

    def test_system_timezone_and_dst_do_not_shift_beijing(self):
        for value in ("2026-03-08T14:00:00+00:00", "2026-11-01T14:00:00+00:00"):
            utc = parse_time(value)
            self.assertEqual(latest_slot(utc), latest_slot(utc.astimezone(ZoneInfo("America/Los_Angeles"))))
            self.assertEqual(latest_slot(utc).astimezone(ZoneInfo("Asia/Shanghai")).hour, 22)

    def test_naive_time_and_clock_reversal(self):
        now = parse_time("2026-10-16T22:00:00+08:00")
        with self.assertRaises(ValueError):
            decide(now.replace(tzinfo=None), None, True)
        self.assertEqual(decide(now, now + timedelta(hours=1), True)["reason"], "clock_moved_backwards")

    def test_review_only_config_and_no_overwrite(self):
        output = self.path / "local.liumo.feasibility.plist"
        self.assertFalse(render_plist(output)["loaded"])
        config = plistlib.loads(output.read_bytes())
        self.assertEqual(config["StartCalendarInterval"], {})
        self.assertIn("schedule", config["ProgramArguments"])
        with self.assertRaises(FileExistsError):
            render_plist(output)

    def test_real_process_overlap_is_rejected(self):
        state = self.path / "schedule.json"
        code = "from validation.state import exclusive;import sys,time\nwith exclusive(sys.argv[1]):\n print('locked',flush=True)\n time.sleep(0.5)"
        process = subprocess.Popen([sys.executable, "-c", code, str(state.with_suffix('.lock'))],
                                   stdout=subprocess.PIPE, text=True, cwd=ROOT)
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            result = subprocess.run([sys.executable, "-m", "validation", "schedule", "--state", str(state)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(state.exists())
        finally:
            process.wait(timeout=10)
            process.stdout.close()

    def test_real_probe_process_repeat_is_coalesced(self):
        state = self.path / "schedule.json"
        command = [sys.executable, "-m", "validation", "schedule", "--state", str(state)]
        first = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=10)
        second = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=10)
        self.assertEqual(json.loads(first.stdout)["runs"], 1)
        self.assertEqual(json.loads(second.stdout)["runs"], 1)
        self.assertEqual(json.loads(first.stdout)["evidence"], "local_process")


class ArchiveTests(LocalTest):
    def test_manual_readiness_accepts_enter_and_cancels_other_input(self):
        for value, expected in (("", True), ("q", False), ("not-ready", False)):
            with patch("builtins.input", return_value=value), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(await_manual_readiness(), expected)
        for error in (EOFError, KeyboardInterrupt):
            with patch("builtins.input", side_effect=error), patch("sys.stdout", new_callable=io.StringIO):
                self.assertFalse(await_manual_readiness())

    def test_manual_cancellation_and_wrong_site_do_not_capture_or_retry(self):
        url = "https://mp.weixin.qq.com/s/test-article"
        for response, current_url, reason in (("q", url, "manual_capture_cancelled"),
                                              ("", "https://example.com/", "left_article_site")):
            with self.subTest(reason=reason), patch("validation.archive.sync_playwright") as driver_factory, \
                    patch("validation.archive.new_run", return_value=self.path), \
                    patch("validation.archive.snapshot_page") as capture, \
                    patch("builtins.input", return_value=response), patch("sys.stdout", new_callable=io.StringIO):
                driver = driver_factory.return_value.__enter__.return_value
                browser = driver.chromium.launch.return_value
                context = browser.new_context.return_value
                page = context.new_page.return_value
                page.url = current_url
                result = archive(url, headed=True, interactive=True)
                capture.assert_not_called()
                page.goto.assert_called_once()
                context.close.assert_called_once()
                browser.close.assert_called_once()
                self.assertIn(reason, result["reasons"])
                self.assertNotEqual(result["status"], "complete")

    def test_comment_rejections_record_no_credentials_and_detach(self):
        callbacks = {}
        page = SimpleNamespace(on=lambda event, fn: callbacks.update({event: fn}),
                               remove_listener=lambda event, fn: callbacks.pop(event))
        failures, detach = watch_comment_requests(page)
        callbacks["response"](SimpleNamespace(url="https://mp.weixin.qq.com/comment?token=secret", status=200,
            headers={"content-type": "application/json"}, json=lambda: {"base_resp": {"ret": 200013}}))
        callbacks["requestfailed"](SimpleNamespace(url="https://mp.weixin.qq.com/reply?token=secret"))
        self.assertEqual([f["reason"] for f in failures], ["business_rejected", "network_failure"])
        self.assertEqual(failures[0]["business_code"], 200013)
        self.assertEqual(failures[0]["http_status"], 200)
        self.assertEqual(failures[0]["path"], "/comment")
        self.assertNotIn("secret", json.dumps(failures))
        detach()
        self.assertEqual(callbacks, {})

    def test_comment_states_are_distinct(self):
        self.assertEqual(comment_status("暂无留言", True), "none")
        self.assertEqual(comment_status("请在微信客户端打开", True), "inaccessible")
        self.assertEqual(comment_status("加载失败", True), "failed")
        self.assertEqual(comment_status("", False), "unknown")
        self.assertEqual(comment_status("一条评论", True, 1), "loaded")
        self.assertEqual(comment_status("一条评论", True, 1, pending=1), "incomplete")

    def test_network_error_never_means_no_comments(self):
        self.assertEqual(comment_status("暂无留言", True, failed_requests=1), "failed")
        self.assertEqual(comment_status("暂无留言", True, items=1), "unknown")

    def test_markdown_and_local_image_survive_without_network(self):
        source = (ROOT / "examples/pages/article.html").read_text()
        from bs4 import BeautifulSoup
        html = str(BeautifulSoup(source, "html.parser").select_one("[data-liumo-body]"))
        result = render_markdown(html, "构造页面", "http://127.0.0.1/", self.path,
                                 lambda _: self.fail("inline image must not use network"))
        markdown = (self.path / "article.md").read_text()
        self.assertIn("BODY-END", markdown)
        self.assertIn("**正文**", markdown)
        self.assertIn("images/", markdown)
        self.assertNotIn("data:image", markdown)
        self.assertEqual(result["image_failures"], [])
        self.assertTrue((self.path / result["images"][0]["path"]).is_file())

    def test_image_failure_is_explicit_and_removes_remote_reference(self):
        def failed(_):
            raise OSError("example secret must not enter evidence")
        result = render_markdown('<p>body</p><img src="https://example.com/a?token=secret">',
                                 "title", "https://example.com/", self.path, failed)
        markdown = (self.path / "article.md").read_text()
        self.assertIn("下载失败", markdown)
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("https://example.com", markdown)

    def test_known_image_failure_is_diagnostic_without_query_or_exception_text(self):
        def failed(_):
            raise ValueError("unverified_image_host")
        result = render_markdown('<img src="https://example.com/image?token=secret">',
                                 "title", "https://example.com/", self.path, failed)
        self.assertEqual(result["image_failures"], [
            {"index": 0, "reason": "unverified_image_host", "source_host": "example.com"}])
        self.assertNotIn("secret", json.dumps(result))

    def test_missing_image_source_does_not_fetch_the_article_as_an_image(self):
        result = render_markdown('<p>body</p><img>', "title", "https://mp.weixin.qq.com/s/test", self.path,
                                 lambda _: self.fail("missing image source must not trigger a request"))
        self.assertEqual(result["image_failures"][0]["reason"], "missing_image_source")

    def test_embedded_title_not_duplicated_and_other_heading_preserved(self):
        result = render_markdown('<h1>文章标题</h1><p>正文</p><h1>另一节</h1>',
                                 "文章标题", "https://example.com/", self.path, lambda _: b"")
        markdown = (self.path / "article.md").read_text()
        self.assertEqual(markdown.count('# 文章标题'), 1)
        self.assertIn('# 另一节', markdown)
        self.assertEqual(result['image_failures'], [])

    def test_selected_image_keeps_original_dom_index_and_rejects_bad_mapping(self):
        def failed(_):
            raise OSError("no image available")
        result = render_markdown('<img src="https://example.com/a">', 'title', 'https://example.com/',
                                 self.path, failed, image_indices=[2])
        self.assertEqual(result['image_failures'][0]['index'], 2)
        self.assertIn('配图 3', (self.path / 'article.md').read_text())
        with self.assertRaises(ValueError):
            render_markdown('<img>', 'title', 'https://example.com/', self.path, failed, image_indices=[])

    def test_only_observed_hidden_empty_account_avatar_is_omitted(self):
        empty_avatar = {"index": 0, "id": "js_tail_panel_account_avatar", "has_source": False,
                        "visible": False, "natural_width": 0, "natural_height": 0,
                        "rendered_width": 0, "rendered_height": 0}
        html = '<p>BODY-END</p><img id="js_tail_panel_account_avatar">'
        result = render_markdown(html, "title", "https://mp.weixin.qq.com/s/test", self.path,
                                 lambda _: self.fail("empty avatar must not trigger a request"), [empty_avatar])
        self.assertEqual(result["image_failures"], [])
        self.assertEqual(result["ignored_image_nodes"], [{"index": 0, "id": empty_avatar["id"],
                                                       "reason": "observed_hidden_empty_account_avatar"}])
        self.assertIn("BODY-END", (self.path / "article.md").read_text())
        self.assertNotIn("下载失败", (self.path / "article.md").read_text())
        variants = [[], [{**empty_avatar, "id": "unknown"}], [{**empty_avatar, "visible": True}],
                    [{**empty_avatar, "rendered_width": 10}], [{**empty_avatar, "has_source": True}]]
        for nodes in variants:
            with self.subTest(nodes=nodes):
                result = render_markdown(html, "title", "https://mp.weixin.qq.com/s/test", self.path,
                                         lambda _: self.fail("missing source must not trigger a request"), nodes)
                self.assertEqual(result["ignored_image_nodes"], [])
                self.assertEqual(result["image_failures"][0]["reason"], "missing_image_source")
                self.assertIsNone(result["image_failures"][0]["source_host"])
        result = render_markdown(html.replace('id="js_tail_panel_account_avatar"', 'id="unknown"'),
                                 "title", "https://mp.weixin.qq.com/s/test", self.path,
                                 lambda _: self.fail("missing source must not trigger a request"), [empty_avatar])
        self.assertEqual(len(result["image_failures"]), 1)
        def failed(_):
            raise OSError("do not hide source-bearing avatars")
        result = render_markdown(html.replace('<img ', '<img src="https://mp.weixin.qq.com/avatar" '),
                                 "title", "https://mp.weixin.qq.com/s/test", self.path, failed, [empty_avatar])
        self.assertEqual(result["ignored_image_nodes"], [])
        self.assertEqual(len(result["image_failures"]), 1)

    def test_scripts_and_nonimage_data_are_rejected(self):
        result = render_markdown('<p>body</p><script>secret()</script><img src="data:text/html;base64,abcd">',
                                 "title", "https://example.com/", self.path, lambda _: b"html")
        self.assertNotIn("secret", (self.path / "article.md").read_text())
        self.assertEqual(len(result["image_failures"]), 1)
        with self.assertRaises(ValueError):
            image_extension(b"<html>not an image</html>")


class SourceTests(unittest.TestCase):
    def test_groups_include_every_article_and_time_is_not_promoted(self):
        children = [{"review": {"reviewId": f"id-{index}", "mpInfo": {
            "originalId": f"token~{index}", "title": "构造标题", "time": 1792159200}}} for index in range(3)]
        items, groups = parse_weread({"reviews": [{"subReviews": children}]}, "MP_WXS_test", "test")
        self.assertEqual((len(items), groups), (3, 1))
        self.assertFalse(any(item["time_verified"] for item in items))
        self.assertTrue(all(item["url"] is None and not item["url_verified"] for item in items))
        self.assertEqual([item["original_id"] for item in items], [f"token~{i}" for i in range(3)])

    def test_rejection_or_shape_change_never_becomes_empty_success(self):
        for payload in ({"errCode": -2012}, {}, {"reviews": [{}]}, [], {"reviews": [{"subReviews": [{"review": {}}]}]}):
            with self.assertRaises(ValueError):
                parse_weread(payload, "MP_WXS_test", "test")


class SourceProbeTests(LocalTest):
    def test_rejected_source_records_safe_diagnostics_and_stops_before_next_page(self):
        from validation.source import discover
        cases = [({"errCode": -2012, "errMsg": "secret"}, "source_rejected", -2012),
                 ({"errCode": "secret"}, "source_rejected", None),
                 ({"private": "secret"}, "source_shape_changed", None),
                 (None, "source_rejected_or_shape_changed", None)]
        for payload, reason, code in cases:
            with self.subTest(payload=payload), patch("validation.source.sync_playwright") as factory, \
                    patch("validation.source.profile_path", return_value=self.path / 'session'), \
                    patch("validation.source.new_run", return_value=self.path):
                driver = factory.return_value.__enter__.return_value
                context = driver.chromium.launch_persistent_context.return_value
                context.pages = []
                context.new_page.return_value.evaluate.return_value = 'test-agent'
                response = context.request.get.return_value
                response.status = 200
                if payload is None:
                    response.json.side_effect = ValueError('token=secret')
                else:
                    response.json.return_value = payload
                result = discover('MP_WXS_3198966508', '猫笔刀')
                self.assertEqual(result['reason'], reason)
                self.assertEqual(result.get('business_code'), code)
                self.assertEqual(result['http_status'], 200)
                self.assertFalse(result['coverage_complete'])
                self.assertEqual(result['pages'], [])
                self.assertNotIn('secret', json.dumps(result))
                context.request.get.assert_called_once()
                context.close.assert_called_once()


class NotificationTests(unittest.TestCase):
    def test_local_boundary_and_chinese_rendering(self):
        sent = []
        result = notify("partial", 2, sender=lambda title, message: sent.append((title, message)))
        self.assertEqual(result["notification"], "sent")
        self.assertEqual(sent, [("留墨", "归档部分成功，请查看未完成原因。涉及 2 篇文章。")])

    def test_sender_failure_and_invalid_input_are_reported(self):
        def failure(*args):
            raise OSError("notification denied")
        self.assertEqual(notify("complete", 1, failure)["notification"], "failed")
        with self.assertRaises(ValueError):
            render_event("complete", -1)


class CommandSafetyTests(LocalTest):
    def test_invalid_inputs_fail_before_browser_or_notification(self):
        cases = [
            ["fixture", "--url", "https://example.com/"],
            ["fixture", "--file", "/etc/hosts"],
            ["discover", "--account", "猫笔刀", "--book-id", "invalid"],
            ["notify", "--event", "complete", "--count", "-1"],
            ["archive", "--sample", "maobidao", "--interactive"],
            ["archive", "--sample", "maobidao", "--headed", "--interactive"],
        ]
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "validation", *args],
                                        cwd=ROOT, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "failed")
                self.assertNotIn("Traceback", result.stdout + result.stderr)


@unittest.skipUnless(os.environ.get("LIUMO_BROWSER_TESTS") == "1", "browser process permission required; not counted as verified")
class BrowserIntegrationTests(LocalTest):
    def test_hidden_body_ui_removed_from_copy_and_visible_override_kept(self):
        from playwright.sync_api import sync_playwright
        from validation.archive import select_markdown_body
        with sync_playwright() as driver:
            browser = driver.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True)
            try:
                page = browser.new_page()
                page.set_content('''<article><h1>title</h1><p><b>VISIBLE</b></p>
                    <div style="display:none">DONATION-NOISE<img src="hidden.png"></div>
                    <div style="visibility:hidden">HIDDEN-TEXT<span style="visibility:visible">OVERRIDE-VISIBLE</span>
                    <img style="width:110px;height:110px" alt="hidden QR"></div>
                    <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aATkAAAAASUVORK5CYII=">
                    <p>BODY-END</p></article>''')
                body = page.locator('article')
                before = body.inner_html()
                selected = select_markdown_body(body)
                self.assertEqual(body.inner_html(), before)
                self.assertNotIn('DONATION-NOISE', selected['html'])
                self.assertNotIn('HIDDEN-TEXT', selected['html'])
                self.assertNotIn('hidden QR', selected['html'])
                self.assertIn('<b>VISIBLE</b>', selected['html'])
                self.assertIn('OVERRIDE-VISIBLE', selected['html'])
                self.assertIn('BODY-END', selected['html'])
                self.assertEqual(selected['retained_image_indices'], [2])
            finally:
                browser.close()

    def test_fixture_full_page_and_reply_expansion(self):
        from playwright.sync_api import sync_playwright
        from validation.archive import snapshot_page
        with sync_playwright() as driver:
            browser = driver.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True)
            try:
                page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=1)
                page.goto((ROOT / "examples/pages/article.html").as_uri())
                result = snapshot_page(page, self.path, fixture=True)
                self.assertEqual(result["status"], "complete", result)
                self.assertEqual(result["comments"]["expanded"], 1)
                self.assertGreaterEqual(result["screenshot_dimensions"]["height"], result["document_dimensions"]["height"])
            finally:
                browser.close()

    def test_comment_failure_cannot_be_complete(self):
        from playwright.sync_api import sync_playwright
        from validation.archive import snapshot_page
        with sync_playwright() as driver:
            browser = driver.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True)
            try:
                page = browser.new_page()
                page.goto((ROOT / "examples/pages/article.html").as_uri() + "?comments=failed")
                result = snapshot_page(page, self.path, fixture=True)
                self.assertEqual(result["status"], "partial")
                self.assertIn("comments_failed", result["reasons"])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
