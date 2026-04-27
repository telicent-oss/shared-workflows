import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load the script file using a Python-safe module name.
script_path = os.path.join(os.path.dirname(__file__), 'metadata-updater.py')
spec = importlib.util.spec_from_file_location('metadata_updater', script_path)
metadata_updater = importlib.util.module_from_spec(spec)
sys.modules['metadata_updater'] = metadata_updater
spec.loader.exec_module(metadata_updater)

from metadata_updater import (
    ArgsFactory, Colours, Console, ChartProcessor
)


class TestArgsFactory(unittest.TestCase):
    def test_parse_default(self):
        args = ArgsFactory.parse(['--ci'])
        self.assertTrue(args.ci)
        self.assertEqual(args.include, [])
        self.assertEqual(args.exclude, [])

    def test_parse_include_exclude(self):
        args = ArgsFactory.parse(['--include', 'chart1', 'chart2', '--exclude', 'chart3'])
        self.assertFalse(args.ci)
        self.assertEqual(args.include, ['chart1', 'chart2'])
        self.assertEqual(args.exclude, ['chart3'])

    def test_parse_help_exits(self):
        with self.assertRaises(SystemExit):
            with patch('sys.stdout', new_callable=io.StringIO):
                ArgsFactory.parse(['--help'])


class TestColours(unittest.TestCase):
    def test_colours_defined(self):
        self.assertEqual(Colours.RED, '\033[91m')
        self.assertEqual(Colours.GREEN, '\033[92m')
        self.assertEqual(Colours.YELLOW, '\033[93m')
        self.assertEqual(Colours.BLUE, '\033[94m')
        self.assertEqual(Colours.NC, '\033[0m')


class TestConsole(unittest.TestCase):
    @patch('metadata_updater.sys.stdout.isatty', return_value=True)
    @patch('builtins.print')
    def test_print(self, mock_print, mock_isatty):
        # Test with multiple args, and every kwarg excel for `colour`.
        # The named functions that follow will test the `colour` kwarg.
        Console.print('test message', 'with kwargs\non multiple lines',
                      sep='//', indent=4, prefix='>> ', end=' <<')
        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        self.assertEqual((f'    {Colours.NC}>> test message//with kwargs\n'
                          f'    >> on multiple lines{Colours.NC}'), args[0])
        self.assertEqual(' <<', kwargs['end'])

    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    @patch('builtins.print')
    def test_print_with_no_colour(self, mock_print, mock_isatty):
        Console.print('test message', 'with kwargs\non multiple lines',
                      sep='//', indent=4, prefix='>> ', end=' <<')
        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        self.assertEqual(('    >> test message//with kwargs\n'
                          '    >> on multiple lines'), args[0])
        self.assertEqual(' <<', kwargs['end'])

    @patch('metadata_updater.sys.stdout.isatty', return_value=True)
    @patch('builtins.print')
    def test_info(self, mock_print, mock_isatty):
        Console.info('info message')
        args, _ = mock_print.call_args
        self.assertTrue(args[0].startswith(Colours.BLUE))
        self.assertTrue(args[0].endswith(Colours.NC))

    @patch('metadata_updater.sys.stdout.isatty', return_value=True)
    @patch('builtins.print')
    def test_success(self, mock_print, mock_isatty):
        Console.success('success message')
        args, _ = mock_print.call_args
        self.assertTrue(args[0].startswith(Colours.GREEN))
        self.assertTrue(args[0].endswith(Colours.NC))

    @patch('metadata_updater.sys.stdout.isatty', return_value=True)
    @patch('builtins.print')
    def test_warning(self, mock_print, mock_isatty):
        Console.warning('warning message')
        args, _ = mock_print.call_args
        self.assertTrue(args[0].startswith(Colours.YELLOW))
        self.assertTrue(args[0].endswith(Colours.NC))

    @patch('metadata_updater.sys.stdout.isatty', return_value=True)
    @patch('builtins.print')
    def test_error(self, mock_print, mock_isatty):
        Console.error('error message')
        args, _ = mock_print.call_args
        self.assertTrue(args[0].startswith(Colours.RED))
        self.assertTrue(args[0].endswith(Colours.NC))


class TestGetCharts(unittest.TestCase):

    @patch('pathlib.Path.glob')
    def test_get_charts_basic(self, mock_glob):
        mock_glob.return_value = [
            Path('charts/test-chart/Chart.yaml')
        ]
        charts = ChartProcessor.get_charts('charts', [], [])
        self.assertIn('test-chart', charts)
        self.assertEqual(charts['test-chart'], 'charts/test-chart')
        self.assertEqual(ChartProcessor.errors['chart_does_not_exist'], {})

    @patch('pathlib.Path.glob')
    def test_get_charts_exclude(self, mock_glob):
        mock_glob.return_value = [
            Path('charts/included1/Chart.yaml'),
            Path('charts/included2/Chart.yaml'),
            Path('charts/excluded/Chart.yaml')
        ]
        charts = ChartProcessor.get_charts('charts', [], ['charts/excluded'])
        self.assertIn('included1', charts)
        self.assertIn('included2', charts)
        self.assertNotIn('excluded', charts)

    @patch('pathlib.Path.glob')
    def test_get_charts_include(self, mock_glob):
        mock_glob.return_value = [
            Path('charts/included/Chart.yaml')
        ]
        charts = ChartProcessor.get_charts('charts', ['charts/included'], [])
        self.assertIn('included', charts)
        self.assertEqual(ChartProcessor.errors['chart_does_not_exist'], {})

    @patch('pathlib.Path.glob')
    def test_get_charts_include_missing(self, mock_glob):
        mock_glob.return_value = []
        charts = ChartProcessor.get_charts('charts', ['charts/missing'], [])
        self.assertEqual(charts, {})
        self.assertEqual(ChartProcessor.errors['chart_does_not_exist'], {'missing': 'charts/missing'})


class TestProcessChart(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.chart_dir = os.path.join(self.temp_dir, 'test-chart')
        os.makedirs(self.chart_dir)

        # Create required files
        with open(os.path.join(self.chart_dir, 'readme.config'), 'w') as f:
            f.write('config')
        with open(os.path.join(self.chart_dir, 'README.md'), 'w') as f:
            f.write(f'# test-chart\n\n## Parameters')
        with open(os.path.join(self.chart_dir, 'values.schema.json'), 'w') as f:
            f.write('{}')
        with open(os.path.join(self.chart_dir, 'values.yaml'), 'w') as f:
            f.write('key: value')
        # Clear errors
        ChartProcessor.errors = {
            'chart_does_not_exist': {},
            'missing_required_file': {},
            'missing_key': {},
            'non_existing_key': {}
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('metadata_updater.Console')
    def test_process_chart_success(self, mock_console, mock_exists, mock_run):
        mock_process = MagicMock()
        mock_run.return_value = mock_process
        mock_exists.return_value = True

        result = ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertTrue(result)
        self.assertEqual(ChartProcessor.errors['missing_key'], {})

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.print')
    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    def test_process_chart_success_outputs_expected_text(self, mock_isatty, mock_print, mock_exists, mock_run):
        mock_process = MagicMock()
        mock_run.return_value = mock_process
        mock_exists.return_value = True

        ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertEqual(mock_print.call_count, 2)
        self.assertEqual(mock_print.call_args_list[0][0][0], '\nProcessing chart: test-chart')
        self.assertEqual(mock_print.call_args_list[1][0][0], '  ✓ Completed test-chart')

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('metadata_updater.Console')
    def test_process_chart_failure_missing_key(self, mock_console, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(1, 'cmd', output='ERROR: Missing metadata for key')
        mock_exists.return_value = True

        result = ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertFalse(result)
        self.assertIn('test-chart', ChartProcessor.errors['missing_key'])

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.print')
    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    def test_process_chart_failure_missing_key_outputs_expected_text(self, mock_isatty, mock_print, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(1, 'cmd', output='ERROR: Missing metadata for key')
        mock_exists.return_value = True

        ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertEqual(mock_print.call_count, 4)
        self.assertEqual(mock_print.call_args_list[0][0][0], '\nProcessing chart: test-chart')
        self.assertEqual(mock_print.call_args_list[1][0][0], '  ✗ Failed to process test-chart (exit code: 1)')
        self.assertEqual(mock_print.call_args_list[2][0][0], '    | ERROR: Missing metadata for key')
        self.assertEqual(mock_print.call_args_list[3][0][0], '  ⚠ Metadata misconfiguration detected')

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('metadata_updater.Console')
    def test_process_chart_failure_non_existing_key(self, mock_console, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(1, 'cmd', output='ERROR: Metadata provided for non existing key')
        mock_exists.return_value = True

        result = ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertFalse(result)
        self.assertIn('test-chart', ChartProcessor.errors['non_existing_key'])

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.print')
    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    def test_process_chart_failure_non_existing_key_outputs_expected_text(self, mock_isatty, mock_print, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(1, 'cmd', output='ERROR: Metadata provided for non existing key')
        mock_exists.return_value = True

        ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertEqual(mock_print.call_count, 4)
        self.assertEqual(mock_print.call_args_list[0][0][0], '\nProcessing chart: test-chart')
        self.assertEqual(mock_print.call_args_list[1][0][0], '  ✗ Failed to process test-chart (exit code: 1)')
        self.assertEqual(mock_print.call_args_list[2][0][0], '    | ERROR: Metadata provided for non existing key')
        self.assertEqual(mock_print.call_args_list[3][0][0], '  ⚠ Metadata misconfiguration detected')

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('metadata_updater.Console')
    def test_process_chart_missing_values_file(self, mock_console, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(2, 'cmd', output='ERROR: no such file or directory: values.yaml')
        mock_exists.side_effect = lambda path: 'values.yaml' not in path

        result = ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertFalse(result)
        self.assertIn('test-chart', ChartProcessor.errors['missing_required_file'])

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.print')
    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    def test_process_chart_missing_values_file_outputs_expected_text(self, mock_isatty, mock_print, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(2, 'cmd', output='ERROR: no such file or directory: values.yaml')
        mock_exists.side_effect = lambda path: 'values.yaml' not in path

        ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertEqual(mock_print.call_count, 3)
        self.assertEqual(mock_print.call_args_list[0][0][0], '\nProcessing chart: test-chart')
        self.assertEqual(mock_print.call_args_list[1][0][0], '  ✗ Failed to process test-chart (exit code: 2)')
        self.assertEqual(mock_print.call_args_list[2][0][0], '    | ERROR: no such file or directory: values.yaml')

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('metadata_updater.Console')
    def test_process_chart_missing_readme_config_file(self, mock_console, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(2, 'cmd', output='ERROR: no such file or directory: readme.config')
        mock_exists.side_effect = lambda path: 'readme.config' not in path

        result = ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertFalse(result)
        self.assertIn('test-chart', ChartProcessor.errors['missing_required_file'])

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.print')
    @patch('metadata_updater.sys.stdout.isatty', return_value=False)
    def test_process_chart_missing_readme_config_file_outputs_expected_text(self, mock_isatty, mock_print, mock_exists, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(2, 'cmd', output='ERROR: no such file or directory: readme.config')
        mock_exists.side_effect = lambda path: 'readme.config' not in path

        ChartProcessor.process_chart('test-chart', self.chart_dir, 'echo test')
        self.assertEqual(mock_print.call_count, 3)
        self.assertEqual(mock_print.call_args_list[0][0][0], '\nProcessing chart: test-chart')
        self.assertEqual(mock_print.call_args_list[1][0][0], '  ✗ Failed to process test-chart (exit code: 2)')
        self.assertEqual(mock_print.call_args_list[2][0][0], '    | ERROR: no such file or directory: readme.config')


class TestPrintSummary(unittest.TestCase):
    @patch('metadata_updater.Console')
    def test_print_summary_success(self, mock_console):
        results = [('test-chart1', True), ('test-chart2', True)]
        ChartProcessor.errors = {
            'chart_does_not_exist': {},
            'missing_required_file': {},
            'missing_key': {},
            'non_existing_key': {}
        }

        ChartProcessor.print_summary(results)
        mock_console.success.assert_called()

    @patch('metadata_updater.Console')
    def test_print_summary_failure(self, mock_console):
        
        results = [('test-chart1', True), ('test-chart2', False)]
        ChartProcessor.errors = {
            'chart_does_not_exist': {},
            'missing_required_file': {},
            'missing_key': {'test-chart2': ['error']},
            'non_existing_key': {}
        }

        ChartProcessor.print_summary(results)
        mock_console.error.assert_called()


if __name__ == '__main__':
    unittest.main()
