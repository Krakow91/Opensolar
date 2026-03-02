from __future__ import annotations

import unittest

from opendtu_stats.ha_bridge import _slug, _to_number


class HaBridgeHelperTests(unittest.TestCase):
    def test_slug_normalizes_and_fallbacks(self) -> None:
        self.assertEqual(_slug("OpenSolar openDTU"), "opensolar_opendtu")
        self.assertEqual(_slug("%%%"), "opensolar")

    def test_to_number_handles_int_float_and_invalid(self) -> None:
        self.assertEqual(_to_number(12), 12)
        self.assertEqual(_to_number(12.34), 12.34)
        self.assertIsNone(_to_number("not-a-number"))
        self.assertIsNone(_to_number(None))


if __name__ == "__main__":
    unittest.main()
