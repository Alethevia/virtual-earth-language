"""Offline checks that graphical summaries faithfully show locked trial metrics."""
import copy
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from plot_results import CHARTS, render_chart, validate_summary


class PlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(
            (Path(__file__).parent / "results" / "run_v1" / "summary.json").read_text()
        )

    def test_svg_valid_and_contains_all_counts(self):
        validate_summary(self.payload)
        for filename, (conditions, _, _, _) in CHARTS.items():
            chart = render_chart(self.payload, filename)
            self.assertEqual(ET.fromstring(chart).tag, "{http://www.w3.org/2000/svg}svg")
            for condition in conditions:
                for method in ("tracking", "no_load", "load_augmented"):
                    d = self.payload["results"][condition][method]
                    self.assertIn(f'{d["count"]}/{d["n"]} ({100*d["rate"]:.1f}%)', chart)
            self.assertIn("Synthetic model only", chart)

    def test_rejects_inconsistent_count(self):
        bad = copy.deepcopy(self.payload)
        bad["results"]["bias"]["tracking"]["count"] = -1
        with self.assertRaises(ValueError):
            validate_summary(bad)

    def test_rejects_wrong_metric_or_protocol(self):
        bad = copy.deepcopy(self.payload)
        bad["results"]["healthy"]["tracking"]["metric"] = "valid_detection_fraction"
        with self.assertRaises(ValueError):
            validate_summary(bad)
        bad = copy.deepcopy(self.payload)
        bad["protocol"] = "changed protocol"
        with self.assertRaises(ValueError):
            validate_summary(bad)


if __name__ == "__main__":
    unittest.main()
