"""Synthetic function inventory controls, not native stack acceptance."""
from collections import Counter
import unittest

from test_npu_raw_stack_usage import check_frames


class RawStackContractTests(unittest.TestCase):
    def test_C_frames_match_and_do_not_silently_claim_other_symbols(self):
        self.assertEqual(check_frames(Counter(context=2, dispatch=1),
            [{'function': 'context'}, {'function': 'context'}], False), {'dispatch': 1})

    def test_unknown_or_duplicate_extra_frame_is_rejected(self):
        for frames in ([{'function': 'unknown'}], [{'function': 'context'}] * 3):
            with self.assertRaises(AssertionError):
                check_frames(Counter(context=2), frames, False)

    def test_missing_all_C_frames_cannot_pass(self):
        with self.assertRaises(AssertionError):
            check_frames(Counter(context=1), [], False)

    def test_assembly_symbols_remain_explicitly_unmeasured(self):
        self.assertEqual(check_frames(Counter(assembly=1), [], True), {'assembly': 1})

    def test_assembly_only_component_cannot_be_reclassified_by_an_unexpected_C_record(self):
        with self.assertRaises(AssertionError):
            check_frames(Counter(assembly=1), [{'function': 'assembly'}], True)


if __name__ == '__main__': unittest.main()
