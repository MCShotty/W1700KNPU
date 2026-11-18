"""Exercise control-flow refusal cases with small synthetic RV32 instructions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "npu"))
from verify_ppe_stop import Instruction, no_polling_loop


class StopFlowTests(unittest.TestCase):
    def check(self, *code, calls=()):
        return no_polling_loop({row.pc: row for row in code}, code[0].pc, set(calls))

    def test_backward_tail_merge_is_not_a_loop(self):
        result = self.check(
            Instruction(0x100, 2, "c.beqz", "a0,0x104"),
            Instruction(0x102, 2, "c.jr", "ra"),
            Instruction(0x104, 2, "c.j", "0x102"),
        )
        self.assertEqual(result["reachable_instructions"], 3)
        self.assertEqual(result["returns"], ["0x102"])

    def test_conditional_polling_back_edge_refused(self):
        with self.assertRaisesRegex(ValueError, "loop"):
            self.check(Instruction(0x100, 2, "c.bnez", "a0,0x100"),
                       Instruction(0x102, 2, "c.jr", "ra"))

    def test_only_known_direct_callee_is_admitted(self):
        code = (Instruction(0x100, 4, "jal", "ra,0x200"), Instruction(0x104, 2, "c.jr", "ra"))
        self.assertEqual(self.check(*code, calls=[0x200])["calls"], ["0x200"])
        with self.assertRaisesRegex(ValueError, "uninspected call"):
            self.check(*code)

    def test_indirect_control_and_uninspected_tail_refused(self):
        for op, args, diagnostic in (
            ("c.jalr", "a5", "unresolved instruction"),
            ("wfi", "", "unresolved instruction"),
            ("c.j", "0x200", "control flow escapes"),
        ):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, diagnostic):
                self.check(Instruction(0x100, 2, op, args), Instruction(0x102, 2, "c.jr", "ra"))


if __name__ == "__main__":
    unittest.main()
