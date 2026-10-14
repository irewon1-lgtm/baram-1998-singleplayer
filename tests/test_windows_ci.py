"""Regression tests for release blocking and preservation, not a GUI PASS."""
from pathlib import Path
import json
import os
import sys
import tempfile
import subprocess
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import windows_ci

class WindowsCIGates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
        self.args=SimpleNamespace(out=str(self.out),require_windows=True)
    def tearDown(self):self.tmp.cleanup()
    def report(self,**changes):
        value={'status':'PASS','game_function_automation':'PASS','windows_native_execution':'PASS','source_sha':'a'*40}
        value.update(changes);windows_ci.write_json(self.out/'verification.json',value)
    def test_failed_game_tests_block_zip_before_stage_access(self):
        self.report(status='FAIL')
        with self.assertRaisesRegex(ValueError,'Verification gate'):windows_ci.archive(self.args)
        self.assertEqual(list(self.out.glob('*.zip')),[])
    def test_linux_execution_cannot_be_native_pass(self):
        self.report(windows_native_execution='NOT_RUN_LINUX_EMBEDDED_PCK_ONLY')
        with self.assertRaisesRegex(ValueError,'Windows-native'):windows_ci.archive(self.args)
    def test_public_actions_cannot_archive_private_payload(self):
        self.report()
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','BARAM_PRIVATE_REPOSITORY':'false'}):
            with self.assertRaisesRegex(ValueError,'Public repository'):windows_ci.archive(self.args)
    def test_unknown_files_and_saves_cannot_enter_runtime(self):
        for name in ['private_assets','private_content','licenses']:(self.out/name).mkdir()
        windows_ci.write_json(self.out/'PACKAGE_MANIFEST.json',{'files':[],'private_only':True,'contains_user_saves':False})
        (self.out/'private_assets/unknown.png').write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'membership'):windows_ci.validate_runtime(self.out)
    @unittest.skipUnless(os.name=='nt','Windows process memory API')
    def test_windows_memory_monitor_observes_a_real_child(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'])
        try:
            samples=[]
            for _ in range(10):
                samples.append(windows_ci.process_rss(child.pid));time.sleep(.05)
            self.assertGreater(max(samples),1024*1024)
        finally:child.terminate();child.wait()

if __name__=='__main__':unittest.main()
