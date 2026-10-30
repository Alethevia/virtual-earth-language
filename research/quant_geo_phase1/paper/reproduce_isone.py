#!/usr/bin/env python3
"""Replay the published ISO-NE model search in a fresh temporary directory."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent


def main():
    manifest = json.loads((HERE/'reproduction_inputs.json').read_text())
    with tempfile.TemporaryDirectory(prefix='isone-replay-') as temporary:
        destination = Path(temporary)/'research'
        for relative, digest in manifest['sha256'].items():
            source = SOURCE/relative
            payload = source.read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ValueError('Published input changed: '+relative)
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        # The modelling command only needs the committed daily-input file.
        assert not list(destination.glob('**/raw'))
        assert not list(destination.glob('**/prepared'))
        guard = Path(temporary)/'guard'; guard.mkdir()
        (guard/'sitecustomize.py').write_text(
            'import socket\n'
            'def denied(*args, **kwargs):\n'
            '    raise RuntimeError("Network disabled for reproduction")\n'
            'socket.socket.connect = denied\n'
            'socket.socket.connect_ex = denied\n'
            'socket.create_connection = denied\n')
        environment = os.environ.copy()
        environment['PYTHONPATH'] = str(guard)+os.pathsep+str(destination)
        expected = pd.read_csv(destination/'isone_v1/qa/test_predictions.csv', index_col='date')
        selection = json.loads((destination/'isone_v1/qa/model_selection.json').read_text())
        logs = []
        for arguments in [('isone_replication.py', 'analyse'), ('verify_isone.py',)]:
            run = subprocess.run([sys.executable, *arguments], cwd=destination,
                                 env=environment, text=True, capture_output=True)
            logs.append('$ python '+' '.join(arguments)+'\n'+run.stdout+run.stderr)
            if run.returncode:
                raise RuntimeError(logs[-1])
        actual = pd.read_csv(destination/'isone_v1/qa/test_predictions.csv', index_col='date')
        if not actual.index.equals(expected.index) or not actual.columns.equals(expected.columns):
            raise ValueError('Prediction date or model columns changed')
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7)
        repeated = json.loads((destination/'isone_v1/qa/model_selection.json').read_text())
        assert set(repeated) == set(selection)
        for key in selection:
            assert repeated[key]['parameters'] == selection[key]['parameters']
            assert repeated[key]['features'] == selection[key]['features']
            np.testing.assert_allclose(repeated[key]['validation_MAE'], selection[key]['validation_MAE'], rtol=0, atol=1e-7)
        report = dict(status='REPRODUCED_FROM_COMMITTED_DAILY_INPUT',
            source_commit=manifest['source_commit'], pinned_files=len(manifest['sha256']),
            raw_archives_used=False, python_socket_connections_blocked=True,
            experimental_model_fits_previously_reported=65, additional_reproduction_fits=65,
            pipelines_reproduced=13, held_out_dates=len(actual), model_predictions_compared=len(actual)*13,
            prediction_max_abs_difference_mw=float(np.max(np.abs(actual.to_numpy()-expected.to_numpy()))),
            validation_selected_parameters_match=True,
            prediction_csv_byte_identical=(destination/'isone_v1/qa/test_predictions.csv').read_bytes()==(SOURCE/'isone_v1/qa/test_predictions.csv').read_bytes(),
            python=sys.version.split()[0],
            limitation='Same runtime replay from prepared inputs; not third-party verification, raw archive reconstruction, or a new statistical experiment.')
        (HERE/'reproduction_result.json').write_text(json.dumps(report, indent=2)+'\n')
        (HERE/'reproduction_log.txt').write_text('\n'.join(logs))
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
