"""Run with python -m validation; see README for actual scope and commands."""

import argparse
import json
import sys
from pathlib import Path

from .common import ROOT, SAMPLES, article_url, error_kind, parse_time, write_json


def main():
    parser = argparse.ArgumentParser(description="留墨可行性验证，不启用正式订阅。")
    commands = parser.add_subparsers(dest="command", required=True)
    page_sample = commands.add_parser("page-sample", help="历史原页诊断，不属于 RSS 产品验收。")
    page_sample.add_argument('--headed', action='store_true')
    page_sample.add_argument('--wait-readable', action='store_true')
    commands.add_parser("weread-plan", help="离线审阅两号发现请求、公开标识和待验证范围，不读取会话或联网。")
    commands.add_parser("certificate-scope-fixture", help="仅离线证书域名约束验证；使用 .venv-capture，不安装信任或访问微信。")
    commands.add_parser("anchor-scope-session", help="已单独授权的 C15 用户级临时信任对照；仅离线，最多 120 秒，无代理或微信请求。")
    commands.add_parser("anchor-scope-recover", help="仅撤销 C15 本次公共证书的用户信任，按固定指纹检查恢复。")
    commands.add_parser("wechat-compat-plan", help="仅审阅下一次微信兼容实验范围和预算，不改系统。")
    commands.add_parser("wechat-compat-fixture", help="仅离线组件／证书／内存 TLS；无监听、信任安装或微信访问。")
    commands.add_parser("wechat-compat-session", help="已单独授权的 C16 单次 180 秒实验，预留 120 秒恢复；不采凭证。")
    commands.add_parser("wechat-compat-recover", help="仅恢复 C16 本次代理、信任、进程和私钥。")
    observation = commands.add_parser("wechat-compat-observe", help="C16 运行中固定计数取样，不能证明 UI 刷新。")
    observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    commands.add_parser("wechat-compat-finish", help="C16 控制通过后提前请求收尾。")
    commands.add_parser("article-functional-session", help="已单独授权的 C17 固定文章一次候选；系统恢复后至多核对正文／评论各一次。")
    commands.add_parser("article-functional-recover", help="仅恢复 C17 本次系统改动，不重复采集或 HTTP 核对。")
    functional_observation = commands.add_parser("article-functional-observe", help="C17 控制通过后的固定计数取样。")
    functional_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    commands.add_parser("article-functional-finish", help="C17 提前请求恢复；不发送功能请求。")
    commands.add_parser("comment-baseline-plan", help="只读审阅 C21 固定文章评论基线范围，无凭证或网络动作。")
    commands.add_parser("comment-baseline-session", help="另行授权的 C21 单次原生评论被动基线；无主动 API 请求。")
    commands.add_parser("comment-baseline-recover", help="仅恢复 C21 本次代理、信任、进程和私钥。")
    comment_observation = commands.add_parser("comment-baseline-observe", help="C21 控制通过后的固定计数取样。")
    comment_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    commands.add_parser("comment-baseline-finish", help="C21 提前请求恢复，不发接口请求。")
    commands.add_parser("comment-baseline-compare", help="C21 系统恢复通过后离线比较私有基线，不主动重放。")
    for action in ("plan", "session", "recover", "finish", "compare"):
        commands.add_parser("comment-refresh-" + action, help="C22 独立明确刷新对照；真实入口需本次授权，plan 只读。")
    refresh_observation = commands.add_parser("comment-refresh-observe", help="C22 控制通过后的固定匹配计数取样。")
    refresh_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    for action in ("plan", "fixture", "session", "recover", "finish"):
        commands.add_parser("html-static-" + action, help="C24 固定文章内存静态取证；plan／fixture 无网络，真实入口需新授权。")
    static_observation = commands.add_parser("html-static-observe", help="C24 控制通过后的固定计数取样。")
    static_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    for action in ("plan", "fixture", "session", "recover", "finish"):
        commands.add_parser("html-static-metadata-" + action, help="C25 独立响应头固定分类及 HTML 静态取证；真实入口需新授权。")
    metadata_observation = commands.add_parser("html-static-metadata-observe", help="C25 控制通过后的固定计数取样。")
    metadata_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    for action in ("plan", "fixture", "session", "recover", "finish"):
        commands.add_parser("html-static-duplicates-" + action, help="C26 独立等价双头处理；plan／fixture 无网络，真实入口需新授权。")
    duplicates_observation = commands.add_parser("html-static-duplicates-observe", help="C26 控制通过后的固定计数取样。")
    duplicates_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    for action in ("plan", "fixture", "session", "recover", "finish"):
        commands.add_parser("html-static-inline-" + action, help="C28 固定 HTML 内联脚本分析；真实入口须新单次授权。")
    inline_observation = commands.add_parser("html-static-inline-observe", help="C28 控制通过后的固定计数取样。")
    inline_observation.add_argument("--phase", required=True, choices=("before_refresh", "after_refresh"))
    archive_parser = commands.add_parser("archive")
    archive_parser.add_argument("--sample", choices=SAMPLES, required=True)
    archive_parser.add_argument("--session", action="store_true")
    archive_parser.add_argument("--headed", action="store_true")
    archive_parser.add_argument("--interactive", action="store_true",
                                help="在可见专用窗口中等待用户正常访问就绪后取证。")
    fixture_parser = commands.add_parser("fixture")
    fixture_input = fixture_parser.add_mutually_exclusive_group()
    fixture_input.add_argument("--url")
    fixture_input.add_argument("--file", type=Path, default=ROOT / "examples/pages/article.html")
    login_parser = commands.add_parser("login")
    login_parser.add_argument("--site", choices=("weread", "article"), required=True)
    login_parser.add_argument("--sample", choices=SAMPLES, default="maobidao")
    login_parser.add_argument("--auto-wait", action="store_true", help="仅微信读书：自动观察最多 300 秒的会话更新，无需终端 Enter。")
    source_parser = commands.add_parser("discover")
    source_parser.add_argument("--book-id", required=True)
    source_parser.add_argument("--account", choices=("猫笔刀", "stormzhang"), required=True)
    source_parser.add_argument("--max-pages", type=int, default=3)
    http_parser = commands.add_parser("http-archive", help="HTTP 正文／配图与独立评论快照，不生成替代截图。")
    http_parser.add_argument("--sample", choices=SAMPLES, required=True)
    http_parser.add_argument("--credentialed", action="store_true", help="先校验项目凭证，正文使用同号已有 Cookie，不匿名回退。")
    http_parser.add_argument("--transport", choices=("python", "curl"), default="python")
    samples_parser = commands.add_parser("sample-check", help="两篇固定技术样本，串行带凭证 HTTP；不访问列表或修改系统。")
    samples_parser.add_argument("--transport", choices=("python", "curl"), default="python")
    samples_parser.add_argument("--browser", action="store_true", help="HTTP 门槛通过后在独立无头上下文验证原页截图。")
    commands.add_parser("sample-check-bridge", help="有限 FIFO 验证桥；需 Agent 以已获准的独立 curl 承载请求，无系统改动。")
    commands.add_parser("mp-diagnose-bridge", help="两号各一次列表结构探针，复用有限 FIFO 桥，不改系统。")
    commands.add_parser("profile-context-bridge", help="两个目标号的正常主页会话前置检查，仅临时内存，不保存新凭证。")
    commands.add_parser("profile-context", help="普通终端的 Python HTTPS 主页会话前置检查，不采集、不改系统。")
    commands.add_parser("http-fixture", help="只处理脱敏构造 HTML／JSON，不访问网络。")
    commands.add_parser("capture-plan", help="仅输出待授权实验配置，不启动采集或更改系统。")
    commands.add_parser("capture-fixture", help="构造凭证采集回放，只在临时目录处理虚假字段。")
    commands.add_parser("capture-preflight", help="只读核对本机代理原配置；不改系统、不采集凭证。")
    session_parser = commands.add_parser("capture-session", help="在普通终端执行已授权的一次有限时实验，并核对恢复。")
    session_parser.add_argument("--baseline", type=Path, required=True)
    commands.add_parser("capture-recover", help="恢复本次实验占用的代理与本次证书信任，不覆盖并行修改。")
    commands.add_parser("profile-capture-session", help="已授权的第二次限定实验；新基线、两号正常主页／列表及即时核对，完成后恢复。")
    commands.add_parser("profile-capture-recover", help="仅恢复第二次主页／列表实验的代理及证书信任。")
    commands.add_parser("transport-diagnostic-session", help="待单独授权的 120 秒无凭证诊断；通过控制请求后才提示刷新猫笔刀主页。")
    commands.add_parser("transport-diagnostic-recover", help="只恢复短诊断实验的代理及本次信任，不操作旧实验。")
    commands.add_parser("ui-transport-diagnostic-session", help="已授权的单次 Agent 右侧主页诊断；独立目录，120 秒，无凭证。")
    commands.add_parser("ui-transport-diagnostic-recover", help="仅恢复 Agent 操作的短诊断实验。")
    commands.add_parser("article-transport-diagnostic-session", help="已授权的单次文章页对照诊断；独立目录，120 秒，无凭证。")
    commands.add_parser("article-transport-diagnostic-recover", help="仅恢复文章页对照诊断实验。")
    mp_parser = commands.add_parser("mp-discover", help="Credential 列表候选；缺少私有输入时不发请求。")
    mp_parser.add_argument("--account", choices=("猫笔刀", "stormzhang"), required=True)
    mp_parser.add_argument("--max-pages", type=int, default=3)
    mp_parser.add_argument("--transport", choices=("python", "curl"), default="python")
    diagnostic_parser = commands.add_parser("mp-diagnose", help="仅一次列表请求，输出固定字段类型与数量，不保存原始响应。")
    diagnostic_parser.add_argument("--account", choices=("猫笔刀", "stormzhang", "all"), required=True)
    diagnostic_parser.add_argument("--transport", choices=("python", "curl"), default="python")
    schedule_parser = commands.add_parser("schedule")
    schedule_parser.add_argument("--state", type=Path, default=ROOT / "state/feasibility-schedule.json")
    schedule_parser.add_argument("--now", help="带时区的构造时间；省略时为真实本机时钟。")
    schedule_parser.add_argument("--offline", action="store_true", help="显式模拟断网；不检测实际微信可达性。")
    schedule_parser.add_argument("--hold", type=float, default=0, help="用于真实重叠进程测试。")
    config_parser = commands.add_parser("config")
    config_parser.add_argument("--output", type=Path, required=True)
    replay_parser = commands.add_parser("replay")
    replay_parser.add_argument("--input", type=Path, required=True)
    replay_parser.add_argument("--state", type=Path, required=True)
    replay_parser.add_argument("--start-at", required=True)
    notify_parser = commands.add_parser("notify")
    notify_parser.add_argument("--event", choices=("complete", "partial", "failed", "login_required"), required=True)
    notify_parser.add_argument("--count", type=int, default=0)
    notify_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == 'page-sample':
            from datetime import datetime, timezone
            from liumo.archive import archive_article
            from liumo.rss import discover
            from liumo.common import timestamp
            item = {**discover()[0], 'first_seen_at':timestamp()}
            output = ROOT/'archives/mvp-samples'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            result = {'output':str(output), 'technical_sample_only':True,
                      **archive_article(item,output,headed=args.headed,wait_readable=args.wait_readable)}
        elif args.command == "archive":
            if args.interactive and (not args.headed or not sys.stdin.isatty()):
                raise ValueError("interactive_requires_headed_terminal")
            from .archive import archive
            from .source import profile_path
            result = archive(article_url(SAMPLES[args.sample]), profile=profile_path("article") if args.session else None,
                             headed=args.headed, interactive=args.interactive)
        elif args.command == "fixture":
            from urllib.parse import urlsplit
            from .archive import archive
            if args.url:
                if urlsplit(args.url).hostname not in {"127.0.0.1", "localhost"}:
                    raise ValueError("fixture_must_be_local")
                url = args.url
            else:
                file = args.file.resolve()
                if not file.is_relative_to(ROOT / "examples/pages") or not file.is_file():
                    raise ValueError("fixture_must_be_in_examples")
                url = file.as_uri()
            result = archive(url, fixture=True)
        elif args.command == "login":
            from .source import login
            result = login(args.site, args.sample, args.auto_wait)
        elif args.command == "weread-plan":
            from .source import review_plan
            result = review_plan()
        elif args.command == "discover":
            from .source import discover
            result = discover(args.book_id, args.account, args.max_pages)
        elif args.command == "http-archive":
            from .http_archive import archive_http
            result = archive_http(args.sample, args.credentialed, args.transport)
        elif args.command == "sample-check":
            from .sample_check import check_samples
            result = check_samples(args.transport, args.browser)
        elif args.command == "sample-check-bridge":
            from .curl_bridge import run_bridge
            result = run_bridge()
        elif args.command == "mp-diagnose-bridge":
            from .curl_bridge import run_bridge
            result = run_bridge(source=True)
        elif args.command == "profile-context-bridge":
            from .curl_bridge import run_bridge
            result = run_bridge(context=True)
        elif args.command == "profile-context":
            from .profile_context import check_profile_contexts
            from .http import WechatHTTP
            result = check_profile_contexts(WechatHTTP())
        elif args.command.startswith("html-static-"):
            from . import html_static_session
            duplicate = args.command.startswith("html-static-duplicates-")
            inline = args.command.startswith("html-static-inline-")
            metadata = args.command.startswith("html-static-metadata-")
            if inline:
                html_static_session.select_inline_mode()
            elif duplicate:
                html_static_session.select_duplicate_mode()
            elif metadata:
                html_static_session.select_metadata_mode()
            action = args.command.removeprefix("html-static-inline-" if inline else "html-static-duplicates-" if duplicate else "html-static-metadata-" if metadata else "html-static-")
            result = (html_static_session.observe(args.phase) if action == "observe" else
                      getattr(html_static_session, "review_plan" if action == "plan" else action)())
        elif args.command.startswith(("comment-baseline-", "comment-refresh-")):
            from . import comment_baseline
            refresh = args.command.startswith("comment-refresh-")
            if refresh:
                comment_baseline.select_refresh_mode()
            action = args.command.removeprefix("comment-refresh-" if refresh else "comment-baseline-")
            if action == "plan":
                result = comment_baseline.review_plan()
            elif action == "observe":
                result = comment_baseline.observe(args.phase)
            else:
                result = getattr(comment_baseline, {"session": "session", "recover": "recover", "finish": "finish", "compare": "compare"}[action])()
        elif args.command == "http-fixture":
            from .http_archive import fixture_http
            result = fixture_http()
        elif args.command == "capture-plan":
            from .capture_plan import review_plan
            result = review_plan()
        elif args.command == "capture-fixture":
            from .capture_plan import fixture_capture
            result = fixture_capture()
        elif args.command == "capture-preflight":
            from .capture_preflight import preflight
            result = preflight()
        elif args.command == "capture-session":
            from .capture_session import session
            result = session(args.baseline)
        elif args.command == "capture-recover":
            from .capture_session import manual_recover
            result = manual_recover()
        elif args.command == "profile-capture-session":
            from .capture_session import profile_session
            result = profile_session()
        elif args.command == "profile-capture-recover":
            from .capture_session import profile_manual_recover
            result = profile_manual_recover()
        elif args.command == "transport-diagnostic-session":
            from .capture_session import diagnostic_session
            result = diagnostic_session()
        elif args.command == "transport-diagnostic-recover":
            from .capture_session import diagnostic_manual_recover
            result = diagnostic_manual_recover()
        elif args.command == "ui-transport-diagnostic-session":
            from .capture_session import ui_diagnostic_session
            result = ui_diagnostic_session()
        elif args.command == "ui-transport-diagnostic-recover":
            from .capture_session import ui_diagnostic_manual_recover
            result = ui_diagnostic_manual_recover()
        elif args.command == "article-transport-diagnostic-session":
            from .capture_session import article_diagnostic_session
            result = article_diagnostic_session()
        elif args.command == "article-transport-diagnostic-recover":
            from .capture_session import article_diagnostic_manual_recover
            result = article_diagnostic_manual_recover()
        elif args.command == "mp-discover":
            from .mp_source import discover_profile
            result = discover_profile(args.account, args.max_pages, args.transport)
        elif args.command == "mp-diagnose":
            from .mp_source import diagnose_profile, diagnose_profiles
            result = diagnose_profiles(args.transport) if args.account == "all" else diagnose_profile(args.account, args.transport)
        elif args.command == "certificate-scope-fixture":
            from .certificate_scope import fixture
            result = fixture()
        elif args.command == "anchor-scope-session":
            from .anchor_scope import session
            result = session()
        elif args.command == "anchor-scope-recover":
            from .anchor_scope import manual_recover
            result = manual_recover()
        elif args.command == "wechat-compat-plan":
            from .wechat_compat import review_plan
            result = review_plan()
        elif args.command == "wechat-compat-fixture":
            from .wechat_compat import fixture
            result = fixture()
        elif args.command == "wechat-compat-session":
            from .compat_session import session
            result = session()
        elif args.command == "wechat-compat-recover":
            from .compat_session import manual_recover
            result = manual_recover()
        elif args.command == "wechat-compat-observe":
            from .compat_session import observe
            result = observe(args.phase)
        elif args.command == "wechat-compat-finish":
            from .compat_session import finish
            result = finish()
        elif args.command == "article-functional-session":
            from .functional_capture import session
            result = session()
        elif args.command == "article-functional-recover":
            from .functional_capture import recover
            result = recover()
        elif args.command == "article-functional-observe":
            from .functional_capture import observe
            result = observe(args.phase)
        elif args.command == "article-functional-finish":
            from .functional_capture import finish
            result = finish()
        elif args.command == "schedule":
            from .schedule import probe
            if not 0 <= args.hold <= 30:
                raise ValueError("invalid_hold")
            result = probe(args.state, parse_time(args.now) if args.now else None, not args.offline, args.hold)
            result["network_evidence"] = "flag_only_no_network_detection"
        elif args.command == "config":
            from .schedule import render_plist
            result = render_plist(args.output)
        elif args.command == "notify":
            from .notify import notify, render_event
            result = render_event(args.event, args.count) if args.dry_run else notify(args.event, args.count)
        else:
            from .state import empty_state, exclusive, ingest, pending
            payload = json.loads(args.input.read_text())
            with exclusive(args.state.with_suffix(".lock")):
                state = json.loads(args.state.read_text()) if args.state.exists() else empty_state()
                result = ingest(state, payload["pages"], args.start_at)
                write_json(args.state, state)
                result.update({"evidence": payload.get("evidence", "unclassified_input"), "pending": pending(state)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        incomplete = {"failed", "blocked", "partial", "not_verified", "list_observed_times_unverified", "list_shape_observed"}
        return 2 if (result.get("status") in incomplete or result.get("complete_scan") is False
                     or result.get("notification") == "failed") else 0
    except Exception as exc:
        # Do not print Playwright tracebacks containing credentials or full URLs.
        result = {"status": "failed", "error": error_kind(exc)}
        if args.command.startswith("html-static-"):
            from .comment_baseline import PUBLIC_FAILURE_REASONS
            from .http import ProbeError
            if isinstance(exc, ProbeError):
                safe = PUBLIC_FAILURE_REASONS | {'html_static_not_authorized', 'html_static_not_running'}
                result["reason"] = exc.reason if exc.reason in safe else "html_static_failed"
        if args.command.startswith(("comment-baseline-", "comment-refresh-")):
            from .comment_baseline import PUBLIC_FAILURE_REASONS
            from .http import ProbeError
            if isinstance(exc, ProbeError):
                result["reason"] = exc.reason if exc.reason in PUBLIC_FAILURE_REASONS else "comment_baseline_failed"
        if args.command in {"capture-session", "capture-recover", "profile-capture-session", "profile-capture-recover",
                            "transport-diagnostic-session", "transport-diagnostic-recover",
                            "ui-transport-diagnostic-session", "ui-transport-diagnostic-recover",
                            "article-transport-diagnostic-session", "article-transport-diagnostic-recover",
                            "anchor-scope-session", "anchor-scope-recover", "wechat-compat-session",
                            "wechat-compat-recover", "wechat-compat-observe", "wechat-compat-finish",
                            "article-functional-session", "article-functional-recover",
                            "article-functional-observe", "article-functional-finish"}:
            from .http import ProbeError
            if isinstance(exc, ProbeError):
                # These two local drivers generate fixed reason codes only.
                result["reason"] = exc.reason
        print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
