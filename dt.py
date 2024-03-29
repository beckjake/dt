#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

_SHORTHAND = {
    'p': 'postgres',
    'pg': 'postgres',
    'postgres': 'postgres',
    'pr': 'presto',
    'presto': 'presto',
    'r': 'redshift',
    'rs': 'redshift',
    'redshift': 'redshift',
    'b': 'bigquery',
    'bq': 'bigquery',
    'bigquery': 'bigquery',
    's': 'snowflake',
    'sf': 'snowflake',
    'snowflake': 'snowflake',
}


def type_convert(types: str):
    result = set()
    for t in types.split(','):
        try:
            result.add(_SHORTHAND[t])
        except KeyError:
            raise ValueError(
                'value "{}" not allowed, must be one of [{}]'
                .format(t, ','.join('"{}"'.format(k) for k in _SHORTHAND)))
    return result


def parse_args(argv):
    if not argv:
        argv.extend(['-it', 'pg'])
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--flake8',
        help='run flake8',
        dest='commands',
        action='append_const', const=Flake8Builder
    )
    parser.add_argument(
        '-u', '--unit',
        help='run unit tests',
        dest='commands',
        action='append_const', const=UnitBuilder
    )
    parser.add_argument(
        '-i', '--integration',
        help='run integration tests',
        dest='commands',
        action='append_const', const=IntegrationBuilder
    )

    parser.add_argument('-v', '--python-version',
                        default='36', choices=['27', '36', '37'],
                        help='what python version to run')
    parser.add_argument(
        '-t', '--types',
        default=None,
        help='The types of tests to run, if this is an integration run, as csv'
    )
    parser.add_argument(
        '-c', '--continue',
        action='store_false', dest='stop',
        help='If set, continue on failures'
    )
    parser.add_argument(
        '-l', '--remove-logs',
        action='store_true',
        help='remove dbt log files before running'
    )

    parser.add_argument(
        '-1', '--single-threaded',
        action='store_true',
        help='Specify if the DBT_TEST_SINGLE_THREADED environment variable should be set'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Make a coverage report and print it to the terminal'
    )
    parser.add_argument(
        '-p', '--pdb',
        action='store_true',
        help='Drop into ipdb on failures, implies "--no-multi"'
    )
    parser.add_argument(
        '-k',
        action='append',
        nargs='?',
        default=[],
        help='Pass-through to pytest, test selector expression'
    )
    parser.add_argument(
        '--no-multi',
        action='store_false',
        dest='multi',
        help='Turn off multiprocessing'
    )

    parser.add_argument(
        '--docker-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify docker-compose args')
    parser.add_argument(
        '--tox-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify tox args')
    parser.add_argument(
        '--pylint-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify pylint args')
    parser.add_argument(
        '-a', '--test-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify integration test parameters, tacked on to the end'
    )
    parser.add_argument(
        '--unit-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify unit test parameters, tacked on to the end'
    )
    parser.add_argument(
        '--flake8-args',
        action='append',
        nargs='?',
        default=[],
        help='Specify flake8 parameters, tacked on to the end'
    )
    parser.add_argument(
        'extra',
        nargs='*',
        default=[],
        help='Any extra args that will apply to all pytest runs'
    )

    parsed = parser.parse_args(argv)
    if parsed.types:
        parsed.types = type_convert(parsed.types)
    else:
        parsed.types = {'postgres', 'redshift', 'bigquery', 'snowflake'}
    return parsed


class ArgBuilder(object):

    def __init__(self, parsed):
        self.parsed = parsed
        self.args = []
        self.add_test_environment_args()

    def add_extras(self):
        raise NotImplementedError

    def add_container_args(self):
        pass

    def run(self):
        print('args={}'.format(self.args))
        result = subprocess.run(self.args)
        result.check_returncode()

    def add_test_environment_args(self):
        pass


class PytestBuilder(ArgBuilder):
    DEFAUlTS = None
    def add_tox_args(self):
        tox_env = 'explicit-py{}'.format(self.parsed.python_version)
        self.args.extend(['test', 'tox', '-e', tox_env])
        if self.parsed.tox_args:
            self.args.extend(self.parsed.tox_args)
        self.args.append('--')

    def add_pytest_args(self):
        assert self.DEFAUlTS is not None
        self.args.append('-s')
        if self.parsed.pdb:
            self.args.extend(['--pdb', '--pdbcls=IPython.terminal.debugger:Pdb'])
            self.parsed.multi = False
        if self.parsed.stop:
            self.args.append('-x')
        if self.parsed.coverage:
            self.args.extend(('--cov', 'dbt', '--cov-branch', '--cov-report', 'term'))
        for arg in self.parsed.k:
            self.args.extend(('-k', arg))
        if self.parsed.multi:
            self.args.extend(('-n', 'auto'))

        if not self.add_extra_pytest_args():
            self.args.extend(self.DEFAUlTS)

    def add_extra_pytest_args(self):
        raise NotImplementedError

    def add_test_environment_args(self):
        self.add_tox_args()
        self.add_pytest_args()


class DockerBuilder(PytestBuilder):
    def add_docker_args(self):
        self.args = ['docker-compose', 'run', '--rm']
        if self.parsed.single_threaded:
            self.args.extend(('-e', 'DBT_TEST_SINGLE_THREADED=y'))
        if self.parsed.docker_args:
            self.args.extend(self.parsed.docker_args)

    def add_test_environment_args(self):
        self.add_docker_args()
        super(DockerBuilder, self).add_test_environment_args()


class IntegrationBuilder(DockerBuilder):
    DEFAUlTS = ['test/integration']

    def add_extra_pytest_args(self):
        if self.parsed.types:
            self.args.append('-m')
            typestrs = ('profile_{}'.format(t) for t in self.parsed.types)
            self.args.append(' or '.join(typestrs))
        start = len(self.args)
        self.args.extend(self.parsed.test_args)
        self.args.extend(self.parsed.extra)
        return len(self.args) - start > 0


class UnitBuilder(DockerBuilder):
    DEFAUlTS = ['test/unit']

    def add_extra_pytest_args(self):
        start = len(self.args)
        self.args.extend(self.parsed.unit_args)
        self.args.extend(self.parsed.extra)
        return len(self.args) - start > 0


class Flake8Builder(ArgBuilder):
    def add_test_environment_args(self):
        self.args.extend(['flake8', '--select', 'E,W,F', '--ignore', 'W504'])
        start = len(self.args)
        self.args.extend(self.parsed.flake8_args)
        if len(self.args) == start:
            if os.path.exists('dbt/main.py'):
                self.args.append('dbt')
            elif os.path.exists('core/dbt/main.py'):
                self.args.append('core/dbt')
                for adapter in ('postgres', 'redshift', 'bigquery', 'snowflake'):
                    self.args.append('plugins/{}/dbt'.format(adapter))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parsed = parse_args(argv)
    print('args={}'.format(parsed))
    if parsed.remove_logs:
        path = 'logs/dbt.log'
        if os.path.exists(path):
            os.remove(path)

    try:
        for cls in parsed.commands:
            builder = cls(parsed)
            builder.run()
    except subprocess.CalledProcessError:
        print('failed!')
        sys.exit(1)
    print('success!')


if __name__ == '__main__':
    main()
