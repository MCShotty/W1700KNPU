"""Receipt and CLI failure controls. Fixtures here never execute the firmware."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import raw_pair_retained as retained
import test_npu_raw_pair as raw


class RawPairRetainedTests(unittest.TestCase):
    def test_invalid_receipt_and_escaped_or_changed_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='raw-receipt-unit-', dir=retained.ROOT / '.local') as directory:
            path = Path(directory) / 'receipt.json'
            path.write_text(json.dumps(dict(passed=False, inputs={})))
            with self.assertRaisesRegex(AssertionError, 'receipt-not-passed'):
                retained.read_receipt(path)
            with self.assertRaisesRegex(AssertionError, 'receipt-input-path'):
                retained.verify_inputs({'../outside': '0' * 64})
            with self.assertRaisesRegex(AssertionError, 'receipt-input-drift'):
                retained.verify_inputs({'tests/npu/raw_pair_retained.py': '0' * 64})

    def test_cli_writes_result_and_uses_new_handler_summary_without_stale_names(self):
        result = dict(passed=True, full_nominal=True, retained_packet_claims=3072,
                      boot_controls=[{}] * 6, controls=[{}] * 8)
        with tempfile.TemporaryDirectory(prefix='raw-cli-unit-', dir=retained.ROOT / '.local') as directory:
            root = Path(directory)
            output = root / '.local/npu-raw-pair-20261010/unit-case'
            capture = io.StringIO()
            arguments = ['test_npu_raw_pair.py', '--pair', str(root / 'pair'), '--name', 'unit-case',
                         '--caller-receipt', str(root / 'caller.json')]
            with patch.object(raw, 'ROOT', root), patch.object(sys, 'argv', arguments), \
                    patch.object(retained, 'check', return_value=result) as check, contextlib.redirect_stdout(capture):
                raw.main()
            self.assertEqual(json.loads((output / 'result.json').read_bytes()), result)
            self.assertEqual(json.loads(capture.getvalue()), dict(passed=True, full_nominal=True,
                claims=3072, raw_pair=True, boot_controls=6, txdone_controls=8))
            self.assertEqual(check.call_args.args[:3], (root / 'pair', root / 'caller.json', output))

    def test_nominal_caller_contract_rejects_partial_or_synthetic_proof(self):
        for caller in (dict(passed=False, native={}), dict(passed=True, native=dict(passed=True,
            actual_c_linux_setup=False, actual_c_txrx_sender=True))):
            with self.assertRaises(AssertionError):
                retained.caller_contract(caller)

    def test_sender_binary_is_checked_against_its_independent_compiler_receipt(self):
        with tempfile.TemporaryDirectory(prefix='sender-receipt-unit-', dir=retained.ROOT / '.local') as directory:
            root = Path(directory)
            shared, binary, receipt = root / 'host-sender.so', root / 'host-test', root / 'result.json'
            shared.write_bytes(b'synthetic unit fixture, not executable')
            binary.write_bytes(b'synthetic sanitized matrix fixture')
            shared_name, binary_name = (str(path.relative_to(retained.ROOT)) for path in (shared, binary))
            receipt.write_text(json.dumps(dict(passed=True, completed_offload=True, shared=shared_name,
                shared_sha256=retained.captured.digest(shared), binary_sha256=retained.captured.digest(binary),
                inputs={binary_name: retained.captured.digest(binary)})))
            caller = dict(inputs={str(receipt.relative_to(retained.ROOT)): retained.captured.digest(receipt)})
            proof = retained.sender_provenance(caller)
            self.assertEqual(proof['inputs'][shared_name], retained.captured.digest(shared))
            shared.write_bytes(b'changed synthetic unit fixture')
            with self.assertRaisesRegex(AssertionError, 'actual-sender-binary-drift'):
                retained.sender_provenance(caller)


if __name__ == '__main__':
    unittest.main()
