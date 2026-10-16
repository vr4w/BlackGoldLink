"""Nginx reload is asynchronous: retry its old gate, never accept it as public."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('public_entry',Path(__file__).resolve().parents[1]/'deployment/activate-public-entry.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)


class PublicEntry(unittest.TestCase):
    def test_old_worker_gate_is_retried_until_new_configuration_answers(self):
        with patch.object(entry.subprocess,'check_output',side_effect=['401','401','200','302','302','302']) as probe,patch.object(entry.time,'sleep') as sleep:
            entry.wait_for_routes('https://bgl.example')
            self.assertEqual(sleep.call_count,2)
            self.assertEqual(probe.call_count,6)
            self.assertEqual(probe.call_args.args[0][-1],'https://bgl.example/api/friends')
            for call in probe.call_args_list:self.assertNotIn('--insecure',call.args[0])

    def test_persistent_gate_fails_for_rollback(self):
        with patch.object(entry.subprocess,'check_output',return_value='401'),patch.object(entry.time,'monotonic',side_effect=[0,31]):
            with self.assertRaisesRegex(RuntimeError,'/ 401'):entry.wait_for_routes('https://bgl.example')

    def test_public_landing_does_not_allow_anonymous_member_data(self):
        with patch.object(entry.subprocess,'check_output',side_effect=['200','200']),patch.object(entry.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'/app 200'):entry.wait_for_routes('https://bgl.example')
            sleep.assert_not_called()

    def test_certificate_or_connection_error_is_not_ignored(self):
        with patch.object(entry.subprocess,'check_output',side_effect=subprocess.CalledProcessError(60,['curl'])),patch.object(entry.time,'sleep') as sleep:
            with self.assertRaises(subprocess.CalledProcessError):entry.wait_for_routes('https://bgl.example')
            sleep.assert_not_called()
