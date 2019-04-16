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
        argv.extend(['-i', '--pg'])
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--integration', action='store_true', help='run integration tests')
    parser.add_argument('-u', '--unit', action='store_true', help='run unit tests')
    parser.add_argument('-f', '--flake8', action='store_true', help='run flake8')
    parser.add_argument('-v', '--python-version',
                        default='36', choices=['27', '36'],
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
        help='Drop into ipdb on failures'
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
        help='Specify the tests, tacked on to the end'
    )
    parser.add_argument(
        'extra',
        nargs='*'
    )

    parsed = parser.parse_args(argv)
    if parsed.types:
        parsed.types = type_convert(parsed.types)
    else:
        parsed.types = {'postgres', 'redshift', 'bigquery', 'snowflake'}

    return parsed


def _run_args(args):
    print('args={}'.format(args))
    result = subprocess.run(args)
    result.check_returncode()


def _docker_tests_args(parsed):
    tox_env = 'explicit-py{}'.format(parsed.python_version)
    args = ['docker-compose', 'run', '--rm']
    if parsed.single_threaded:
        args.extend(('-e', 'DBT_TEST_SINGLE_THREADED=y'))
    if parsed.docker_args:
        args.extend(parsed.docker_args)
    args.extend(['test', 'tox', '-e', tox_env])
    if parsed.tox_args:
        args.extend(parsed.tox_args)
    args.extend(['--', '-s'])
    if parsed.pdb:
        args.extend(['--pdb', '--pdbcls=IPython.terminal.debugger:Pdb'])
    if parsed.stop:
        args.append('-x')
    if parsed.coverage:
        args.extend(('--cov', 'dbt', '--cov-branch', '--cov-report', 'term'))
    if parsed.pylint_args:
        args.extend(parsed.pylint_args)
    return args


def _add_extras(args, parsed, default):
    if parsed.test_args or parsed.extra:
        if parsed.test_args:
            args.extend(parsed.test_args)
        if parsed.extra:
            args.extend(parsed.extra)
    else:
        args.extend(default)


def run_integration(parsed):
    args = _docker_tests_args(parsed)
    if parsed.types:
        args.append('-m')
        args.append(' or '.join('profile_{}'.format(t) for t in parsed.types))
    _add_extras(args, parsed, ['test/integration'])
    _run_args(args)


def run_unit(parsed):
    args = _docker_tests_args(parsed)
    _add_extras(args, parsed, ['test/unit'])
    _run_args(args)


def run_flake8(parsed):
    args = ['flake8', '--select', 'E,W,F', '--ignore', 'W504']
    args.extend(parsed.extra)
    if os.path.exists('dbt/main.py'):
        args.append('dbt')
    elif os.path.exists('core/dbt/main.py'):
        args.append('core/dbt')
        for adapter in ('postgres', 'redshift', 'bigquery', 'snowflake'):
            args.append('plugins/{}/dbt'.format(adapter))
    else:
        print('No main.py found!')
        raise RuntimeError('No main.py')
    _run_args(args)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parsed = parse_args(argv)
    print('args={}'.format(parsed))
    if parsed.remove_logs:
        path = 'logs/dbt.log'
        if os.path.exists(path):
            os.remove(path)
    cmds = []
    try:
        if parsed.flake8:
            run_flake8(parsed)
        if parsed.unit:
            run_unit(parsed)
        if parsed.integration:
            run_integration(parsed)
    except subprocess.CalledProcessError:
        print('failed!')
        sys.exit(1)
    print('success!')


if __name__ == '__main__':
    main()
