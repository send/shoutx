"""Offline corpus invariants and exact-block negative controls."""
import unittest

from mask_cases import blocks, cases, entries, escaped, redact


class MaskCases(unittest.TestCase):
    def test_finite_matrix_and_limits(self):
        matrix = cases()
        self.assertEqual(len(matrix), 16)
        self.assertEqual(sum(case.control for case in matrix.values()), 4)
        self.assertEqual(len(matrix["lines_cap"].registered), 1024)
        self.assertEqual(len(set(matrix["lines_cap"].registered)), 1024)
        self.assertEqual(len(matrix["lines_cap"].inputs[0].encode()), 1_048_576)
        self.assertEqual(len(matrix["nearcap"].inputs[0].encode()), 1_048_576)
        for case in matrix.values():
            self.assertTrue(case.values)
            actual = tuple(v for raw in case.inputs
                           for v in (entries(raw) if case.each_line else (raw,)))
            self.assertEqual(actual, case.registered)
            # No live command prefix can be emitted by the synthetic corpus.
            self.assertFalse(any("##vso[" in value for value in case.values))

    def test_literal_projection_and_noncolliding_markers(self):
        for case in cases().values():
            for _, tag, _ in blocks(case, False):
                for marker in (tag + "_BEGIN", tag + "_END", "PREFIX", "SUFFIX",
                               "SX_UNRELATED_VISIBLE", "SX_EMISSION_COMPLETE"):
                    self.assertEqual(redact(marker, case.registered), marker)
        self.assertEqual(redact("abcdef", ("abc", "cde")), "***f")
        self.assertEqual(escaped("%0A;]\r\n"), "%AZP250A%3B%5D%0D%0A")

    def test_omission_control_is_discriminating(self):
        case = cases()["lines_omission"]
        self.assertEqual([redact(v, case.registered) for v in case.values],
                         ["***", "synthetic-omit-942b", "***"])
        original = cases()["original"]
        self.assertEqual(redact(original.values[1], original.registered), original.values[1])
        for name in ("ascii", "unicode", "whitespace", "lines_short", "lines_pem"):
            case = cases()[name]
            self.assertNotEqual(blocks(case, False), blocks(case, True))


if __name__ == "__main__":
    unittest.main()
