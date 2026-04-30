from collections import OrderedDict
from pathlib import Path
import argparse
import doctest
import os
import re
import shlex
import subprocess
import sys
import textwrap


class ArgsFactory:
    '''Factory for an argument parser that defines the arguments required for
    this script.
    '''

    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=52)
    parser = argparse.ArgumentParser(add_help=False, formatter_class=formatter,
        description='Run metadata updates for Helm charts.')
    parser.add_argument('--help', '-h', action='help',
        help='Show this help message and exit.')
    parser.add_argument('--ci', '-c', action='store_true', default=False,
        help='Indicate execution is happening in a CI environment.')
    parser.add_argument('--path', '-p', default='./charts',
        help=('The path to the Helm charts to inspect. Assumes ./charts if '
            'omitted.'))
    parser.add_argument('--include', '-i', nargs='*', metavar='chart',
        help=('A space separated list of charts to include. Paths should be '
            'relative to the root of the repository. Takes precedence '
            'over `--exclude`.'), default=[])
    parser.add_argument('--exclude', '-e', nargs='*', metavar='chart',
        help=('A space separated list of charts to exclude. Paths should be '
            'relative to the root of the repository. Ignored if `--include` '
            'is specified.'), default=[])

    @staticmethod
    def parse(args: list=None) -> argparse.Namespace:
        '''Parse arguments as defined in the argument parser.

        @param args: A list of arguments to parse. Defaults to `sys.argv`.

        Example
        -------
        >>> ArgsFactory.parse(['--ci', '--exclude', 'charts/test-chart'])
        Namespace(ci=True, path='./charts', include=[], exclude=['charts/test-chart'])
        >>> ArgsFactory.parse(['--ci', '--path', './different-path', '--include', 'charts/test-chart'])
        Namespace(ci=True, path='./different-path', include=['charts/test-chart'], exclude=[])
        >>> ArgsFactory.parse(['--help'])
        Traceback (most recent call last):
        SystemExit: 0
        '''
        return ArgsFactory.parser.parse_args(args)


class Colours:
    '''Define colours for console output.
    
    Example
    -------
    >>> print(f'{Colours.RED}Red text.{Colours.NC}')
    \033[91mRed text.\033[0m
    >>> print(f'{Colours.GREEN}Green text.{Colours.NC}')
    \033[92mGreen text.\033[0m
    >>> print(f'{Colours.YELLOW}Yellow text.{Colours.NC}')
    \033[93mYellow text.\033[0m
    >>> print(f'{Colours.BLUE}Blue text.{Colours.NC}')
    \033[94mBlue text.\033[0m
    '''
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    NC = '\033[0m'


class Console:
    '''Define console output methods for different message types.'''

    @classmethod
    def print(cls, *objects, sep=' ', colour: Colours=Colours.NC, indent: int=0,
              prefix: str='', end: str='\n') -> None:
        '''Prints a message to the console.

        @param objects: Objects stringify that will be joined to make a message.
        @param sep: The separator to join objects with.
        @param colour: The colour to print the message in.
        @param indent: The number of spaces to indent each line of the message by.
        @param prefix: A string prefix to apply to each line of the message.
        @param end: The string to append to the end of the message.

        Example
        -------
        >>> Console.print('Example message.')
        Example message.
        >>> Console.print('Example message with indent of 4.', indent=4)
            Example message with indent of 4.
        >>> Console.print('Example message with prefix and custom terminator.',
        ...     prefix='<--', end='-->')
        <--Example message with prefix and custom terminator.-->
        '''

        lines = sep.join(map(str, objects)).splitlines(True)
        prefixed_lines = [prefix + line for line in lines]
        start_colour = colour if sys.stdout.isatty() else ''
        end_colour = Colours.NC if sys.stdout.isatty() else ''
        output = start_colour + ''.join(prefixed_lines) + end_colour
        print(textwrap.indent(output, ' ' * indent), end=end)

    @classmethod
    def info(cls, *msgs, **kwargs) -> None:
        '''Prints a info message to the console. Extends `print`.
        
        Example
        -------
        >>> Console.info('Example message.')
        Example message.
        >>> Console.info('Invalid kwargs.', invalid=True)
        Traceback (most recent call last):
        TypeError
        '''
        cls.print(*msgs, colour=Colours.BLUE, **kwargs)

    @classmethod
    def success(cls, *msgs, **kwargs) -> None:
        '''Prints a success message to the console. Extends `print`.
        
        Example
        -------
        >>> Console.success('Example message.')
        Example message.
        >>> Console.success('Invalid kwargs.', invalid=True)
        Traceback (most recent call last):
        TypeError
        '''
        cls.print(*msgs, colour=Colours.GREEN, **kwargs)

    @classmethod
    def warning(cls, *msgs, **kwargs) -> None:
        '''Prints a warning message to the console. Extends `print`.
        
        Example
        -------
        >>> Console.warning('Example message.')
        Example message.
        >>> Console.warning('Invalid kwargs.', invalid=True)
        Traceback (most recent call last):
        TypeError
        '''
        cls.print(*msgs, colour=Colours.YELLOW, **kwargs)

    @classmethod
    def error(cls, *msgs, **kwargs) -> None:
        '''Prints an error message to the console. Extends `print`.
        
        Example
        -------
        >>> Console.error('Example message.')
        Example message.
        >>> Console.error('Invalid kwargs.', invalid=True)
        Traceback (most recent call last):
        TypeError
        '''
        cls.print(*msgs, colour=Colours.RED, **kwargs)


class ChartProcessor:
    
    errors = OrderedDict([
        ('chart_does_not_exist', {}),
        ('missing_required_file', {}),
        ('missing_key', {}),
        ('non_existing_key', {})
    ])

    error_headers = {
        'chart_does_not_exist': 'Charts That Could Not Be Found',
        'missing_required_file': 'Missing Required Files',
        'missing_key': 'Missing Keys',
        'non_existing_key': 'Non-Existing Keys'
    }

    @classmethod
    def get_charts(cls, path: str, include: list[str]=[], exclude: list[str]=[]) -> dict[str, str]:
        '''Returns a dictionary of all chart name -> chart path for all charts
        in the charts directory, excluding those in the `exclude` list.

        @param path: The path to where Helm charts are located.
        @param include: A list of charts to include. Takes precedence `exclude`.
            Paths should be relative to the root of the repository.
        @param exclude: A list of charts to exclude. Paths should be relative
            to the root of the repository.

        Example
        -------
        >>> test_charts = ChartProcessor.get_charts('charts')
        '''

        charts = {}
        for p in Path(path).glob('**/Chart.yaml'):
            chart_obj = p.parent
            chart = str(chart_obj)

            include_chart = ((include and chart in include)
                or (not include and chart not in exclude))
            
            if include_chart:
                charts[chart_obj.name] = chart

        missing_charts = {Path(p).name: p for p in set(include) - set(charts.values())}
        cls.errors['chart_does_not_exist'] = missing_charts

        return charts

    @classmethod
    def process_chart(cls, chart_name: str, chart_path: str,
        readme_generator_cmd: str) -> bool:
        '''Processes a singe chart, returning `True` if the chart metadata is
        valid, otherwise `False`.

        @param chart_name: The name of the chart to process.
        @param chart_path: The path to the chart to process.
        @param readme_generator_cmd: The command to use when running the
            `readme-generator-for-helm` Node.js package.
        @param errors: A dictionary to populate with any errors detected.

        Example
        -------
        >>> readme_generator_cmd = '.github/actions/helm-metadata-updater/readme-generator-for-helm'
        >>> test_charts = ChartProcessor.get_charts('.github/actions/helm-metadata-updater/files/charts')
        >>> test_chart = next(iter(test_charts))
        >>> test_chart_path = (next(iter(test_charts.values())))
        >>> ChartProcessor.process_chart('test-fake-chart', 'charts/does-not-exist', readme_generator_cmd)
        Traceback (most recent call last):
        FileNotFoundError
        >>> ChartProcessor.process_chart(test_chart, test_chart_path, readme_generator_cmd)
        --ignore--
        True
        >>> readme_generator_cmd = 'npx @bitnami/readme-generator-for-helm'
        >>> ChartProcessor.process_chart(test_chart, test_chart_path, readme_generator_cmd)
        --ignore--
        True
        '''

        Console.info('\nProcessing chart:', chart_name)

        # Set paths to files required by the readme generator.
        chart_path_obj = Path(chart_path)
        readme_config_file = chart_path_obj / 'readme.config'
        readme_file = chart_path_obj / 'README.md'
        values_file = chart_path_obj / 'values.yaml'
        values_schema_file = chart_path_obj / 'values.schema.json'

        # Test that a README.md file exists. If not, create it.
        if not readme_file.is_file():
            with open(readme_file, 'w') as f:
                Console.warning('README.md file does not exist in chart, so will be created.')
                f.write(f'# {chart_name}\n\n## Parameters')

        # Run the metadata generator for this chart.
        cmd = shlex.split(readme_generator_cmd) + [
            '--config', readme_config_file,
            '--readme', readme_file,
            '--values', values_file,
            '--schema', values_schema_file]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True, text=True)
            Console.success('  ✓ Completed', chart_name)
            return True

        except subprocess.CalledProcessError as e:
            error_text = e.stdout or e.stderr or ''
            output = '\n'.join(
                line for line in error_text.splitlines()
                if line.lower().startswith('error: ')
            )
            return_code = e.returncode
            Console.error('  ✗ Failed to process', chart_name, f'(exit code: {return_code})')
            Console.print(output, indent=4, prefix='| ')

            # Parse errors from the output.
            error_patterns = [
                (r'.*missing metadata for key.*', 'missing_key', True),
                (r'.*metadata provided for non existing key.*', 'non_existing_key', True),
                (r'.*no such file or directory.*values\.yaml.*', 'missing_required_file', False),
                (r'.*no such file or directory.*readme\.config.*', 'missing_required_file', False)]
            has_metadata_errors = False
            for pattern, error_key, is_metadata in error_patterns:
                errors = re.findall(pattern, output, re.IGNORECASE | re.MULTILINE)
                if errors:
                    cls.errors[error_key][chart_name] = errors
                    has_metadata_errors = has_metadata_errors or is_metadata

            if has_metadata_errors:
                Console.warning('  ⚠', 'Metadata misconfiguration detected')

            return False

    @classmethod
    def print_summary(cls, results: list[tuple[str, str]]) -> None:
        '''Prints a summary of the metadata update process, including the number of
        charts processed successfully and unsuccessfully. Also lists the key errors
        detected for failed charts.

        Example
        -------
        >>> ChartProcessor.print_summary([])
        --ignore--
        All charts processed successfully!
        '''

        Console.info('\n\nProcessing Summary')
        Console.info('-' * 18)

        successful_charts = [chart_name for chart_name, result in results if result]
        failed_charts = [chart_name for chart_name, result in results if not result]

        # Output any charts that were successfully processed.
        if successful_charts:
            Console.success(f'\n{len(successful_charts)} chart(s) processed successfully -')
            for chart in successful_charts:
                Console.success('  ✓', end=' ')
                Console.print(chart)

        # Output any charts that failed to process.
        if failed_charts:
            Console.error(f'\n{len(failed_charts)} chart(s) failed to process -')
            for chart in failed_charts:
                Console.error('  ✗', end=' ')
                Console.print(chart)

            if cls.errors['missing_key'] or cls.errors['non_existing_key']:
                warning_msg = ('Metadata misconfiguration detected.\n',
                '-- Add @key annotations to all configuration values in values.yaml.\n',
                '-- Ensure @section and @descStart/@descEnd are properly formatted.\n',
                '-- Check that readme.config includes all required sections.\n',
                '-- Verify values.yaml syntax is valid YAML.')
                Console.warning('\n⚠', *warning_msg)
        else:
            Console.success('\nAll charts processed successfully!')
        
        # List chart errors by type.
        for error_type, charts in ((k, v) for k, v in cls.errors.items() if v):
            Console.error(f'\n{cls.error_headers[error_type]}')
            for chart, errors in sorted(charts.items()):
                Console.error('  ●', end=' ')
                Console.info(chart, ':', sep='', end=' ')
                if error_type == 'chart_does_not_exist':
                    Console.print(errors)
                else:
                    errors = [cls._extract_error_message(error) for error in errors]
                    Console.print(', '.join(errors))

    @staticmethod
    def _extract_error_message(error: str) -> str:
        '''Extract the clean error message from a full error string.

        First takes the substring after the last `/` character, then takes the
        substring after the last `:` character, stripping whitespace ans quotes.
        
        @param error: The full error string (e.g. '/file/path: ERROR: message').

        @return str: The clean error message.
        '''
        after_path = error[error.rfind('/') + 1:].strip(" '")
        return after_path[after_path.rfind(':') + 1:].strip()


class TestModule:
    '''Run doctest for this module.'''

    ELLIPSIS_MARKER = '--ignore--'
    DEFAULT_FLAGS = doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS

    @classmethod
    def run(cls, module: str=__name__, option_flags:int=None) -> int:
        '''Execute all module doctest examples and return the exit code.
        
        @param module: The name of the module to test. Defaults to `__name__`.
        @param option_flags: The doctest option flags to use. Defaults to the
            class `DEFAULT_FLAGS`.
        '''

        doctest.ELLIPSIS_MARKER = cls.ELLIPSIS_MARKER
        option_flags = option_flags if option_flags is not None else cls.DEFAULT_FLAGS
        result = doctest.testmod(name=module, optionflags=option_flags)

        if result.failed:
            print(f'[ERROR] {result.attempted} doctest(s) run, {result.failed} failed.')
            return 1

        print(f'[SUCCESS] {result.attempted} doctest(s) run, all passed.')
        return 0


# Preserve the old helper name for compatibility.
test_module = TestModule.run


if __name__ == '__main__':
    
    # Test this script if `-t` in sys.argv or '--test' in sys.argv.
    if '-t' in sys.argv or '--test' in sys.argv:
        sys.exit(TestModule.run())

    # Parse command line arguments.
    args = ArgsFactory.parse()

    # Test to see if the script is being run in CI mode, which will allow the
    # readme generator command to be set accordingly.
    if args.ci:
        readme_generator_cmd = 'npx @bitnami/readme-generator-for-helm'
    else:
        script_path = Path(os.path.realpath(__file__)).parent
        readme_generator_cmd = f'{script_path}/readme-generator-for-helm'

    Console.info('\nStarting metadata update for all charts')
    Console.info('-' * 39)

    # Get charts, process them and print a summary of the results.
    charts = ChartProcessor.get_charts(args.path, args.include, args.exclude)
    results = [(chart_name, ChartProcessor.process_chart(chart_name, chart_path, readme_generator_cmd))
            for chart_name, chart_path in sorted(charts.items())]
    ChartProcessor.print_summary(results)

    sys.exit(0 if all([result for _, result in results]) else 1)
