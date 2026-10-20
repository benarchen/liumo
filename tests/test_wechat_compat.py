"""Offline real component verification; no installed trust or network sockets."""

import json
import math
import subprocess
from unittest.mock import patch

from test_validation import LocalTest
from validation.common import ROOT
from validation.wechat_compat import operation_budget, review_plan, RESTORE_STEPS


class CompatibilityBudgetTests(LocalTest):
    def test_complete_cleanup_reserve_does_not_fit_a_120_second_trial(self):
        plan = review_plan()
        self.assertEqual(sum(cost for _, cost in RESTORE_STEPS), 120)
        self.assertEqual(plan['active_budget_seconds'], 60)
        self.assertEqual(plan['duration_seconds_proposed'], 180)
        self.assertTrue(plan['system_experiment_authorized'])
        self.assertTrue(plan['system_runtime_implemented'])
        self.assertFalse(operation_budget(100, 1120, 100, 1000, 1))
        self.assertTrue(operation_budget(100, 1180, 100, 1000, 30))

    def test_wall_and_monotonic_clocks_both_limit_operations(self):
        self.assertTrue(operation_budget(100, 1180, 130, 1030, 30))
        self.assertFalse(operation_budget(100, 1180, 130.001, 1030, 30))
        self.assertFalse(operation_budget(100, 1180, 100, 1030.001, 30))
        self.assertFalse(operation_budget(100, 1180, 161, 900, 1))
        for bad in (math.nan, math.inf, True, 'PRIVATE'):
            with self.assertRaises(ValueError): operation_budget(100, 1180, 100, bad, 1)
        for size in (0, -1, 31):
            with self.assertRaises(ValueError): operation_budget(100, 1180, 100, 1000, size)
        with self.assertRaises(ValueError): operation_budget(100, 1180, 99, 1000, 1)

    def test_review_CLI_has_no_system_runtime(self):
        from validation.__main__ import main
        import io
        output = io.StringIO()
        with patch('sys.argv', ['validation', 'wechat-compat-plan']), patch('sys.stdout', output):
            self.assertEqual(main(), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result['system_or_network_operations_executed'])
        self.assertFalse(result['collect_credentials'])


class ActualCompatibilityTests(LocalTest):
    def run_isolated(self, code):
        python = ROOT / '.venv-capture/bin/python'
        if not python.exists(): self.skipTest('optional isolated component not installed')
        result = subprocess.run([str(python), '-c', code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_real_component_SAN_selection_and_34_TLS_checks_without_network(self):
        result = self.run_isolated(r'''
import json,socket,tempfile
from pathlib import Path
from unittest.mock import patch
from validation import wechat_compat as s
from validation.common import ROOT
actual_socket=socket.socket
def local_only(family=socket.AF_INET,*args,**kwargs):
 if family in (socket.AF_INET,socket.AF_INET6):raise AssertionError('network socket prohibited')
 return actual_socket(family,*args,**kwargs)
with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
 base=Path(raw)
 with patch.object(s,'ROOT',base),patch.object(socket,'socket',side_effect=local_only), \
      patch.object(socket,'create_connection',side_effect=AssertionError('network connection prohibited')), \
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS prohibited')):
  result=s.fixture(base/'output')
 report=json.loads((base/'output/compatibility.json').read_text())
 assert result['offline_checks_passed'] and report['matrix_passed']
 assert len(report['matrix_rows'])==30
 assert {x['case'] for x in report['matrix_rows']}=={x['id'] for x in s.cases() if x['id'] not in ('expired','bad_signature')}
 selection=report['component_selection']
 assert selection['passed'] and selection['configured_CA_preserved'] and selection['fixed_certificate_selected']
 assert selection['fixed_SAN']==['mp.weixin.qq.com']
 assert selection['default_selection_TLS']['control']['outcome']=='accepted'
 assert selection['default_selection_TLS']['root']['outcome']=='rejected'
 assert selection['fixed_selection_TLS']['outcome']=='accepted'
 assert selection['wrong_host_TLS']['outcome']=='rejected'
 assert selection['ssl_insecure'] is False and selection['upstream_cert'] is False
 assert selection['master_run_called'] is False
 assert report['temporary_directory_removed'] and not report['private_keys_retained']
 assert len(list((base/'output').glob('*.pem')))==20
 assert not any(b'PRIVATE KEY' in p.read_bytes() for p in (base/'output').iterdir())
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 before=(base/'output/root.pem').read_bytes()
 with patch.object(s,'ROOT',base):
  try:s.fixture(base/'output')
  except FileExistsError:pass
  else:raise AssertionError('existing output replaced')
 assert before==(base/'output/root.pem').read_bytes()
 print(json.dumps({'TLS_checks':34,'network_socket_allowed':False,'private_keys_retained':False}))
''')
        self.assertEqual(result, {'TLS_checks': 34, 'network_socket_allowed': False, 'private_keys_retained': False})

    def test_failure_paths_remove_keys_and_reject_bad_keypair(self):
        result = self.run_isolated(r'''
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from mitmproxy.exceptions import OptionsError
from validation import wechat_compat as s
from validation.common import ROOT
with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
 base=Path(raw)
 with patch.object(s,'ROOT',base),patch.object(s,'memory_verify',side_effect=RuntimeError('constructed failure')):
  try:s.fixture(base/'failed')
  except RuntimeError:pass
  else:raise AssertionError('failure hidden')
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 assert not any(b'PRIVATE KEY' in p.read_bytes() for p in (base/'failed').iterdir())
 original=s.prepare_store
 def mismatch(directory):
  m=original(directory)
  ca_key=serialization.load_pem_private_key(m['ca_bundle'].read_bytes(),password=None)
  private=ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
  m['target_bundle'].write_bytes(private+m['target_leaf'].read_bytes()+m['root'].read_bytes())
  return m
 with patch.object(s,'ROOT',base),patch.object(s,'prepare_store',side_effect=mismatch):
  try:s.fixture(base/'mismatch')
  except (ValueError,OptionsError):pass
  else:raise AssertionError('wrong private key accepted')
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 assert not any(b'PRIVATE KEY' in p.read_bytes() for p in (base/'mismatch').iterdir())
 def missing_key(directory):
  m=original(directory);m['ca_bundle'].unlink();return m
 with patch.object(s,'ROOT',base),patch.object(s,'prepare_store',side_effect=missing_key):
  try:s.fixture(base/'missing')
  except s.ProbeError:pass
  else:raise AssertionError('missing CA key silently regenerated')
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 with patch.object(s,'ROOT',base),patch.object(s,'memory_verify',return_value={'outcome':'not_verified','reason':'constructed_unknown'}):
  result=s.fixture(base/'unknown')
 assert result['status']=='failed' and not result['offline_checks_passed']
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 print(json.dumps({'failure_cleanup':True,'key_mismatch_rejected':True}))
''')
        self.assertTrue(result['failure_cleanup'])
        self.assertTrue(result['key_mismatch_rejected'])

    def test_existing_symlink_and_wide_parent_rejected_and_key_files_private(self):
        result = self.run_isolated(r'''
import json,tempfile,stat
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from validation import wechat_compat as s
from validation.common import ROOT
with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
 base=Path(raw);store=base/'store';m=s.prepare_store(store)
 assert stat.S_IMODE(store.stat().st_mode)==0o700
 assert all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in store.iterdir())
 ca=x509.load_pem_x509_certificate(m['root'].read_bytes())
 nc=ca.extensions.get_extension_for_class(x509.NameConstraints)
 assert nc.critical and [n.value for n in nc.value.permitted_subtrees]==['mp.weixin.qq.com']
 assert [str(n.value) for n in nc.value.excluded_subtrees]==['.mp.weixin.qq.com','0.0.0.0/0','::/0']
 leaf=x509.load_pem_x509_certificate(m['target_leaf'].read_bytes());leaf.verify_directly_issued_by(ca)
 ca_key=serialization.load_pem_private_key(m['ca_bundle'].read_bytes(),password=None)
 leaf_key=serialization.load_pem_private_key(m['target_bundle'].read_bytes(),password=None)
 assert ca_key.public_key().public_numbers()!=leaf_key.public_key().public_numbers()
 before=m['ca_bundle'].read_bytes()
 try:s.prepare_store(store)
 except FileExistsError:pass
 else:raise AssertionError('existing store replaced')
 assert before==m['ca_bundle'].read_bytes()
 symlink=base/'symlink';symlink.symlink_to(store)
 try:s.prepare_store(symlink)
 except FileExistsError:pass
 else:raise AssertionError('symlink accepted')
 wide=base/'wide';wide.mkdir(mode=0o755);wide.chmod(0o755)
 try:s.prepare_store(wide/'store')
 except s.ProbeError:pass
 else:raise AssertionError('wide parent accepted')
 assert not (wide/'store').exists()
 print(json.dumps({'private_modes':True,'CA_leaf_keys_distinct':True,'invalid_paths_rejected':True}))
''')
        self.assertEqual(result, {'private_modes': True, 'CA_leaf_keys_distinct': True, 'invalid_paths_rejected': True})
