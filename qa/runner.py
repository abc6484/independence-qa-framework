"""A small plain-Python test runner. No test framework.

A test is a normal function that uses `assert`. Its parameter names ask for adapters:
`rest`, `gql`, `catalog`. The runner builds them, calls the test, closes them, and
writes one JUnit XML file and one HTML page covering every API.
"""
import argparse
import html
import importlib
import inspect
import os
import sys
import time
import traceback
from pathlib import Path
from xml.sax.saxutils import quoteattr
from qa.adapters import make_adapter

ROOT = Path(__file__).resolve().parents[1]
TESTS = []   # (function, tags)
CONFIG = {'vampi_url': 'http://127.0.0.1:5102', 'dvga_url': 'http://127.0.0.1:5013',
          'catalog_address': '127.0.0.1:3550',
          'source_root': os.environ.get('QA_SOURCE_ROOT', '.lab')}
ADAPTERS = {'rest': ('rest', 'vampi_url'), 'gql': ('graphql', 'dvga_url'), 'catalog': ('grpc', 'catalog_address')}


def check(*tags, cases=None):
    """Register a test function with tags such as risk_high, security, contract, unit.

    With cases=[...], the function must take a parameter named `case`. It then runs once
    per case, and each case is reported (and can fail) on its own.
    """
    def register(function):
        if cases is None:
            TESTS.append((function, set(tags), None, function.__name__))
        else:
            for case in cases:
                TESTS.append((function, set(tags), (case,), f'{function.__name__}[{case!r}]'))
        return function
    return register


def expect_error(error_type, function, *args, match=None):
    """Assert that function(*args) raises error_type (optionally containing text `match`)."""
    try:
        function(*args)
    except error_type as caught:
        assert match is None or match in str(caught), f'wrong error message: {caught}'
        return
    raise AssertionError(f'{function.__name__}{args} did not raise {error_type.__name__}')


def run_one(function, case):
    opened = []
    try:
        kwargs = {'case': case[0]} if case else {}
        for name in inspect.signature(function).parameters:
            if name == 'case': continue
            protocol, key = ADAPTERS[name]
            kwargs[name] = make_adapter(protocol, CONFIG[key])
            opened.append(kwargs[name])
        function(**kwargs)
        return 'passed', ''
    except AssertionError:
        return 'failed', traceback.format_exc(limit=-2)
    except Exception:
        return 'error', traceback.format_exc(limit=-3)
    finally:
        for adapter in opened:
            adapter.close()


def write_reports(results, junit, page):
    failed = sum(r['status'] != 'passed' for r in results)
    total_time = sum(r['seconds'] for r in results)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             f'<testsuites><testsuite name="qa" tests="{len(results)}" failures="{failed}" time="{total_time:.3f}">']
    for r in results:
        lines.append(f'<testcase classname={quoteattr(r["module"])} name={quoteattr(r["name"])} time="{r["seconds"]:.3f}">')
        if r['status'] != 'passed':
            lines.append(f'<failure message={quoteattr(r["detail"].strip().splitlines()[-1])}>{html.escape(r["detail"])}</failure>')
        lines.append('</testcase>')
    lines.append('</testsuite></testsuites>')
    Path(junit).write_text('\n'.join(lines) + '\n')
    rows = ''.join(
        f'<tr class="{r["status"]}"><td>{html.escape(r["module"])}</td><td>{html.escape(r["name"])}</td>'
        f'<td>{r["status"]}</td><td>{r["seconds"]:.2f}s</td><td><pre>{html.escape(r["detail"])}</pre></td></tr>' for r in results)
    Path(page).write_text('<!doctype html><meta charset="utf-8"><title>QA report</title>'
        '<style>body{font-family:sans-serif}td{border:1px solid #ccc;padding:4px;vertical-align:top}'
        '.passed{background:#e6f7e6}.failed,.error{background:#fdeaea}pre{margin:0;white-space:pre-wrap}</style>'
        f'<h1>One report for all APIs</h1><p>{len(results)-failed} passed, {failed} failed or errored</p>'
        f'<table><tr><th>Module</th><th>Test</th><th>Result</th><th>Time</th><th>Detail</th></tr>{rows}</table>')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the cross-API checks')
    parser.add_argument('--vampi-url', default=CONFIG['vampi_url'])
    parser.add_argument('--dvga-url', default=CONFIG['dvga_url'])
    parser.add_argument('--catalog-address', default=CONFIG['catalog_address'])
    parser.add_argument('--source-root', default=CONFIG['source_root'])
    parser.add_argument('--tag', action='append', default=[], help='only tests with this tag (repeatable)')
    parser.add_argument('-k', dest='contains', default='', help='only tests whose name contains this text')
    parser.add_argument('--modules', nargs='*', default=['test_core', 'test_regression', 'test_security'])
    parser.add_argument('--junitxml', default='artifacts/all-apis.xml')
    parser.add_argument('--html', default='artifacts/all-apis.html')
    args = parser.parse_args(argv)
    CONFIG.update(vampi_url=args.vampi_url, dvga_url=args.dvga_url,
                  catalog_address=args.catalog_address, source_root=args.source_root)
    sys.path.insert(0, str(ROOT))
    for module in args.modules:
        importlib.import_module('tests.' + module)
    results = []
    log = []

    def say(text):
        print(text)
        log.append(text)
    for function, test_tags, case, name in TESTS:
        if args.tag and not set(args.tag) & test_tags: continue
        if args.contains not in name: continue
        start = time.monotonic()
        status, detail = run_one(function, case)
        results.append({'module': function.__module__, 'name': name, 'status': status,
                        'detail': detail, 'seconds': time.monotonic() - start})
        say(f'{status.upper():7} {name}')
        if status != 'passed': say('        ' + detail.strip().splitlines()[-1])
    Path(args.junitxml).parent.mkdir(exist_ok=True)
    write_reports(results, args.junitxml, args.html)
    bad = sum(r['status'] != 'passed' for r in results)
    if not results:
        say('No tests selected: refusing to report success')
        return 1
    say(f'\n{len(results)-bad} passed, {bad} failed')
    Path(args.junitxml).with_suffix('.txt').write_text('\n'.join(log) + '\n')
    return 1 if bad else 0
