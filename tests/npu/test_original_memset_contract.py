"""Model and harness contracts with synthetic metadata,not router firmware."""
import hashlib
import json
import tempfile
from pathlib import Path
import unittest

from test_original_memset_native import CODE, DATA, END, ROOT, Fixture, expected_effects, load_code


def initial(destination, length, value):
    state = [0]+[0xa0000000+index for index in range(1,32)]
    state[1], state[2] = END, 0x85001000
    state[10], state[11], state[12] = destination, value, length
    return state


class OriginalMemsetContracts(unittest.TestCase):
    def test_manifest_base_must_match_the_actual_mapping(self):
        with tempfile.TemporaryDirectory(prefix='memset-contract-',dir=ROOT / '.local') as directory:
            root = Path(directory)
            pair = root / 'pair'
            pair.mkdir()
            data = b'\x01\x00'
            (pair / 'CODE.bin').write_bytes(data)
            (pair / 'manifest.json').write_text(json.dumps(dict(synthetic_only=True,
                code=dict(base=CODE+4096,bytes=2,sha256=hashlib.sha256(data).hexdigest()))))
            original, export = root / 'original.bin', root / 'export.json'
            original.write_bytes(data)
            export.write_text(json.dumps(dict(passed=True,synthetic_only=True)))
            with self.assertRaisesRegex(AssertionError,'CODE-base-drift'):
                load_code(pair,original,export)

    def test_model_covers_exact_owned_bytes_for_every_alignment(self):
        for alignment in range(16):
            for length in range(66):
                destination = DATA+0x100+alignment
                _, writes = expected_effects(initial(destination,length,0x123456ff),destination,length,0x123456ff)
                visited = []
                for pc, address, width, value in writes:
                    self.assertIn(width,(1,4))
                    self.assertTrue(destination <= address < address+width <= destination+length)
                    if width == 4:
                        self.assertEqual(address%4,0)
                    visited.extend(range(address,address+width))
                    self.assertEqual(value.to_bytes(width,'little'),b'\xff'*width)
                self.assertEqual(sorted(visited),list(range(destination,destination+length)))

    def test_model_preserves_RA_SP_GP_TP_and_callee_saved_registers(self):
        protected = (0,1,2,3,4,8,9,*range(18,28))
        for alignment in range(16):
            for length in (0,1,15,16,17,31,32,65,1024):
                destination = DATA+0x100+alignment
                before = initial(destination,length,0x100)
                after, _ = expected_effects(before,destination,length,0x100)
                self.assertEqual([after[index] for index in protected],[before[index] for index in protected])
                self.assertEqual(after[10],destination)

    def test_low_byte_and_bulk_register_expansion_are_distinct(self):
        destination = DATA+0x100
        short, writes = expected_effects(initial(destination,1,0x100),destination,1,0x100)
        self.assertEqual(short[11],0x100)
        self.assertEqual(writes[0][3],0)
        bulk, writes = expected_effects(initial(destination,32,0x100),destination,32,0x100)
        self.assertEqual(bulk[11],0)
        self.assertTrue(all(width == 4 and value == 0 for pc,address,width,value in writes))

    def test_outside_finite_domain_is_rejected_before_engine_use(self):
        fixture = object.__new__(Fixture)
        for case in ((-1,0,0),(16,0,0),(0,-1,0),(0,1025,0),(0,0,-1),(0,0,1<<32)):
            with self.subTest(case=case), self.assertRaises(AssertionError):
                fixture.run(*case)


if __name__ == '__main__':
    unittest.main()
