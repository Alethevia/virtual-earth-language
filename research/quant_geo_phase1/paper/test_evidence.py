"""Fault-injection checks of the publication gate, including optimized Python."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paper = self.root/'paper'
        self.paper.mkdir()
        for name in ('build_evidence.py', 'MANUSCRIPT.md', 'evidence.csv',
                     'evidence_table.md', 'evidence_provenance.json'):
            shutil.copyfile(HERE/name, self.paper/name)
        manifest = json.loads((HERE/'evidence_provenance.json').read_text())
        for name in manifest['source_sha256']:
            destination = self.root/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, destination)

    def check_gate(self, error=None):
        for flags in ([], ['-O']):
            with self.subTest(flags=flags):
                run = subprocess.run([sys.executable, *flags,
                    str(self.paper/'build_evidence.py'), '--check'],
                    capture_output=True, text=True)
                if error is None:
                    self.assertEqual(run.returncode, 0, run.stderr)
                else:
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn(error, run.stderr)

    def change_metrics(self, change):
        path = self.root/'bridge_2024/qa/metrics.csv'
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        target = next(r for r in rows if r['scope']=='GHCNh_2024_native'
                      and r['family']=='hgb' and r['representation']=='B2_distribution')
        change(rows, target)
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)

    def test_published_evidence_passes(self):
        self.check_gate()

    def test_missing_manuscript_fails(self):
        (self.paper/'MANUSCRIPT.md').unlink()
        self.check_gate('FileNotFoundError')

    def test_duplicate_marker_fails(self):
        p = self.paper/'MANUSCRIPT.md'
        p.write_text(p.read_text()+'\n<!-- EVIDENCE_TABLE_BEGIN -->')
        self.check_gate('marker pair')

    def test_duplicate_score_fails(self):
        self.change_metrics(lambda rows, r: rows.append(r.copy()))
        self.check_gate('Duplicate score')

    def test_nonfinite_score_fails(self):
        self.change_metrics(lambda rows, r: r.update(high_load_MAE='nan'))
        self.check_gate('Non-finite')

    def test_mismatched_counts_fail(self):
        self.change_metrics(lambda rows, r: r.update(high_load_n='1'))
        self.check_gate('sample counts')

    def test_changed_mean_fails(self):
        self.change_metrics(lambda rows, r: r.update(high_load_MAE='100'))
        self.check_gate('Paired mean')

    def test_stale_manuscript_table_fails(self):
        p = self.paper/'MANUSCRIPT.md'
        p.write_text(p.read_text().replace('| 525.39 |', '| 999.99 |'))
        self.check_gate('Manuscript table differs')


if __name__ == '__main__':
    unittest.main()
