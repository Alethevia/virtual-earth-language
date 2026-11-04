#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-results/reproduced}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python bank_study.py tests
python bank_study.py calibrate --out "$OUT"
for c in healthy healthy_shift bias bias_shift drift stuck startup_bias healthy_late_shift bias_late_shift healthy_outside_bank healthy_nonlinear bias_nonlinear; do
  python bank_study.py evaluate --out "$OUT" --condition "$c"
done
python bank_study.py summarize --out "$OUT"
python - "$OUT" <<'CHECK'
import json,sys
from pathlib import Path
expected=json.loads(Path('REFERENCE.json').read_text())
actual=json.loads((Path(sys.argv[1])/'summary.json').read_text())
assert actual['source_hashes']==expected['source_sha256']
assert actual['primary_screen_passed'] is False
for condition,counts in expected['counts'].items():
    for method,count in zip(expected['method_order'],counts):
        row=next(r for r in actual['results'] if r['condition']==condition and r['method']==method)
        assert row['count']==count,(condition,method,row['count'],count)
print('All 84 reference counts reproduced; the scientific screen remains FAILED.')
CHECK
