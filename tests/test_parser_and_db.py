from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from opendtu_stats.db import init_db, insert_snapshot
from opendtu_stats.parser import parse_status_payload


def sample_payload() -> dict:
    return {
        "total": {
            "Power": {"v": "49.3"},
            "YieldDay": {"v": "6894"},
            "YieldTotal": {"v": "4430.404"},
            "Power DC": {"v": "51.6"},
        },
        "inverters": [
            {
                "serial": "116190744364",
                "name": "HS 1500",
                "reachable": 1,
                "producing": 1,
                "INV": {
                    "0": {
                        "Power DC": {"v": "51.6"},
                        "YieldDay": {"v": "6894"},
                        "YieldTotal": {"v": "2990.414"},
                        "Temperature": {"v": "20.6"},
                        "Efficiency": {"v": "95.43"},
                    }
                },
                "AC": {
                    "0": {
                        "Power": {"v": "49.3"},
                        "Voltage": {"v": "230.1"},
                        "Current": {"v": "0.21"},
                        "Frequency": {"v": "50.0"},
                        "PowerFactor": {"v": "0.99"},
                        "ReactivePower": {"v": "5.0"},
                    }
                },
                "DC": {
                    "0": {
                        "Power": {"v": "20.0"},
                        "Voltage": {"v": "40.0"},
                        "Current": {"v": "0.50"},
                        "YieldDay": {"v": "3000.0"},
                        "YieldTotal": {"v": "1200.0"},
                    },
                    "1": {
                        "Power": {"v": "31.6"},
                        "Voltage": {"v": "41.0"},
                        "Current": {"v": "0.77"},
                        "YieldDay": {"v": "3894.0"},
                        "YieldTotal": {"v": "1790.414"},
                    },
                },
            },
            {
                "serial": "1164a00ed8e8",
                "name": "HS2000",
                "reachable": 0,
                "producing": 0,
                "INV": {
                    "0": {
                        "Power DC": {"v": "0"},
                        "YieldDay": {"v": "0"},
                        "YieldTotal": {"v": "1431.696"},
                        "Temperature": {"v": "18.0"},
                        "Efficiency": {"v": "0"},
                    }
                },
                "AC": {"0": {"Power": {"v": "0"}}},
                "DC": {
                    "0": {
                        "Power": {"v": "0"},
                        "YieldDay": {"v": "0"},
                        "YieldTotal": {"v": "700.0"},
                    }
                },
            },
        ],
    }


class ParserAndDbTests(unittest.TestCase):
    def test_parse_status_payload_maps_expected_fields(self) -> None:
        snap = parse_status_payload(sample_payload(), dtu_host="http://192.168.178.73")

        self.assertEqual(snap.dtu_host, "http://192.168.178.73")
        self.assertEqual(len(snap.inverters), 2)
        self.assertAlmostEqual(snap.total_power_w or 0.0, 49.3, places=2)
        self.assertAlmostEqual(snap.dc_power_w or 0.0, 51.6, places=2)
        self.assertAlmostEqual(snap.total_yield_day_wh or 0.0, 6894.0, places=1)
        self.assertAlmostEqual(snap.total_yield_total_kwh or 0.0, 4430.404, places=3)

        first = snap.inverters[0]
        self.assertEqual(first.serial, "116190744364")
        self.assertEqual(len(first.dc_strings), 2)
        self.assertEqual(len(first.ac_phases), 1)
        self.assertTrue(first.reachable)
        self.assertTrue(first.producing)

    def test_db_insert_roundtrip_writes_all_tables(self) -> None:
        snap = parse_status_payload(sample_payload(), dtu_host="http://OpenDTU-FAE538")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "stats.db"
            init_db(db_path)
            run_id = insert_snapshot(db_path, snap)
            self.assertGreater(run_id, 0)

            conn = sqlite3.connect(db_path)
            try:
                runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                inv_count = conn.execute("SELECT COUNT(*) FROM inverter_stats").fetchone()[0]
                dc_count = conn.execute("SELECT COUNT(*) FROM inverter_dc_strings").fetchone()[0]
                ac_count = conn.execute("SELECT COUNT(*) FROM inverter_ac_phases").fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(runs_count, 1)
            self.assertEqual(inv_count, 2)
            self.assertEqual(dc_count, 3)
            self.assertEqual(ac_count, 2)


if __name__ == "__main__":
    unittest.main()
