"""Independent implementation tests; inputs are synthetic, not live WeChat."""

import copy
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup

from test_validation import LocalTest
from validation.common import ROOT
from validation.comments import collect_comments
from validation.credentials import load_credentials
from validation.http import ProbeError, WechatHTTP, allowed_target
from validation.http_archive import parse_article, save_http_article
from validation.mp_source import parse_profile, scan_profile
from validation.state import empty_state, ingest


IDENTITY = {"comment_id": "200", "appmsgid": "100", "idx": "1"}


def fixture_pages():
    return json.loads((ROOT / "examples/comment-pages.json").read_text())


def credential():
    return {"account": "猫笔刀", "biz": "FIXTURE_BIZ", "uin": "private-uin", "key": "private-key",
            "pass_ticket": "private-pass", "appmsg_token": "private-token", "cookie": "secret=cookie",
            "captured_at": "2026-10-17T11:00:00+08:00"}


def request_from(pages, calls):
    def request(action, fields):
        calls.append((action, fields))
        return copy.deepcopy(pages[action][fields["buffer"] if action == "comments" else str(fields["max_reply_id"])])
    return request


class CommentTests(unittest.TestCase):
    def test_two_comment_and_two_reply_pages_preserve_embedded_reply(self):
        calls = []
        result = collect_comments(request_from(fixture_pages(), calls), IDENTITY)
        self.assertEqual(result["status"], "loaded")
        self.assertTrue(result["snapshot_finished"])
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["reply_pages"], 2)
        self.assertEqual({item["reply_id"] for item in result["items"][0]["replies"]}, {"10", "9", "8"})
        self.assertFalse(result["original_page_verified"])

    def test_duplicate_comments_and_replies_do_not_inflate_counts(self):
        pages, calls = fixture_pages(), []
        pages["comments"]["page-2"]["elected_comment"].append(copy.deepcopy(pages["comments"][""]["elected_comment"][0]))
        pages["replies"]["10"]["reply_list"]["reply_list"].append({"reply_id": 10, "content": "已内嵌的构造回复"})
        result = collect_comments(request_from(pages, calls), IDENTITY)
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(len(result["items"][0]["replies"]), 3)

    def test_cross_page_business_failure_keeps_first_page_and_stops(self):
        pages, calls = fixture_pages(), []
        pages["comments"]["page-2"] = {"base_resp": {"ret": -3, "errmsg": "private-key"}}
        result = collect_comments(request_from(pages, calls), IDENTITY)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["error_code"], -3)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("private-key", json.dumps(result))
        self.assertEqual(len(result["items"][0]["replies"]), 1)

    def test_repeated_comment_cursor_and_page_limit_are_partial(self):
        for limit in (1, 3):
            pages, calls = fixture_pages(), []
            pages["comments"]["page-2"].update({"continue_flag": 1, "buffer": "page-2"})
            result = collect_comments(request_from(pages, calls), IDENTITY, max_pages=limit)
            self.assertEqual(result["status"], "partial")
            self.assertLessEqual(len(calls), 2)

    def test_reply_stall_and_reply_page_limit_preserve_partial_content(self):
        for limit in (1, 3):
            pages, calls = fixture_pages(), []
            pages["replies"]["10"] = {"base_resp": {"ret": 0}, "buffer": "",
                                      "reply_list": {"max_reply_id": 10, "reply_list": []}}
            result = collect_comments(request_from(pages, calls), IDENTITY, max_reply_pages=limit)
            self.assertEqual(result["status"], "partial")
            self.assertIn("reply_count_mismatch", result["reasons"])
            self.assertEqual(len(calls), 3)

    def test_unknown_extent_or_extra_sections_never_mark_loaded(self):
        for mutate in (lambda p: p.pop("elected_comment_total_cnt"),
                       lambda p: p.pop("enabled"),
                       lambda p: p.update({"my_comment": [{"content": "other"}]}),
                       lambda p: p["elected_comment"][0].pop("reply_new")):
            pages, calls = fixture_pages(), []
            mutate(pages["comments"][""])
            result = collect_comments(request_from(pages, calls), IDENTITY)
            self.assertNotIn(result["status"], {"loaded", "none"})

    def test_empty_rejected_and_disabled_are_different(self):
        empty = {"base_resp": {"ret": 0}, "elected_comment_total_cnt": 0,
                 "enabled": 1, "elected_comment": [], "continue_flag": 0}
        self.assertEqual(collect_comments(lambda *_: empty, IDENTITY)["status"], "none")
        self.assertEqual(collect_comments(lambda *_: {**empty, "enabled": 0}, IDENTITY)["status"], "inaccessible")
        self.assertEqual(collect_comments(lambda *_: {"base_resp": {"ret": -3}}, IDENTITY)["status"], "failed")

    def test_bad_later_row_retains_valid_row_without_crashing(self):
        pages, calls = fixture_pages(), []
        pages["comments"][""]["elected_comment"].append({"content": "missing ID"})
        result = collect_comments(request_from(pages, calls), IDENTITY)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(len(calls), 1)


class HttpBodyTests(LocalTest):
    def html(self):
        return (ROOT / "examples/pages/http-article.html").read_text()

    def test_body_local_images_and_api_snapshot_do_not_imply_full_archive(self):
        result = save_http_article(self.html(), "https://mp.weixin.qq.com/s/fixture", "猫笔刀", self.path,
                                   lambda _: self.fail("inline image must not use network"),
                                   request_from(fixture_pages(), []), "FIXTURE_BIZ", "constructed")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["comments"]["status"], "loaded")
        self.assertFalse(result["publication_time_verified"])
        self.assertEqual(result["screenshot"]["status"], "not_attempted")
        text = (self.path / "article.md").read_text()
        self.assertIn("BODY-END", text)
        self.assertIn("images/", text)
        self.assertNotIn("隐藏操作面板", text)
        self.assertTrue((self.path / result["images"][0]["path"]).is_file())
        self.assertEqual(len(json.loads((self.path / "comments.json").read_text())["items"]), 2)
        self.assertNotIn("构造留言一", json.dumps(result))

    def test_account_or_biz_mismatch_prevents_comment_requests(self):
        for account, biz in [("stormzhang", "FIXTURE_BIZ"), ("猫笔刀", "WRONG_BIZ")]:
            result = save_http_article(self.html(), "https://mp.weixin.qq.com/s/fixture", account, self.path,
                                       lambda _: b"", lambda *_: self.fail("wrong account must not be requested"), biz)
            self.assertEqual(result["comments"]["status"], "blocked")

    def test_restriction_unknown_template_and_paid_preview_do_not_succeed(self):
        for html in ["<p>环境异常，请完成验证</p>", "<p>unknown template</p>",
                     self.html().replace("var biz", "var is_pay_subscribe = 1; var biz")]:
            with self.assertRaises(ProbeError):
                parse_article(html, "https://mp.weixin.qq.com/s/fixture", "猫笔刀")

    def test_picture_only_body_supported_and_script_not_executed(self):
        html = self.html().replace("var mid = '100'", "var mid = '100'; throw new Error('never execute')")
        document = BeautifulSoup(html, "html.parser")
        body = document.select_one("#js_content")
        image = body.select_one("img").extract()
        body.clear()
        body.append(image)
        html = str(document)
        parsed = parse_article(html, "https://mp.weixin.qq.com/s/fixture", "猫笔刀")
        self.assertEqual(parsed["identity"]["appmsgid"], "100")
        self.assertFalse(parsed["body_visibility_verified"])
        self.assertNotIn("script", parsed["body"])
        self.assertEqual(BeautifulSoup(parsed["body"], "html.parser").get_text(strip=True), "")


class CredentialTests(LocalTest):
    def write_input(self, data):
        folder = self.path / ".auth" / "wechat"
        folder.mkdir(parents=True, mode=0o700)
        folder.parent.chmod(0o700)
        path = folder / "maobidao.json"
        path.write_text(json.dumps(data))
        path.chmod(0o600)
        return path

    def test_missing_credentials_do_not_read_browser_sessions(self):
        with patch("validation.credentials.ROOT", self.path), self.assertRaisesRegex(ProbeError, "credentials_missing"):
            load_credentials("猫笔刀")

    def test_private_input_only_matching_account_and_no_newlines(self):
        data = credential()
        path = self.write_input(data)
        with patch("validation.credentials.ROOT", self.path):
            self.assertEqual(load_credentials("猫笔刀")["biz"], "FIXTURE_BIZ")
            path.chmod(0o644)
            with self.assertRaisesRegex(ProbeError, "permissions"):
                load_credentials("猫笔刀")
            path.chmod(0o600)
            for bad in [{**data, "account": "stormzhang"}, {**data, "cookie": "a=b\nprivate-key"}]:
                path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ProbeError, "input_invalid"):
                    load_credentials("猫笔刀")

    def test_symlink_input_rejected(self):
        path = self.write_input(credential())
        other = path.with_suffix(".other")
        path.rename(other)
        path.symlink_to(other)
        with patch("validation.credentials.ROOT", self.path), self.assertRaisesRegex(ProbeError, "symlink"):
            load_credentials("猫笔刀")


class ProfileTests(unittest.TestCase):
    def payload(self, more=0, offset=10):
        def article(mid, idx):
            return {"title": "相同标题", "content_url": f"https://mp.weixin.qq.com/s?__biz=FIXTURE_BIZ&mid={mid}&idx={idx}&sn=s&key=private-key"}
        parent = article(100, 1)
        parent["multi_app_msg_item_list"] = [article(100, 2)]
        return {"ret": 0, "general_msg_list": json.dumps({"list": [{"comm_msg_info": {"datetime": 1792159200},
                                                                  "app_msg_ext_info": parent}]}),
                "can_msg_continue": more, "next_offset": offset}

    def test_multi_article_identity_and_time_not_promoted(self):
        items, more, _ = parse_profile(self.payload(), "猫笔刀", "FIXTURE_BIZ")
        self.assertEqual(len(items), 2)
        self.assertNotEqual(items[0]["id"], items[1]["id"])
        self.assertFalse(more)
        self.assertTrue(all(not item["time_verified"] for item in items))
        self.assertNotIn("private-key", json.dumps(items))

    def test_later_page_failure_retains_results_and_never_advances_state(self):
        pages = [self.payload(1), {"ret": -3, "errmsg": "private-key"}]
        result = scan_profile(lambda *_: pages.pop(0), "猫笔刀", "FIXTURE_BIZ")
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(len(result["pages"][0]["items"]), 2)
        state = empty_state()
        self.assertFalse(ingest(state, result["pages"], "2026-10-16T00:00:00+08:00")["complete_scan"])
        self.assertIsNone(state["last_complete_check"])
        self.assertNotIn("private-key", json.dumps(result))

    def test_stalled_offset_and_wrong_account_biz_are_rejected(self):
        result = scan_profile(lambda *_: self.payload(1, 0), "猫笔刀", "FIXTURE_BIZ")
        self.assertEqual(result["reason"], "source_cursor_stalled")
        with self.assertRaises(ProbeError):
            parse_profile(self.payload(), "猫笔刀", "OTHER_BIZ")

    def test_repeated_page_links_are_deduplicated_by_incremental_state(self):
        payloads = [self.payload(1), self.payload(0)]
        result = scan_profile(lambda *_: payloads.pop(0), "猫笔刀", "FIXTURE_BIZ")
        self.assertTrue(result["coverage_complete"])
        # Only synthetic time verification here, never applied to real output.
        pages = copy.deepcopy(result["pages"])
        for page in pages:
            for item in page["items"]:
                item["time_verified"] = True
        state = empty_state()
        ingested = ingest(state, pages, "2026-10-16T00:00:00+08:00")
        self.assertTrue(ingested["complete_scan"])
        self.assertEqual(len(state["tasks"]), 2)


class TransportTests(unittest.TestCase):
    def test_https_whitelist_and_no_proxy_or_tls_downgrade(self):
        self.assertTrue(allowed_target("https://mp.weixin.qq.com/s/test"))
        self.assertTrue(allowed_target("https://mmbiz.qpic.cn/x"))
        for url in ["http://mp.weixin.qq.com/s/x", "https://mp.weixin.qq.com.evil.test/x",
                    "https://user:private-key@mp.weixin.qq.com/s/x", "https://mp.weixin.qq.com:444/x"]:
            self.assertFalse(allowed_target(url))
        client = WechatHTTP()
        for handler in client.opener.handlers:
            if hasattr(handler, "proxies"):
                self.assertFalse(handler.proxies)
            if hasattr(handler, "_context") and handler._context:
                self.assertTrue(handler._context.check_hostname)

    def test_cookie_never_sent_to_cdn_and_reserved_query_not_overridden(self):
        client = WechatHTTP()
        with self.assertRaisesRegex(ProbeError, "credential_target"):
            client.read("https://mmbiz.qpic.cn/x", {"Cookie": "private-key"})
        with self.assertRaisesRegex(ProbeError, "invalid_request_fields"):
            client.api("list", {"__biz": "OTHER"}, credential())

    def test_protocol_encoding_and_credential_values_not_returned(self):
        client = WechatHTTP()
        captured = []
        with patch.object(client, "read", side_effect=lambda url, headers: captured.append((url, headers)) or b'{"base_resp":{"ret":0}}'):
            result = client.api("comments", {**IDENTITY, "buffer": "a+b/c=", "limit": 100}, credential())
        params = parse_qs(urlsplit(captured[0][0]).query)
        self.assertEqual(params["buffer"], ["a+b/c="])
        self.assertEqual(params["appmsg_token"], ["private-token"])
        self.assertNotIn("private-token", json.dumps(result))

    def test_transport_errors_never_include_sensitive_urls(self):
        client = WechatHTTP()
        for raw in [HTTPError("https://mp.weixin.qq.com/?key=private-key", 302, "private-key", {}, None),
                    HTTPError("https://mp.weixin.qq.com/?key=private-key", 403, "private-key", {}, None),
                    URLError("https://mp.weixin.qq.com/?key=private-key")]:
            with patch.object(client.opener, "open", side_effect=raw):
                with self.assertRaises(ProbeError) as caught:
                    client.read("https://mp.weixin.qq.com/s/fixture")
                self.assertNotIn("private-key", str(caught.exception))

    def test_non_json_response_is_not_an_empty_success(self):
        client = WechatHTTP()
        with patch.object(client, "read", return_value=b'<p>private-key</p>'):
            with self.assertRaisesRegex(ProbeError, "response_not_json"):
                client.api("list", {"offset": 0, "count": 10}, credential())

    def test_real_loopback_transport_redirect_and_size_guard(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(302 if self.path == "/redirect" else 200)
                if self.path == "/redirect":
                    self.send_header("Location", "/target")
                self.end_headers()
                self.wfile.write(b"fixture-body")

            def log_message(self, *_):
                pass
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError:
            self.skipTest("environment cannot bind loopback; not transport validation passed")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            # Production target/TLS policy is tested separately. Only the test
            # redirects transport to loopback; no such switch exists in the CLI.
            with patch("validation.http.allowed_target", return_value=True):
                client = WechatHTTP()
                self.assertEqual(client.read(base + "/ok"), b"fixture-body")
                with self.assertRaisesRegex(ProbeError, "redirect_blocked"):
                    client.read(base + "/redirect")
                with self.assertRaisesRegex(ProbeError, "response_size_limit"):
                    client.read(base + "/large", limit=3)
            self.assertNotIn("/target", seen)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
