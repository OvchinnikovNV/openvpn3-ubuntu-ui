import unittest
from unittest.mock import patch

from utils.openvpn3 import CommandResult, OpenVPN3, VpnSession


class TestOpenVPN3(unittest.TestCase):
    def setUp(self):
        OpenVPN3.clear_shutdown()

    def test_status_connected(self):
        self.assertTrue(OpenVPN3._status_is_connected('Connection, Client connected'))

    def test_status_failed(self):
        self.assertTrue(OpenVPN3._status_is_failed('Connection, Client authentication failed: Authentication failed'))

    def test_status_reconnect_not_connected(self):
        self.assertFalse(OpenVPN3._status_is_connected('Connection, Client reconnect'))

    def test_status_no_status_is_transient(self):
        self.assertTrue(OpenVPN3._status_is_transient('(No status)'))
        self.assertTrue(OpenVPN3._status_is_transient(''))
        self.assertTrue(OpenVPN3._status_is_transient('Connection, Client reconnect'))
        self.assertFalse(OpenVPN3._status_is_transient('Connection, Client connected'))

    def test_snapshot_list_unavailable(self):
        with patch.object(OpenVPN3, 'list_sessions', return_value=None):
            snap = OpenVPN3.snapshot_session('/p/1')
        self.assertTrue(snap.list_unavailable)

    def test_wait_retries_on_transient_missing(self):
        calls = {'n': 0}

        def fake_snapshot(path):
            calls['n'] += 1
            if calls['n'] < 3:
                return OpenVPN3.snapshot_session.__wrapped__(path) if False else type('S', (), {
                    'list_unavailable': False,
                    'connected': False,
                    'session': None,
                    'session_path': path,
                    'pending_auth': False,
                })()
            session = VpnSession(path, 'test.ovpn', 'Connection, Client connected')
            return type('S', (), {
                'list_unavailable': False,
                'connected': True,
                'session': session,
                'session_path': path,
                'pending_auth': False,
            })()

        with patch.object(OpenVPN3, 'snapshot_session', side_effect=fake_snapshot):
            with patch.object(OpenVPN3, '_trigger_web_auth_when_ready'):
                with patch.object(OpenVPN3, 'trigger_web_auth', return_value=False):
                    with patch.object(OpenVPN3, '_interruptible_sleep', return_value=False):
                        self.assertTrue(OpenVPN3.wait_for_session_ready('/p/1'))

    def test_wait_fails_on_auth_failed_status(self):
        session = VpnSession('/p/1', 'test.ovpn', 'Connection, Client authentication failed: Authentication failed')
        snap = type('S', (), {
            'list_unavailable': False,
            'connected': False,
            'session': session,
            'session_path': '/p/1',
            'pending_auth': False,
        })()
        with patch.object(OpenVPN3, 'snapshot_session', return_value=snap):
            with patch.object(OpenVPN3, '_trigger_web_auth_when_ready'):
                with patch.object(OpenVPN3, '_interruptible_sleep', return_value=False):
                    self.assertFalse(OpenVPN3.wait_for_session_ready('/p/1'))
        self.assertIn('authentication failed', OpenVPN3.last_error.lower())

    def test_auth_not_retriggered_twice(self):
        stdout = '---\nAuth Request: 12345\nPath: /p/1\n---\n'
        ok = CommandResult(stdout, '', 0)
        with patch.object(OpenVPN3, 'run_command', return_value=ok):
            self.assertTrue(OpenVPN3.trigger_web_auth('/p/1'))
            calls = OpenVPN3.run_command.call_count
            self.assertTrue(OpenVPN3.trigger_web_auth('/p/1'))
            self.assertEqual(OpenVPN3.run_command.call_count, calls + 1)


if __name__ == '__main__':
    unittest.main()
