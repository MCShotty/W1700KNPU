#!/usr/bin/env python3
"""Run unchanged module inspections around compiler phases without a resident Python parent."""
import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import time

PHASES = ('provider', 'consumers-compile', 'consumers-link')
ENV_KEYS = ('STAGING_DIR', 'PATH', 'LANG', 'LC_ALL', 'TZ', 'KCONFIG_NOSILENTUPDATE')


class PhaseYield(Exception):
    pass


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def state_dir(directory):
    result = directory / 'phase-control'
    result.mkdir(exist_ok=True)
    return result


def phase_make(directory, command, name, environment):
    assert name in PHASES, ('unknown-compile-phase', name)
    state = state_dir(directory)
    spec = dict(command=command, environment={key: environment[key] for key in ENV_KEYS})
    path = state / (name + '-command.json')
    if path.exists():
        assert json.loads(path.read_bytes()) == spec, ('phase-command-drift', name)
    else:
        save(path, spec)
    done = state / (name + '-result.json')
    if done.exists():
        result = json.loads(done.read_bytes())
        assert result['returncode'] == 0 and result['command_sha256'] == digest(path)
        assert result['log_sha256'] == digest(directory / (name + '.log'))
        return
    pending = state / 'pending.json'
    request = dict(name=name, command_sha256=digest(path))
    if pending.exists():
        assert json.loads(pending.read_bytes()) == request, 'different-phase-pending'
    else:
        save(pending, request)
    if not (state / 'clock.json').exists():
        save(state / 'clock.json', dict(start_monotonic_ns=time.monotonic_ns(), limit_ns=1800_000_000_000))
    raise PhaseYield(name)


def pending_phase(directory):
    state = state_dir(directory)
    request = json.loads((state / 'pending.json').read_bytes())
    name = request['name']
    assert name in PHASES
    path = state / (name + '-command.json')
    assert request['command_sha256'] == digest(path), 'pending-command-drift'
    return state, name, path


def execute_phase(directory):
    state, name, path = pending_phase(directory)
    spec = json.loads(path.read_bytes())
    clock = json.loads((state / 'clock.json').read_bytes())
    remaining = (clock['start_monotonic_ns'] + clock['limit_ns'] - time.monotonic_ns()) // 1_000_000_000
    if remaining <= 0:
        raise SystemExit(124)
    environment = dict(os.environ)
    environment.pop('MAKEFLAGS', None)
    environment.pop('MFLAGS', None)
    environment.update(spec['environment'])
    log = directory / (name + '.log')
    with log.open('x') as stream:
        os.dup2(stream.fileno(), 1)
        os.dup2(stream.fileno(), 2)
        os.execvpe('/usr/bin/timeout', ['timeout', '--signal=TERM', '--kill-after=5s',
            str(remaining), *spec['command']], environment)


def complete_phase(directory, returncode):
    state, name, path = pending_phase(directory)
    assert returncode == 0, ('compiler-phase-failed', name, returncode)
    save(state / (name + '-result.json'), dict(returncode=returncode,
        command_sha256=digest(path), log_sha256=digest(directory / (name + '.log'))))
    (state / 'pending.json').unlink()


def symvers_once(path, text):
    if path.exists():
        assert path.read_text() == text, 'dependency-symbol-table-drift'
    else:
        with path.open('x') as stream:
            stream.write(text)


def transform_inner(source):
    tree = ast.parse(source)
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
    counts = dict(make=0, symvers=0)

    class Transform(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == 'make':
                assert [arg.arg for arg in node.args.args] == ['command', 'name']
                assert counts['make'] == 0
                counts['make'] += 1
                node.body = ast.parse('return _phase_make(directory, command, name, environment)').body
                return node
            return self.generic_visit(node)

        def visit_With(self, node):
            call = node.items[0].context_expr if len(node.items) == 1 else None
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and \
                    isinstance(call.func.value, ast.Name) and call.func.value.id == 'extra_path' and call.func.attr == 'open':
                assert len(call.args) == 1 and isinstance(call.args[0], ast.Constant) and call.args[0].value == 'x'
                assert len(node.body) == 1 and isinstance(node.body[0], ast.Expr)
                write = node.body[0].value
                assert isinstance(write, ast.Call) and isinstance(write.func, ast.Attribute)
                assert isinstance(write.func.value, ast.Name) and write.func.value.id == 'stream' and write.func.attr == 'write'
                assert len(write.args) == 1 and counts['symvers'] == 0
                counts['symvers'] += 1
                return ast.copy_location(ast.Expr(ast.Call(func=ast.Name(id='_symvers_once', ctx=ast.Load()),
                    args=[ast.Name(id='extra_path', ctx=ast.Load()), write.args[0]], keywords=[])), node)
            return self.generic_visit(node)

    tree = Transform().visit(tree)
    assert counts == dict(make=1, symvers=1), ('unexpected-inspector-shape', counts)
    return ast.fix_missing_locations(tree)


def inspect_phase(directory):
    import test_rro_reset_modules as original
    source = inspect.getsource(original.inner)
    tree = transform_inner(source)
    environment = dict(original.__dict__, _phase_make=phase_make, _symvers_once=symvers_once)
    exec(compile(tree, original.__file__, 'exec'), environment)
    environment['inner'](directory)
    state = state_dir(directory)
    assert all((state / (name + '-result.json')).exists() for name in PHASES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('inspect', 'execute', 'complete'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--returncode', type=int)
    args = parser.parse_args()
    assert args.directory.is_absolute() and args.directory.is_dir()
    if args.mode == 'inspect':
        try:
            inspect_phase(args.directory)
        except PhaseYield:
            raise SystemExit(75)
    elif args.mode == 'execute':
        execute_phase(args.directory)
    else:
        assert args.returncode is not None
        complete_phase(args.directory, args.returncode)


if __name__ == '__main__':
    main()
