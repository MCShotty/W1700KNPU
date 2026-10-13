#!/usr/bin/env python3
"""Cold envelope/lease and Linux codec/executor C with explicit dependency models."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent

ROOT, SOURCE, loader = parent.ROOT, parent.SOURCE, parent.loader
HARNESS = ROOT / 'tests/npu/cold-wire-harness.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    header = ROOT / '.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h'
    dest = ROOT / '.local/npu-cold-wire-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in
              (source, header, HARNESS, Path(__file__), Path(parent.__file__), Path(loader.__file__),
               Path(loader.extract.__file__))}
    inputs |= {str(p.relative_to(ROOT)): loader.sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def run(name, replacements=None, expected=0):
        directory = dest / name
        command = parent.prepare(directory, source.read_text(), header.read_text())
        command = [HARNESS if item == parent.HARNESS else item for item in command]
        for original, changed in (replacements or {}).items():
            path = directory / original.name
            path.write_text(changed)
            command = [path if item == original else item for item in command]
        binary = directory / 'test'
        loader.run(command + flags + ['-o', binary], directory / 'build.log')
        done = loader.run([binary], directory / 'run.log', env=env, accepted=expected)
        return done, binary

    done, binary = run('nominal')
    matrix = json.loads(done.stdout)
    print(json.dumps(dict(stage='host', **matrix)), flush=True)
    server, client = SOURCE / 'cold-setup.c', SOURCE / 'cold-client.c'
    executor = SOURCE / 'linux-control.c'
    original, codec, linux = server.read_text(), client.read_text(), executor.read_text()
    mutations = {
        'skip-RX-late-handle': {server: loader.once(original,
            's->rx_event != s->prior_rx_event ||', '(0 && s->rx_event != s->prior_rx_event) ||')},
        'skip-RX-late-progress': {server: loader.once(original,
            's->rx_event_steps != s->prior_rx_event_steps ||', '(0 && s->rx_event_steps != s->prior_rx_event_steps) ||')},
        'skip-RX-pending-handle': {server: loader.once(original,
            's->pending_rx_event != s->command.value : s->pending_rx_event != s->rx_event)',
            '0 : s->pending_rx_event != s->rx_event)')},
        'skip-RX-TX-overlap': {server: loader.once(original,
            '(!s->rx_event || npu_cold_rx_event_dma_valid(plan, step + 1, s->rx_event));', '(1);')},
        'skip-host-RX-TX-order': {executor: loader.once(linux,
            'control->txbuf_steps != NPU_COLD_TXBUF_STEPS ||', '(0 && control->txbuf_steps != NPU_COLD_TXBUF_STEPS) ||')},
        'skip-held-workers': {server: loader.once(original, 'load(&b->parked[i]) != 1 || load(&b->ready[i])', 'load(&b->ready[i])')},
        'skip-deferred-irq': {server: loader.once(original, 'if (a->deferred[i])', 'if (0 && a->deferred[i])')},
        'allow-replay': {server: loader.once(original, 'p.sequence <= session->last_sequence', 'p.sequence == 0')},
        'ignore-late-identity': {server: loader.once(original, 'session->boot_lo != s->boot_lo || session->boot_hi != s->boot_hi ||', '')},
        'release-failed-lease': {server: loader.once(original, 's->failed = 1;', 's->inflight = a->active = 0;\n    s->failed = 1;')},
        'ignore-callback-result': {server: loader.once(original, '!reply || result != 1 || reply->header', '!reply || (result != 1 && result == 99) || reply->header')},
        'skip-reply-ticket': {client: loader.once(codec, 'read_word(packet, 6) != ticket ||', '')},
        'skip-reply-reserved': {client: loader.once(codec, 'if (read_word(packet, i))', 'if (0 && read_word(packet, i))')},
        'skip-bar-overlap': {server: loader.once(original, 'if (r->bytes && base < r->base + r->bytes && r->base < base + bytes)', 'if (0 && r->bytes && base < r->base + r->bytes && r->base < base + bytes)')},
        'skip-page-offset': {server: loader.once(original, 'p->value == s->endpoint_base + NPU_COLD_PAGE_REG0 + 0x10u * i', 'p->value != 0')},
        'skip-late-bar': {server: loader.once(original, 's->endpoint_base != s->prior_base ||', '')},
        'skip-full-prefix': {server: loader.once(original, 'if (bit == NPU_COLD_ADDR8 && s->counts[i] != limits[i])', 'if (0 && bit == NPU_COLD_ADDR8 && s->counts[i] != limits[i])')},
        'skip-late-counts': {server: loader.once(original, 'if (s->counts[i] != s->prior_counts[i])', 'if (0 && s->counts[i] != s->prior_counts[i])')},
        'skip-tx2-offset': {server: loader.once(original, '(p->value == s->endpoint_base + NPU_COLD_TX_REG2 ||\n             p->value == s->endpoint_base + NPU_COLD_TX_REG2 + NPU_COLD_TX_HIF2)', '(p->value != 0)')},
        'skip-tx2-window': {server: loader.once(original, 'p->value - s->endpoint_base <= s->endpoint_bytes - 12', '(1)')},
        'relax-token-limit': {server: loader.once(original, 'p->api == 33 && p->value == 8192', 'p->api == 33 && p->value <= 8193')},
        'skip-getter-order': {server: loader.once(original, '(s->completed != NPU_COLD_COMPLETED_MASK || descriptor != s->descriptor_gets)', '(s->completed != NPU_COLD_COMPLETED_MASK)')},
        'skip-late-getter-count': {server: loader.once(original, 's->descriptor_gets != s->prior_descriptor_gets ||', '')},
        'skip-late-getter-arena': {server: loader.once(original, 's->descriptor_arena != s->prior_descriptor_arena ||', '')},
        'skip-server-getter-pointer': {server: loader.once(original, 's->completed != NPU_COLD_COMPLETED_MASK || !arena)', 's->completed != NPU_COLD_COMPLETED_MASK)')},
        'skip-codec-getter-pointer': {client: loader.once(codec, '!npu_cold_descriptor_reply_arena(descriptor, result, 0) :', '(0 && !npu_cold_descriptor_reply_arena(descriptor, result, 0)) :')},
        'skip-host-getter-order': {executor: loader.once(linux, 'descriptor < NPU_COLD_DESCRIPTOR_STEPS && descriptor != control->descriptor_gets', '0 && descriptor < NPU_COLD_DESCRIPTOR_STEPS && descriptor != control->descriptor_gets')},
        'skip-host-exact-arena': {executor: loader.once(linux, 'npu_cold_descriptor_reply_arena(descriptor, output, control->descriptor_arena)', 'npu_cold_descriptor_reply_arena(descriptor, output, 0)')},
        'skip-pending-plan-pin': {server: loader.once(original, '!npu_cold_txbuf_plan_equal(&candidate, &s->pending_txbuf)', '(0 && !npu_cold_txbuf_plan_equal(&candidate, &s->pending_txbuf))')},
        'skip-host-enrollment-order': {executor: loader.once(linux, 'enrollment != control->txbuf_enrolled)', '(0 && enrollment != control->txbuf_enrolled))')},
        'skip-host-txbuf-order': {executor: loader.once(linux, 'txbuf != control->txbuf_steps ||', '(0 && txbuf != control->txbuf_steps) ||')},
        'skip-txbuf-handle': {server: loader.once(original, 'p.command.value != s->txbuf.host[txbuf]', '(0 && p.command.value != s->txbuf.host[txbuf])')},
        'skip-late-txbuf-steps': {server: loader.once(original, 's->txbuf_steps != s->prior_txbuf_steps ||', '(0 && s->txbuf_steps != s->prior_txbuf_steps) ||')},
        'skip-enrolled-get7-history': {server: loader.once(original,
            '(s->txbuf_enrolled == NPU_COLD_TXBUF_RECORDS &&\n         s->descriptor_gets == 8 && s->txbuf_steps < 3)',
            '(0 && s->txbuf_enrolled == NPU_COLD_TXBUF_RECORDS &&\n         s->descriptor_gets == 8 && s->txbuf_steps < 3)')},
    }
    rejected = []
    for name, replacements in mutations.items():
        done, mutant = run(name, replacements, -6)
        assert 'Assertion' in done.stderr and 'AddressSanitizer' not in done.stderr
        rejected.append(dict(name=name, binary_sha256=loader.sha(mutant), exit_code=done.returncode))
    assert all(loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result = dict(passed=True, matrix=matrix, mutants=rejected, inputs=inputs,
                  binary_sha256=loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual cold server/codec and Linux executor; kernel/provider/worker/callback effects are modeled.',
                          'Initial binding is exercised through actual V2 control C; fixture cold backing/parking is not physical proof.',
                          'Fourteen ordered mailbox/TX records, lost replies and pending-plan mutations join the existing cold prefix/getters.',
                          'Native API21 store correctness is outside this host fixture proof; INODE/TXDONE/final IRQ and physical/hot/client gates remain open.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected))))


if __name__ == '__main__':
    main()
