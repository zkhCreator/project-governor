"""Purpose: Regress isolated simulator selection without weakening the configured UI evidence matrix.
Responsibilities: Check runtime requirements, exact device targeting and all language/appearance/scenario combinations.
Inputs/Outputs: A synthetic simulator inventory and mocked process/file outputs produce real routing and check results.
Non-goals: Does not claim iOS behavior or validate actual screenshots; existing runtime tests remain required.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from project_governor.cli import build_parser
from project_governor.ios import resolve_runtime_devices
from project_governor.checks import run_ui_checks
from project_governor.util import CommandResult

INVENTORY = {'simulator_devices': [
    {'udid': 'legacy', 'name': 'iPhone', 'runtime': '17.0'},
    {'udid': 'shared', 'name': 'iPhone', 'runtime': '26.5'},
    {'udid': 'isolated', 'name': 'iPhone', 'runtime': '26.5'},
]}

class UIDeviceSelectionTests(unittest.TestCase):
    def test_explicit_device_wins_over_same_name_shared_device(self):
        devices, missing = resolve_runtime_devices(INVENTORY, '17.0', False, ['isolated'])
        self.assertEqual([d['udid'] for d in devices], ['isolated'])
        self.assertEqual(missing, [])

    def test_explicit_device_cannot_waive_legacy_or_modern_requirements(self):
        for ids in [['isolated'], ['legacy'], [], ['missing'], ['isolated', 'isolated'], ['shared', 'isolated', 'legacy']]:
            with self.subTest(ids=ids):
                self.assertTrue(resolve_runtime_devices(INVENTORY, '17.0', True, ids)[1])
        devices, missing = resolve_runtime_devices(INVENTORY, '17.0', True, ['legacy', 'isolated'])
        self.assertEqual({d['udid'] for d in devices}, {'legacy', 'isolated'})
        self.assertFalse(missing)

    def test_cli_preserves_each_explicit_runtime_device(self):
        args = build_parser().parse_args(['verify', '--change-id', 'fixture', '--ui-device', 'legacy', '--ui-device', 'isolated'])
        self.assertEqual(args.ui_device, ['legacy', 'isolated'])

    def test_matrix_and_attachments_still_required_on_exact_device(self):
        project = {'container': 'App.xcworkspace', 'container_type': 'workspace', 'scheme': 'App',
                   'ios': {'minimum_version': '17.0', 'languages': ['en', 'zh-Hans'], 'appearances': ['light', 'dark']},
                   'ui_scenarios': [{'id': 'first', 'test_identifier': 'UITests/First'}, {'id': 'second', 'test_identifier': 'UITests/Second'}]}
        calls = []
        def execute(argv, **kwargs):
            if argv[0] == 'xcodebuild':
                calls.append(argv)
                Path(argv[argv.index('-resultBundlePath') + 1]).mkdir()
            else:
                folder = Path(argv[argv.index('--output-path') + 1]); folder.mkdir()
                (folder / 'fixture.png').write_bytes(b'unit-test-attachment')
            return CommandResult(list(argv), 0, '', '')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('project_governor.checks.inspect_project', return_value=INVENTORY), patch('project_governor.checks.run_command', side_effect=execute):
                result = run_ui_checks(root, project, root / 'evidence', False, ['isolated'])
            self.assertEqual(result['status'], 'pass')
            self.assertEqual(len(calls), 8)
            self.assertTrue(all(c[c.index('-destination') + 1] == 'platform=iOS Simulator,id=isolated' for c in calls))
            self.assertEqual({r['device_udid'] for r in result['runs']}, {'isolated'})
            self.assertTrue(all(len(r['attachments']) == 1 for r in result['runs']))
            with patch('project_governor.checks.inspect_project', return_value=INVENTORY), patch('project_governor.checks.run_command') as runner:
                blocked = run_ui_checks(root, project, root / 'other', True, ['isolated'])
            self.assertEqual(blocked['status'], 'blocked')
            runner.assert_not_called()
