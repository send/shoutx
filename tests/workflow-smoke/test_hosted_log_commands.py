import unittest
from hosted_log_commands import BEGIN, END, expected, verify_log


class Verification(unittest.TestCase):
    def test_exact_and_timestamped(self):
        lines = [BEGIN, *expected(), END]
        for prefix in ["", "2026-10-17T00:00:00.000Z "]:
            verify_log("\n".join(prefix + line for line in lines).encode())

    def test_missing_extra_changed_or_disabled_is_not_success(self):
        lines = [BEGIN, *expected(), END]
        for mutation in [lines[1:], lines[:-1], lines + [END],
                         [BEGIN, END], [BEGIN, "::debug::not decoded", END],
                         [BEGIN, *expected(), "##[warning]extra", END],
                         [BEGIN, *[line for line in expected() if not line.startswith("##[debug]")], END],
                         [BEGIN, *expected()[:-1], END]]:
            with self.assertRaises(RuntimeError):
                verify_log("\n".join(mutation).encode())


if __name__ == "__main__":
    unittest.main()
