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
            raise ValueError('value "{}" not allowed, must be one of [{}]'
                .format(t, ','.join('"{}"'.format(k) for k in _SHORTHAND)))
    return result


def parse_args(argv):
    if not argv:
        argv.extend(['-i', '--pg'])
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--integration', action='store_true', help='run integration tests')
    parser.add_argument('-u', '--unit', action='store_true', help='run unit tests')
    parser.add_argument('-p', '--pep8', action='store_true', help='run pep8')
    parser.add_argument('-v', '--python-version',
        default='36', choices=['27', '36'],
        help='what python version to run'
    )
    parser.add_argument(
        '-t','--types',
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
        '-a', '--test-args',
        nargs='+',
        help='Specify the tests, tacked on to the end'
    )
    parser.add_argument(
        '--postgres', '--pg',
        action='store_true',
        help='run postgres tests'
    )
    parser.add_argument(
        '--redshift', '--rs',
        action='store_true',
        help='run redshift tests'
    )
    parser.add_argument(
        '--bigquery', '--bq',
        action='store_true',
        help='run bigquery tests'
    )
    parser.add_argument(
        '--snowflake', '--sf',
        action='store_true',
        help='run snowflake tests'
    )
    parser.add_argument(
        '--presto', '--pr',
        action='store_true',
        help='run presto tests'
    )

    parser.add_argument(
        '--docker-args',
        nargs='+',
        help='Specify docker-compose args')
    parser.add_argument(
        '--tox-args',
        nargs='+',
        help='Specify tox args')
    parser.add_argument(
        'extra',
        nargs='*'
    )

    parsed = parser.parse_args(argv)
    if parsed.types:
        parsed.types = type_convert(parsed.types)
    else:
        parsed.types = set()
    if parsed.postgres:
        parsed.types.add('postgres')
    if parsed.redshift:
        parsed.types.add('redshift')
    if parsed.bigquery:
        parsed.types.add('bigquery')
    if parsed.snowflake:
        parsed.types.add('snowflake')
    if not parsed.types:
        parsed.types.update({'postgres', 'redshift', 'bigquery', 'snowflake'})

    return parsed


def _run_args(args):
    print('args={}'.format(args))
    subprocess.run(args)


def _docker_tests_args(parsed):
    tox_env = 'explicit-py{}'.format(parsed.python_version)
    args = ['docker-compose', 'run', '--rm']
    if parsed.docker_args:
        args.extend(parsed.docker_args)
    args.extend(['test', 'tox', '-e', tox_env])
    if parsed.tox_args:
        args.extend(parsed.tox_args)
    args.extend(['--', '-s'])
    if parsed.stop:
        args.append('-x')
    if parsed.extra:
        args.extend(parsed.extra)
    return args


def run_integration(parsed):
    args = _docker_tests_args(parsed)
    for testtype in parsed.types:
        args.extend(('-a', 'type={}'.format(testtype)))
    if parsed.test_args:
        args.extend('test/integration/{}'.format(a) for a in parsed.test_args)
    else:
        args.append('test/integration')
    _run_args(args)


def run_unit(parsed):
    args = _docker_tests_args(parsed)
    if parsed.test_args:
        args.extend(parsed.test_args)
    else:
        args.append('test/unit')
    _run_args(args)


def run_pep8(parsed):
    args = ['pep8']
    args.extend(parsed.extra)
    args.append('dbt')
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
    if parsed.integration:
        run_integration(parsed)
    if parsed.unit:
        run_unit(parsed)
    if parsed.pep8:
        run_pep8(parsed)


if __name__ == '__main__':
    main()
