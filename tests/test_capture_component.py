"""Installed component header objects, not real TLS interception."""

import json
import subprocess
import unittest

from validation.common import ROOT


class InstalledComponentTests(unittest.TestCase):
    def test_diagnostic_only_real_component_blocks_credentials_and_separates_control(self):
        python = ROOT / '.venv-capture/bin/python'
        if not python.exists():
            self.skipTest('optional isolated capture component not installed')
        code = r'''
import asyncio, json, os, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from mitmproxy import http, connection, tls
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from validation import capture_plan, capture_session
from validation.mitm_addon import WechatCaptureAddon
from validation.transport_diagnostic import CONTROL_URL
os.umask(0o077)
actual_root = capture_session.ROOT
async def check():
 with tempfile.TemporaryDirectory(dir=actual_root / '.tmp/wechat-session-validation') as temporary:
  root = Path(temporary)
  directory = root/'.auth/wechat-capture/diagnostic-session'
  directory.mkdir(parents=True, mode=0o700)
  for path in (root/'.auth', directory.parent): path.chmod(0o700)
  capture_plan.ROOT = capture_session.ROOT = root
  capture_session.SESSION = directory
  proxy = {'Enabled':'Yes','Server':'127.0.0.1','Port':'7897','Authenticated Proxy Enabled':'0'}
  plan = {'version':1,'experiment':'diagnostic','duration_seconds':120,
          'baseline':{'active_service':'Wi-Fi','https_proxy':proxy,'http_proxy':dict(proxy),'pac':{'Enabled':'No'},
                      'autodiscovery':'Auto Proxy Discovery: Off','bypass_domains':['localhost'],'review_reasons':[]},
          'mode':'upstream:http://127.0.0.1:7897','ca_name':'liumo-CONSTRUCTED-DIAGNOSTIC','wall_deadline':time.time()+120}
  capture_session.private_write(directory/'plan.json', plan)
  capture_session.private_write(directory/'state.json', {'capture_disabled':False})
  capture_session.Native(plan).prepare_ca()
  assert capture_session.private_json(directory/'recovery-plan.json')['recommended_entry'][-1]=='transport-diagnostic-recover'
  opts = Options(confdir=str(directory/'mitmproxy'), mode=[plan['mode']], server=False)
  master = DumpMaster(opts, with_termlog=False)
  if not hasattr(opts,'termlog_verbosity'): opts.add_option('termlog_verbosity',str,'error','No output.')
  opts.update(listen_host='127.0.0.1',listen_port=8899,allow_hosts=[capture_plan.ALLOW_HOST],ssl_insecure=False,
              flow_detail=0,show_ignored_hosts=False,store_streamed_bodies=False,command_history=False,strip_ech=False)
  addon = WechatCaptureAddon()
  master.addons.add(addon)
  opts.update(liumo_capture=True,liumo_diagnostic_only=True,liumo_capture_seconds=120)
  assert addon.runtime_directory==directory
  for url in (CONTROL_URL, 'https://mp.weixin.qq.com/mp/profile_ext?key=PRIVATE'):
   flow = SimpleNamespace(request=http.Request.make('GET',url),response=http.Response.make(200,b'BODY_NOT_READ'))
   addon.requestheaders(flow)
   addon.responseheaders(flow)
   assert flow.request.stream and flow.response.stream
  assert addon.diagnostics['control_target_responses_seen']==1
  assert addon.diagnostics['target_host_responses_seen']==1
  assert addon.session.summary()['saved_by_account']=={}
  assert not (directory/'requests').exists()
  client = connection.Client(peername=('127.0.0.1', 10001), sockname=('127.0.0.1', 10002), sni='mp.weixin.qq.com')
  client.error = 'tlsv1 alert unknown ca PRIVATE_ERROR'
  addon.tls_failed_client(tls.TlsData(conn=client, context=None))
  assert addon.diagnostics['tls_client_target_reason_certificate_alert']==1
  assert 'PRIVATE' not in json.dumps(addon.diagnostics)
  capture_session.private_write(directory/'state.json', {'capture_disabled':True})
  addon.capture_disabled()
  assert addon.session.stopped and addon.passthrough_only
  addon.done()
  master.shutdown()
asyncio.run(check())
print(json.dumps({'diagnostic_component':'passed','system_changes':False,'listener_started':False,'network_requests':0}))
'''
        for ui in (False, True):
            variant = code
            if ui:
                variant = (code.replace('diagnostic-session', 'ui-diagnostic-session')
                           .replace("'experiment':'diagnostic'", "'experiment':'ui_diagnostic'")
                           .replace("'transport-diagnostic-recover'", "'ui-transport-diagnostic-recover'")
                           .replace('liumo_diagnostic_only=True,', 'liumo_diagnostic_only=True,liumo_ui_diagnostic=True,'))
            with self.subTest(ui=ui):
                result = subprocess.run([str(python), '-c', variant], cwd=ROOT, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'diagnostic_component': 'passed', 'system_changes': False,
                                                            'listener_started': False, 'network_requests': 0})

    def test_profile_mode_real_component_headers_options_and_recovery_hint(self):
        python = ROOT / '.venv-capture/bin/python'
        if not python.exists():
            self.skipTest('optional isolated capture component not installed')
        code = r'''
import asyncio, json, os, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from validation import capture_plan, capture_session
from validation.mitm_addon import WechatCaptureAddon
from validation.capture import TARGETS
os.umask(0o077)
actual_root = capture_session.ROOT
async def check():
 with tempfile.TemporaryDirectory(dir=actual_root / '.tmp/wechat-session-validation') as temporary:
  root = Path(temporary)
  directory = root / '.auth/wechat-capture/profile-session'
  directory.mkdir(parents=True, mode=0o700)
  for path in (root/'.auth', directory.parent): path.chmod(0o700)
  (directory/'requests').mkdir(mode=0o700)
  capture_plan.ROOT = capture_session.ROOT = root
  capture_session.SESSION = directory
  proxy = {'Enabled':'Yes','Server':'127.0.0.1','Port':'7897','Authenticated Proxy Enabled':'0'}
  plan = {'version':1,'experiment':'profile','baseline':{'active_service':'Wi-Fi','https_proxy':proxy,'http_proxy':dict(proxy),
          'pac':{'Enabled':'No'},'autodiscovery':'Auto Proxy Discovery: Off','bypass_domains':['localhost'],'review_reasons':[]},
          'mode':'upstream:http://127.0.0.1:7897','ca_name':'liumo-CONSTRUCTED-PROFILE','wall_deadline':time.time()+600}
  capture_session.private_write(directory/'plan.json', plan)
  capture_session.private_write(directory/'state.json', {'capture_disabled':False})
  native = capture_session.Native(plan)
  native.prepare_ca()
  assert capture_session.private_json(directory/'recovery-plan.json')['recommended_entry'][-1] == 'profile-capture-recover'
  opts = Options(confdir=str(directory/'mitmproxy'), mode=[plan['mode']], server=False)
  master = DumpMaster(opts, with_termlog=False)
  if not hasattr(opts,'termlog_verbosity'): opts.add_option('termlog_verbosity',str,'error','No test output.')
  opts.update(listen_host='127.0.0.1',listen_port=8899,allow_hosts=[capture_plan.ALLOW_HOST],ssl_insecure=False,
              flow_detail=0,show_ignored_hosts=False,store_streamed_bodies=False,command_history=False,strip_ech=False)
  addon = WechatCaptureAddon()
  master.addons.add(addon)
  opts.update(liumo_capture=True,liumo_profile_capture=True)
  assert addon.runtime_directory == directory
  biz = next(biz for biz,row in TARGETS.items() if row['account']=='猫笔刀')
  url = 'https://mp.weixin.qq.com/mp/profile_ext?' + urlencode({'action':'getmsg','__biz':biz,'key':'FAKE_KEY',
        'uin':'FAKE_UIN','pass_ticket':'FAKE_PASS','offset':'0','count':'10','unknown':'DISCARD'})
  flow = SimpleNamespace(request=http.Request.make('GET',url,headers={'User-Agent':'CONSTRUCTED',
                         'Cookie':'poc_sid=FAKE_SID; unrelated=DISCARD'}),
                         response=http.Response.make(200,b'BODY_MUST_NOT_BE_READ'))
  addon.requestheaders(flow)
  addon.responseheaders(flow)
  assert flow.request.stream and flow.response.stream
  value = capture_session.private_json(directory/'requests/maobidao-getmsg.json')
  assert value['omitted_query_fields']==1 and 'DISCARD' not in json.dumps(value)
  capture_session.private_write(directory/'state.json',{'capture_disabled':True})
  addon.capture_disabled()
  assert addon.session.stopped and addon.passthrough_only
  assert opts.allow_hosts == [r'(?!)']
  addon.done()
  master.shutdown()
asyncio.run(check())
print(json.dumps({'profile_component':'passed','system_changes':False,'listener_started':False,'network_requests':0}))
'''
        result = subprocess.run([str(python), '-c', code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'profile_component': 'passed', 'system_changes': False,
                                                    'listener_started': False, 'network_requests': 0})

    def test_real_component_CA_and_upstream_options_without_OS_trust_or_listener(self):
        python = ROOT / ".venv-capture/bin/python"
        if not python.exists() or not (ROOT / ".venv-capture/bin/mitmdump").exists():
            self.skipTest("optional isolated capture component not installed; initialization not verified")
        code = r'''
import asyncio, json, os, stat, tempfile, time
from pathlib import Path
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from cryptography import x509
from validation import capture_plan, capture_session
from validation.mitm_addon import WechatCaptureAddon
os.umask(0o077)
actual_root = capture_session.ROOT
async def check():
 with tempfile.TemporaryDirectory(dir=actual_root / ".tmp/wechat-session-validation") as temporary:
  root = Path(temporary)
  directory = root / ".auth/wechat-capture/session"
  directory.mkdir(parents=True, mode=0o700)
  for path in [root/".auth", directory.parent]: path.chmod(0o700)
  capture_plan.ROOT = capture_session.ROOT = root
  capture_session.SESSION = directory
  proxy = {"Enabled":"Yes", "Server":"127.0.0.1", "Port":"7897", "Authenticated Proxy Enabled":"0"}
  baseline = {"active_service":"Wi-Fi", "https_proxy":proxy, "http_proxy":dict(proxy),
              "pac":{"Enabled":"No"}, "autodiscovery":"Auto Proxy Discovery: Off",
              "bypass_domains":["localhost"], "review_reasons":[]}
  plan = {"version":1, "baseline":baseline, "mode":"upstream:http://127.0.0.1:7897", "ca_name":"liumo-CONSTRUCTED-TEST", "wall_deadline":time.time()+600}
  capture_session.private_write(directory / "plan.json", plan)
  native = capture_session.Native(plan, directory)
  fingerprint = native.prepare_ca()
  assert len(fingerprint) == 64
  recovery_plan = capture_session.private_json(directory / "recovery-plan.json")
  assert recovery_plan["certificate_sha256"] == fingerprint
  assert recovery_plan["restore_proxy_argv"][-2:] == ["7897", "off"]
  leaf = x509.load_pem_x509_certificate((directory / "scope-probe.pem").read_bytes())
  names = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
  assert set(names) == {"mp.weixin.qq.com", "liumo-scope-check.invalid"}
  assert stat.S_IMODE((directory / "mitmproxy/mitmproxy-ca.pem").stat().st_mode) == 0o600
  opts = Options(confdir=str(directory / "mitmproxy"), mode=[plan["mode"]], server=False)
  master = DumpMaster(opts, with_termlog=False)
  if not hasattr(opts, "termlog_verbosity"):
   opts.add_option("termlog_verbosity", str, "error", "No output in constructed test.")
  opts.update(listen_host="127.0.0.1", listen_port=8899, allow_hosts=[capture_plan.ALLOW_HOST],
              ssl_insecure=False, flow_detail=0, show_ignored_hosts=False, store_streamed_bodies=False,
              command_history=False, strip_ech=False)
  capture_plan.check_proxy_options(opts)
  addon = WechatCaptureAddon()
  master.addons.add(addon)
  opts.update(liumo_capture=True, liumo_capture_seconds=1)
  assert addon.runtime_directory == directory
  assert addon.session is not None
  capture_session.private_write(directory / "state.json", {"capture_disabled":True})
  addon.running()
  await asyncio.sleep(0.3)
  assert opts.liumo_capture is False and opts.allow_hosts == [r"(?!)"]
  assert addon.session.stopped and addon.passthrough_only
  (directory / "STOP").touch()
  await asyncio.sleep(0.3)
  assert capture_session.private_json(directory / "capture.json")["running"] is False
  addon.done()
  master.shutdown()
asyncio.run(check())
print(json.dumps({"test_CA_generated_and_removed":True, "upstream_options_checked":True,
                  "system_trust_changed":False, "listener_started":False, "network_requests":0}))
'''
        result = subprocess.run([str(python), "-c", code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"test_CA_generated_and_removed": True,
            "upstream_options_checked": True, "system_trust_changed": False, "listener_started": False,
            "network_requests": 0})

    def test_real_component_headers_match_without_network_or_credentials(self):
        python = ROOT / ".venv-capture/bin/python"
        if not python.exists() or not (ROOT / ".venv-capture/bin/mitmdump").exists():
            self.skipTest("optional isolated capture component not installed; integration not verified")
        code = r'''
import json
from types import SimpleNamespace
from urllib.parse import urlencode
from mitmproxy import http
from validation.capture import CaptureSession
from validation.mitm_addon import WechatCaptureAddon
target = {"FIXTURE_BIZ": {"account": "猫笔刀", "mid": "100", "idx": "1"}}
query = urlencode({"__biz": "FIXTURE_BIZ", "mid": "100", "idx": "1", "uin": "FAKE_UIN",
                   "key": "FAKE_KEY", "pass_ticket": "FAKE_PASS"})
request = http.Request.make("GET", "https://mp.weixin.qq.com/s?" + query,
                            headers={"Cookie": "appmsg_token=OLD; unrelated=DISCARD"})
response = http.Response.make(200, b"", headers=http.Headers([
    (b"Set-Cookie", b"appmsg_token=FAKE_TOKEN; Secure; HttpOnly"),
    (b"Set-Cookie", b"wap_sid2=FAKE_SID; Secure")]))
flow = SimpleNamespace(request=request, response=response)
saved = []
addon = WechatCaptureAddon()
addon.session = CaptureSession(targets=target, writer=saved.append)
from mitmproxy import connection, tls
client = connection.Client(peername=('127.0.0.1', 10001), sockname=('127.0.0.1', 10002), sni='mp.weixin.qq.com')
addon.tls_failed_client(tls.TlsData(conn=client, context=None))
assert addon.diagnostics['tls_client_failures_target'] == 1
addon.requestheaders(flow)
addon.responseheaders(flow)
assert len(saved) == 1 and saved[0]["appmsg_token"] == "FAKE_TOKEN"
assert "DISCARD" not in saved[0]["cookie"]
assert request.stream and response.stream
addon.done()
addon.responseheaders(flow)
assert len(saved) == 1
print(json.dumps({"header_events": "passed", "network_requests": 0, "credentials_written": 0}))
'''
        result = subprocess.run([str(python), "-c", code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, "isolated component header integration failed")
        self.assertEqual(json.loads(result.stdout), {"header_events": "passed", "network_requests": 0,
                                                    "credentials_written": 0})
