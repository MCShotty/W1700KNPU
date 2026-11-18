"""Exercise coherent-pool rounding and the scope of the cold sizing model."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "npu"))
from verify_coherent_budget import ceiling, first_fit, order_pages


class CoherentBudgetTests(unittest.TestCase):
    def test_rounds_each_request_independently(self):
        self.assertEqual([order_pages(n, 4096) for n in (1, 4096, 4097, 12288, 212992)],
                         [1, 1, 2, 4, 64])
        result = ceiling({"emi": [16, 16], "rx": [12288]}, 32768, 4096)
        self.assertEqual(result["reserved_bytes"], 24576)
        self.assertEqual(result["headroom_bytes"], 8192)

    def test_exhausts_capacity_without_combining_separate_objects(self):
        with self.assertRaisesRegex(ValueError, "exceeds coherent pool"):
            ceiling({"separate objects": [16, 16, 16]}, 8192, 4096)
        with self.assertRaisesRegex(ValueError, "invalid coherent allocation"):
            order_pages(0, 4096)
        with self.assertRaisesRegex(ValueError, "powers of two"):
            ceiling({"objects": [16]}, 12288, 4096)

    def test_empty_eight_page_pool_all_reachable_no_free_states(self):
        capacity = 8
        visited, remaining = set(), [0]
        while remaining:
            bitmap = remaining.pop()
            if bitmap in visited:
                continue
            visited.add(bitmap)
            for block in (1, 2, 4, 8):
                if block > capacity - bitmap.bit_count():
                    with self.assertRaisesRegex(ValueError, "pool exhausted"):
                        first_fit(bitmap, capacity, block)
                else:
                    start, next_bitmap = first_fit(bitmap, capacity, block)
                    self.assertEqual(start % block, 0)
                    self.assertEqual(next_bitmap.bit_count(), bitmap.bit_count() + block)
                    remaining.append(next_bitmap)
        self.assertGreater(len(visited), 8)

    def test_frees_allow_fragmentation_despite_enough_total_space(self):
        capacity, bitmap = 8, 0
        for _ in range(4):
            _, bitmap = first_fit(bitmap, capacity, 2)
        bitmap &= ~0b11001100
        self.assertEqual(capacity - bitmap.bit_count(), 4)
        with self.assertRaisesRegex(ValueError, "pool exhausted"):
            first_fit(bitmap, capacity, 4)


if __name__ == "__main__":
    unittest.main()
