#!/usr/bin/env python3
"""Server-side code runner. Called by Flask via subprocess."""
import sys, io, json, traceback, builtins

def main():
    payload = json.loads(sys.argv[1])
    code = payload['code']
    tests = payload.get('tests', [])

    # Mock input() so it never blocks
    builtins.input = lambda prompt='': ''

    namespace = {}
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    orig_out, orig_err = sys.stdout, sys.stderr
    sys.stdout = captured_out
    sys.stderr = captured_err

    exec_error = None
    try:
        exec(compile(code, '<user_code>', 'exec'), namespace)
    except SystemExit:
        pass
    except Exception:
        exec_error = traceback.format_exc()

    sys.stdout = orig_out
    sys.stderr = orig_err

    stdout = captured_out.getvalue()
    stderr = captured_err.getvalue() + (exec_error or '')

    ran_ok = exec_error is None

    test_results = []
    for test in tests:
        t = test['type']
        passed = False
        try:
            if t == 'runs_without_error':
                passed = ran_ok
            elif t == 'stdout_contains':
                passed = str(test.get('value', '')) in stdout
            elif t == 'stdout_equals':
                passed = stdout.strip() == str(test.get('value', '')).strip()
            elif t == 'stdout_lines_gte':
                passed = len([l for l in stdout.splitlines() if l.strip()]) >= int(test.get('value', 0))
            elif t == 'variable_exists':
                name = test.get('variable_name') or test.get('variable', '')
                passed = name in namespace
            elif t == 'variable_equals':
                name = test.get('variable_name') or test.get('variable', '')
                passed = name in namespace and str(namespace[name]) == str(test.get('value', ''))
            elif t == 'function_exists':
                fname = test.get('function_name', '')
                passed = fname in namespace and callable(namespace[fname])
            elif t == 'function_returns':
                fname = test.get('function_name', '')
                args = test.get('args', [])
                expected = test.get('value')
                result = namespace[fname](*args)
                passed = result == expected or str(result) == str(expected)
        except Exception:
            passed = False
        test_results.append({'type': t, 'passed': passed, 'message': test.get('message', '')})

    sys.stdout.write(json.dumps({'stdout': stdout, 'stderr': stderr, 'tests': test_results}))

main()
