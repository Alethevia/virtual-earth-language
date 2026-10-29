"""Predeclared model-based design, followed by untouched seeded evaluation."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import numpy as np
import scipy
from dynamic import (Model, candidate_probes, admissible, trajectories, separation,
                     bayes_risk, state_filter, finite_predict, frozen_design_risk,
                     batch_llr, online_llr, wilson)

SPANS = [0.25, 0.5, 1., 2., 4., 8., 16.]
BITS = [2, 3, 4, 8]
METHODS = ['fixed_center', 'posterior']
NOISE_SCALES = [1., 0.75, 1.25]
SEED = 2026102907
N_PER_HYPOTHESIS = 20000
PROTOCOL_COMMIT = '3876398b3f8c3183d9c6a14f7764c808454f4fae'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def select_design(out):
    out = Path(out)
    if (out/'design.json').exists():
        raise FileExistsError('Existing design must not be overwritten')
    out.mkdir(parents=True, exist_ok=True)
    model = Model()
    all_v = candidate_probes(model)
    keep = admissible(all_v, model)
    original_ids = np.flatnonzero(keep)
    v = all_v[keep]
    means, states = trajectories(v, model)
    kappas = separation(means, model.sigma)
    info = kappas.sum(axis=1)
    full_risk = bayes_risk(info)
    # Exhaustive search ONLY within the recorded schedule/span family.
    design_scores = []
    for span in SPANS:
        scored = state_filter(kappas, 2, span, 'posterior')
        design_scores.append(scored['risk'])
        print('design span', span, 'best risk', float(scored['risk'].min()), flush=True)
    score_matrix = np.array(design_scores).T
    best_span_index = score_matrix.argmin(axis=1)
    best_risk = score_matrix[np.arange(len(v)), best_span_index]
    full_i = int(np.argmax(info))
    mem_i = int(np.argmin(best_risk))
    rand_i = int(np.random.default_rng(27001).integers(len(v)))
    chosen = [('no_probe', None), ('full_information_design', full_i),
              ('two_bit_design', mem_i), ('fixed_random_design', rand_i)]
    choices = {}
    for name, index in chosen:
        probe = np.zeros(model.horizon) if index is None else v[index]
        mu, x = trajectories(probe, model)
        q = separation(mu, model.sigma)
        options = []
        for bits in BITS:
            for method in METHODS:
                risks = [float(state_filter(q, bits, span, method)['risk'][0]) for span in SPANS]
                j = int(np.argmin(risks))
                options.append(dict(bits=bits, method=method, span=SPANS[j],
                                    modeled_risk=risks[j], all_span_risks=risks))
        choices[name] = dict(original_candidate_id=None if index is None else int(original_ids[index]),
                             probe=probe.tolist(), energy=float(probe@probe),
                             true_state_min=float(x.min()), true_state_max=float(x.max()),
                             squared_separation=float(q.sum()),
                             full_information_risk=float(bayes_risk(q.sum())),
                             classifiers=options)
    doc = dict(protocol_commit=PROTOCOL_COMMIT, model=vars(model),
               candidate_count=len(all_v), admissible_count=len(v), span_grid=SPANS,
               state_bit_budgets=BITS, evaluation_seed=SEED,
               n_per_hypothesis=N_PER_HYPOTHESIS, noise_scales=NOISE_SCALES,
               memory_scope='Data-dependent diagnostic register ONLY; clock, ROM, current sample and scratch precision excluded.',
               schedule_optimality='Exhaustive over the 7920 predeclared schedules after finite-model safety filtering; not global.',
               quantizer_optimality='Best declared span, not optimal among all finite-state machines.', choices=choices)
    dump(out/'design.json', doc)
    with (out/'candidate_design_scores.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['original_candidate_id', 'squared_separation', 'full_information_risk',
                         'posterior_2bit_best_risk', 'best_span']+[f'risk_span_{s:g}' for s in SPANS])
        for j in range(len(v)):
            writer.writerow([int(original_ids[j]), info[j], full_risk[j], best_risk[j],
                             SPANS[int(best_span_index[j])], *score_matrix[j]])
    print('DESIGN_FROZEN_SHA256', sha(out/'design.json'), flush=True)
    for name, choice in choices.items():
        print(name, 'input', choice['probe'], 'full risk', choice['full_information_risk'],
              '2bit posterior', next(o['modeled_risk'] for o in choice['classifiers']
                                     if o['bits']==2 and o['method']=='posterior'), flush=True)
    return doc


def row_statistics(prediction, truth):
    error = prediction != truth
    n = len(truth)
    count = int(error.sum())
    per_h = []
    for h in (0, 1):
        mask = truth == h
        per_h.append(dict(hypothesis=h, n=int(mask.sum()), errors=int(error[mask].sum()),
                          rate=float(error[mask].mean())))
    return dict(n=n, errors=count, rate=count/n, wilson95_descriptive=wilson(count, n),
                per_hypothesis=per_h), error


def evaluate(out):
    out = Path(out)
    if (out/'summary.json').exists():
        raise FileExistsError('Do not overwrite prior evaluation')
    design_hash = sha(out/'design.json')
    doc = json.loads((out/'design.json').read_text())
    model = Model(**doc['model'])
    n = doc['n_per_hypothesis']
    truth = np.repeat(np.arange(2, dtype=np.int8), n)
    eps = np.random.default_rng(doc['evaluation_seed']).normal(size=(2*n, model.horizon))
    saved = {'truth': truth}
    rows, identity = [], {}
    for name, choice in doc['choices'].items():
        probe = np.asarray(choice['probe'])
        means, x = trajectories(probe, model)
        q = separation(means, model.sigma)
        for scale in doc['noise_scales']:
            scenario = f'{name}__noise_{scale:g}'
            y = means[0, truth] + model.sigma*scale*eps
            full = batch_llr(y, means[0], model.sigma)
            online = online_llr(y, means[0], model.sigma)
            diff = float(np.max(np.abs(full-online)))
            disagreements = int(np.count_nonzero((full > 0) != (online > 0)))
            identity[scenario] = dict(max_abs_llr_difference=diff, decision_disagreements=disagreements)
            oracle_error = None
            for method, values in [('full_history_llr', full), ('recursive_llr', online)]:
                stats, err = row_statistics((values > 0).astype(np.int8), truth)
                if method == 'full_history_llr':
                    oracle_error = err
                saved[scenario+'__'+method] = err
                rows.append(dict(schedule=name, noise_scale=scale, method=method,
                                 state_bits=1152 if method=='full_history_llr' else 64,
                                 modeled_risk=float(bayes_risk(q.sum(), scale)),
                                 energy=choice['energy'], **stats))
            for option in choice['classifiers']:
                fitted = state_filter(q, option['bits'], option['span'], option['method'], retain=True)
                pred = finite_predict(y, means[0], model.sigma, fitted)
                stats, err = row_statistics(pred, truth)
                key = f"{option['method']}_{option['bits']}bit"
                saved[scenario+'__'+key] = err
                d = err.astype(float)-oracle_error.astype(float)
                se = float(d.std(ddof=1)/math.sqrt(len(d)))
                rows.append(dict(schedule=name, noise_scale=scale, method=option['method'],
                                 state_bits=option['bits'], span=option['span'],
                                 modeled_risk=float(frozen_design_risk(fitted, scale)[0]),
                                 energy=choice['energy'], paired_excess_error=float(d.mean()),
                                 paired_excess_normal95=[float(d.mean()-1.96*se), float(d.mean()+1.96*se)],
                                 **stats))
            print(scenario, 'full error', float(oracle_error.mean()), 'LLR difference', diff, flush=True)
    np.savez_compressed(out/'episode_error_vectors.npz', **saved)
    result = dict(design_sha256=design_hash, independent_noise_trajectories=2*n,
                  schedule_noise_conditions=len(doc['choices'])*len(doc['noise_scales']),
                  paired_trajectory_evaluations=2*n*len(doc['choices'])*len(doc['noise_scales']),
                  note='40,000 independent standard-noise trajectories reused across all schedules/scales; do not count paired copies as independent evidence.',
                  identity_checks=identity, results=rows)
    dump(out/'summary.json', result)
    scalar_keys = ['schedule','noise_scale','method','state_bits','span','modeled_risk','energy',
                   'n','errors','rate','paired_excess_error']
    with (out/'metrics.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=scalar_keys, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    assert sha(out/'design.json') == design_hash, 'Design changed during evaluation!'
    source = Path(__file__).resolve().parent
    manifest = dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                    platform=platform.platform(), protocol_commit=PROTOCOL_COMMIT,
                    source_sha256={p.name:sha(p) for p in source.iterdir()
                                   if p.is_file() and p.suffix in ('.py','.md','.txt')},
                    artifacts_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'manifest.json', manifest)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=Path('results/run_v1'))
    p.add_argument('--phase', choices=['design','evaluate','all'], default='all')
    args = p.parse_args()
    if args.phase in ('design','all'):
        select_design(args.out)
    if args.phase in ('evaluate','all'):
        evaluate(args.out)
