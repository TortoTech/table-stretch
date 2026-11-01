#!/usr/bin/env python3
"""Audit frozen evaluation records and generate tables, ablations and profiles."""
import json
import math
import statistics
from collections import Counter
from datetime import datetime
from html import escape

from benchmark_ablation import DIRECTORY, PROTOCOL, SELECTION, load_protocol, read_records, summarize
from benchmark_native import ROOT
from benchmark_unified import sha, verify
from benchmark_table import render_svg
from report_native import NAMES, paper_name, fmt_kib

ORDER = ['Pareto DP', 'A*', 'LCG', 'MIP', 'CP']


def percentile(values):
    return sorted(values)[math.ceil(.95*len(values))-1]


def audit(stage, mode, protocol, selection):
    ids = protocol['evaluation_cases'] if stage=='ebooks' else protocol['minizinc_cases']
    settings = protocol['timing' if mode=='timing' else 'memory']
    cap = protocol['timing']['timeout_ms']
    all_records, environments, digests = {}, {}, {}
    for method in selection['selected'].values():
        path = DIRECTORY/f'{stage}-{method}-{mode}.jsonl'
        env, records = read_records(path)
        assert (env['stage'],env['mode'],env['algorithm']) == (stage,mode,method)
        assert env['protocol_sha256'] == sha(PROTOCOL) and env['selection_sha256'] == sha(SELECTION)
        assert env['source_sha256'] == selection['source_sha256']
        assert datetime.fromisoformat(env['utc']) >= datetime.fromisoformat(selection['utc'])
        assert env['profiles'] == protocol['profiles'][method]
        assert env['case_ids'] == ids and env['settings'] == settings and env['timeout_ms'] == cap
        assert env['manifest_sha256'] == sha(ROOT/env['manifest']) == protocol['inputs'][env['manifest']]
        inputs = json.loads((ROOT/env['manifest']).read_text())
        assert len(records) == len(ids)*len(env['profiles'])
        for profile, options in env['profiles'].items():
            cases = [r for r in records if r['profile']==profile]
            assert len(cases)==len(ids) and {r['case'] for r in cases}==set(ids)
            for record in cases:
                item = inputs[record['case']]
                assert record['algorithm']==method and record['options']==options
                assert record['input_sha256']==item['input_sha256']
                assert len(record['runs'])==settings['repeats']
                runs = record['runs'] + ([record['warmup']] if record['warmup'] else [])
                assert bool(record['warmup']) == (settings['warmups']==1)
                for run in runs:
                    assert run['status'] in ('optimal','timeout','resource_limit','error')
                    if run['status']=='optimal':
                        assert run['layout']['optimal'] and 0 <= run['wall_ns'] <= cap*1_000_000
                        verify(item['table'],run['layout'],item['reference_height'])
                    else: assert run['layout'] is None
                    if mode=='memory' and run['memory_available']:
                        assert run['heap_extra_peak_bytes']==run['heap_peak_bytes']-run['heap_baseline_bytes'] >= 0
                        assert run['heap_peak_bytes'] >= run['heap_end_bytes'] >= 0 and run['rss_peak_bytes']>0
            all_records[method,profile] = sorted(cases,key=lambda r:r['case'])
        environments[method] = env
        digests[str(path.relative_to(ROOT))] = sha(path)
    return all_records, environments, digests


def results(timing, memory, cap):
    output = {}
    for (method, profile), cases in timing.items():
        summary = summarize(cases,[r['case'] for r in cases],len(cases[0]['runs']),cap)
        summary['statuses'] = dict(Counter(run['status'] for c in cases for run in c['runs']))
        summary['root_certified_cases'] = sum(all(run['status']=='optimal'
            and run['layout']['stats']['generated']==0 and run['layout']['stats']['terminal_evaluations']==0
            and run['layout']['stats']['bound_pruned']>0 for run in c['runs']) for c in cases)
        summary['case_ms'] = {str(c['case']):statistics.median(r['wall_ns']/1e6 for r in c['runs'])
            if all(r['status']=='optimal' for r in c['runs']) else None for c in cases}
        full = timing[method,'full']
        ratios = [statistics.median(r['wall_ns'] for r in c['runs']) / statistics.median(r['wall_ns'] for r in f['runs'])
            for c,f in zip(cases,full) if all(r['status']=='optimal' for r in c['runs']+f['runs'])]
        summary['paired_cases'] = len(ratios)
        summary['paired_geomean_ratio_to_full'] = math.exp(statistics.mean(math.log(v) for v in ratios)) if ratios else None
        mem = memory[method,profile]
        measured = sum(all(r['memory_available'] for r in c['runs']) for c in mem)
        summary['memory_measured'] = measured
        summary['memory_completed'] = sum(all(r['status']=='optimal' for r in c['runs']) for c in mem)
        summary['memory_statuses'] = dict(Counter(r['status'] for c in mem for r in c['runs']))
        for key in ['heap_extra_peak_bytes','rss_peak_bytes']:
            summary[key+'_p95'] = percentile([statistics.median(r[key] for r in c['runs']) for c in mem]) if measured==len(mem) else None
        output.setdefault(method,{})[profile] = summary
    return output


def profile_points(methods):
    cases = list(next(iter(methods.values()))['case_ms'])
    ratios = {name:[] for name in methods}
    for case in cases:
        solved = [m['case_ms'][case] for m in methods.values() if m['case_ms'][case] is not None]
        best = min(solved) if solved else None
        for name, method in methods.items():
            value = method['case_ms'][case]
            ratios[name].append(value/best if value is not None else math.inf)
    return ratios, len(cases)


def performance_svg(methods, title):
    ratios, n = profile_points(methods)
    largest = max((v for values in ratios.values() for v in values if math.isfinite(v)), default=1)
    decades = max(2, math.ceil(math.log10(largest)))
    ceiling = 10**decades
    colors = ['#0969da','#bf8700','#1a7f37','#8250df','#6e7781']
    left, top, plot_w, plot_h = 58, 48, 600, 220
    def x(v): return left+math.log10(v)/decades*plot_w
    def y(v): return top+(1-v)*plot_h
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="720" height="350" viewBox="0 0 720 350" role="img">',
         f'<title>{escape(title)}</title>',
         f'<desc>Fraction of all cases solved within a multiple of the fastest successful full configuration. Failures are at infinity. Ratios are shown from 1 to {ceiling}, including every finite ratio.</desc>',
         '<style>text{font:12px sans-serif;fill:#1f2328}.bg{fill:#fff}.grid{stroke:#d1d9e0;stroke-width:1}@media(prefers-color-scheme:dark){text{fill:#f0f6fc}.bg{fill:#0d1117}.grid{stroke:#3d444d}}</style>',
         '<rect class="bg" width="720" height="350"/>',
         f'<text x="58" y="24" font-weight="700">{escape(title)}</text>']
    for tick in [0,.25,.5,.75,1]:
        s += [f'<path class="grid" d="M{left} {y(tick)} H{left+plot_w}"/>',f'<text x="48" y="{y(tick)+4}" text-anchor="end">{tick:.0%}</text>']
    for tick in ([1,2,5,10,20,50,100] if decades==2 else [10**p for p in range(decades+1)]):
        s += [f'<path class="grid" d="M{x(tick)} {top} V{top+plot_h}"/>',f'<text x="{x(tick)}" y="286" text-anchor="middle">{tick}×</text>']
    for (name, values), color in zip(ratios.items(),colors):
        observed = sorted(set(v for v in values if math.isfinite(v)))
        path = [f'M{x(1)} {y(sum(v<=1 for v in values)/n)}']
        for value in observed:
            path += [f'H{x(value)}',f'V{y(sum(v<=value for v in values)/n)}']
        path += [f'H{x(ceiling)}']
        s += [f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2.5"/>']
    s += ['<text x="358" y="307" text-anchor="middle">Time relative to the fastest solved implementation (log scale)</text>']
    for i,(name,color) in enumerate(zip(ratios,colors)):
        lx = 58+i*120
        s += [f'<path d="M{lx} 332 h18" stroke="{color}" stroke-width="3"/>',f'<text x="{lx+25}" y="336">{escape(name)}</text>']
    return '\n'.join(s+['</svg>',''])


def primary_table(stage, metrics, selection, cap):
    headers = ['Metric']+[paper_name(f,selection['selected'][f]) for f in ORDER]
    methods = [selection['selected'][f] for f in ORDER]
    rows = []
    def ms(value): return f'> {cap:.2f}' if value>=cap else '<0.001' if 0<value<.001 else f'{value:.3f}'
    for title,key,formatter in [('P50 (ms)','p50_ms',ms),('P95 (ms)','p95_ms',ms),
            ('Extra heap P95 (KiB)','heap_extra_peak_bytes_p95',fmt_kib),('RSS P95 (KiB)','rss_peak_bytes_p95',fmt_kib)]:
        values = [metrics[m]['full'][key] for m in methods]
        minimum = min((v for v in values if v is not None),default=None)
        row = [title]
        for value in values:
            label = formatter(value) if value is not None else '—'
            if value is not None and value==minimum and not (key.endswith('_ms') and value>=cap): label = r'$\color{green}{'+label+'}$'
            row.append(label)
        rows.append(row)
    rows.append(['Completed']+[f'{metrics[m]["full"]["completed"]}/{metrics[m]["full"]["cases"]}' for m in methods])
    asset = ROOT/f'docs/assets/ablation-{stage}.svg'
    asset.write_text(render_svg(headers,rows,'Book-grouped evaluation' if stage=='ebooks' else 'MiniZinc: validation-selected algorithms'))
    markdown = ''.join('| '+' | '.join(row)+' |\n' for row in [headers,['---']+['---:']*5,*rows])
    return asset, markdown


def main():
    protocol = load_protocol()
    selection = json.loads(SELECTION.read_text())
    assert selection['protocol_sha256']==sha(PROTOCOL)
    validation = {}
    for method in selection['metrics']:
        path = DIRECTORY/f'validation-{method}-timing.jsonl'
        assert sha(path)==selection['validation_raw_sha256'][str(path.relative_to(ROOT))]
        env, records = read_records(path)
        assert env['source_sha256']==selection['source_sha256']
        validation[method] = summarize(records,protocol['validation_cases'],protocol['timing']['repeats'],protocol['timing']['timeout_ms'])
        assert validation[method]==selection['metrics'][method]
    chosen = {f:min(ms,key=lambda m:(-validation[m]['completed'],validation[m]['p95_ms'],validation[m]['p50_ms'],m)) for f,ms in protocol['families'].items()}
    assert chosen==selection['selected']
    cap = protocol['timing']['timeout_ms']
    output = dict(protocol_sha256=sha(PROTOCOL), selection_sha256=sha(SELECTION), selected=chosen,
                  validation=validation, suites={}, raw_sha256={})
    text = '# Controlled evaluation and ablations\n\n'
    text += '**Retrospective evaluation:** both corpora were used in earlier algorithm development. Grouping prevents new configuration selection from crossing book boundaries; it does not turn these into previously unseen data or establish generalization to new books.\n\n'
    text += f'The [protocol](ablation-protocol.json) was committed before measurement. Book hashes and duplicate aliases define disjoint groups: **{len(protocol["validation_books"])} validation books / {len(protocol["validation_cases"])} cases**, **{len(protocol["evaluation_books"])} evaluation books / {len(protocol["evaluation_cases"])} cases**. All widths of a source table stay together. All **26 MiniZinc** instances are a separate evaluation suite. No evaluation result is used to choose the featured algorithm or ablation profile.\n\n'
    text += 'One full implementation per family is selected using validation completion count, then capped P95, median and name. The same frozen choice is used for both evaluation suites. Every measured configuration uses the same 1-second call limit, one warmup and three timed repetitions, with shuffled order. Three separate fresh-process memory repetitions measure extra live heap and process RSS. Input conversion, startup and JSON are outside library timing; all preparation and solver construction are inside.\n\n'
    text += '## Validation-only selection\n\n| Family | Selected implementation | Completed | P95 (ms) |\n| --- | --- | ---: | ---: |\n'
    for family in ORDER:
        m = chosen[family]; v = validation[m]
        text += f'| {family} | {paper_name(NAMES[m],m)} | {v["completed"]}/{v["cases"]} | {v["p95_ms"]:.4f} |\n'
    text += '\n[All validation metrics and locked selection](ablation/selection.json). Selection is based on these full configurations only; ablations are explanatory, not candidates selected on the evaluation set.\n\n'
    text += '## Configurations\n\n- **base:** search-family enhancements disabled; Pareto dominance and A* area/column-minimality mechanisms remain. Research models retain the prior compact encodings, static floors/caps and fixed-cell elimination, but disable the new root area bound and feasible-incumbent restrictions.\n- **common:** add the incumbent, area/floor bounds and global candidate caps to search methods, leaving terminal completion and compact paths off. For CP/LCG/MIP, common is identical to full and is not measured twice.\n- **full:** all current enhancements.\n- **without_X:** remove that enhancement from full. Removing the incumbent also removes its dependent row caps and root certificate in research models. This is an explicitly coupled removal, not an isolated measurement of incumbent construction.\n\n'
    text += 'The three-way base/common/full comparison and leave-one-out comparisons expose interactions but are not a full factorial design. Different engines still perform different propagation/inference; this is not a normalization of every internal pruning rule. [Exact flag values and applicability](ablation-protocol.json).\n'
    text += '\n<!-- effect-overview -->\n'
    readme = (ROOT/'README.md').read_text()
    workers = {}
    for stage, title in [('ebooks','Book-grouped evaluation'),('minizinc','MiniZinc evaluation')]:
        timing, envs, hashes = audit(stage,'timing',protocol,selection)
        memory, memory_envs, mem_hashes = audit(stage,'memory',protocol,selection)
        for mode, environments in [('timing',envs),('memory',memory_envs)]:
            binaries = {e['worker_sha256'] for e in environments.values()}
            assert len(binaries)==1
            binary = next(iter(binaries))
            assert workers.setdefault(mode,binary)==binary
        for m in envs:
            assert envs[m]['machine']==memory_envs[m]['machine'] and envs[m]['memory_bytes']==memory_envs[m]['memory_bytes']
            assert envs[m]['rustc']==memory_envs[m]['rustc'] and envs[m]['platform']==memory_envs[m]['platform']
        metrics = results(timing,memory,cap)
        output['suites'][stage] = metrics
        output['raw_sha256'].update(hashes); output['raw_sha256'].update(mem_hashes)
        asset, table = primary_table(stage,metrics,selection,cap)
        svg = ROOT/f'docs/assets/ablation-{stage}-performance.svg'
        svg.write_text(performance_svg({f:metrics[chosen[f]]['full'] for f in ORDER},title))
        text += f'\n## {title}\n\n![{title}; Pareto DP outlined in blue, minima in green.](assets/{asset.name}?v={sha(asset)[:12]})\n\n<details>\n<summary>Table data and paper links</summary>\n\n'+table+'\n</details>\n\n'
        text += f'![Performance profiles: {title}](assets/{svg.name}?v={sha(svg)[:12]})\n\n'
        text += 'Performance-profile denominator includes every case. An implementation counts as solved only when all repetitions finish optimally; failures have infinite ratios. At 1×, the curve gives the fraction of cases where that implementation is fastest. The log-scale x-axis includes every finite ratio, so each curve ends at its completion fraction.\n'
        for family in ORDER:
            method = chosen[family]
            text += f'\n### {family}: {NAMES[method]}\n\n| Configuration | Completed | P50 (ms) | P95 (ms) | Heap P95 (KiB) | RSS P95 (KiB) | Memory completed | Root certificates | Paired time / full | Pairs |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n'
            for profile in protocol['profiles'][method]:
                r = metrics[method][profile]
                def ms(x): return f'> {cap:.2f}' if x>=cap else f'{x:.4f}'
                def mem(key): return fmt_kib(r[key]) if r[key] is not None else '—'
                ratio = f'{r["paired_geomean_ratio_to_full"]:.3f}×' if r['paired_geomean_ratio_to_full'] is not None else '—'
                text += f'| {profile} | {r["completed"]}/{r["cases"]} | {ms(r["p50_ms"])} | {ms(r["p95_ms"])} | {mem("heap_extra_peak_bytes_p95")} | {mem("rss_peak_bytes_p95")} | {r["memory_completed"]}/{r["cases"]} | {r["root_certified_cases"]} | {ratio} | {r["paired_cases"]} |\n'
            issues = {p:{k:v for k,v in r['statuses'].items() if k not in ('optimal','timeout')} for p,r in metrics[method].items()}
            issues = {p:s for p,s in issues.items() if s}
            if issues: text += '\nNon-timeout failures (retained in aggregates): `'+json.dumps(issues)+'`.\n'
            memory_issues = {p:{k:v for k,v in r['memory_statuses'].items() if k not in ('optimal','timeout')} for p,r in metrics[method].items()}
            memory_issues = {p:s for p,s in memory_issues.items() if s}
            if memory_issues: text += '\nNon-timeout memory-pass failures: `'+json.dumps(memory_issues)+'`.\n'
            missing = {p:r['cases']-r['memory_measured'] for p,r in metrics[method].items() if r['memory_measured'] != r['cases']}
            if missing: text += '\nCases missing memory telemetry (aggregates withheld): `'+json.dumps(missing)+'`.\n'
        env = next(iter(envs.values()))
        n = len(env['case_ids'])
        block = f'Latest controlled run: **{env["utc"][:10]}**, {env["machine"]}, {env["memory_bytes"]//2**30} GiB RAM. **{n} '+('cases from 21 evaluation books' if stage=='ebooks' else 'MiniZinc public cases')+'**, single thread, 3 measurements, 1-second limit.\n\n'
        block += 'Algorithms are fixed using 10 validation books. This is a **retrospective grouped evaluation**: both corpora were used in earlier development. Timing includes preparation, model/search and final layout; excludes text measurement, JSON and startup.\n\n'
        block += f'![Benchmark results; Pareto DP outlined in blue, minima in green.](docs/assets/{asset.name}?v={sha(asset)[:12]})\n\n<details>\n<summary>Table data and paper links</summary>\n\n'+table+'\n</details>\n\n'
        block += 'Memory is measured separately in fresh processes, including observed timeout peaks. Timeout percentiles are shown as **> 1000.00 ms**. [Protocol, all ablations and performance profiles](docs/ablation-report.md).\n'
        marker = 'benchmark' if stage=='ebooks' else 'benchmark-minizinc'
        begin,end = f'<!-- {marker}:start -->',f'<!-- {marker}:end -->'
        a,b = readme.index(begin)+len(begin),readme.index(end)
        readme = readme[:a]+'\n'+block+readme[b:]
    overview = '## Observed effects\n\nFull configurations are kept fixed even where a leave-one-out configuration has a lower P95. Small differences are descriptive measurements, not claims of statistical significance.\n\n| Suite | Method | Base P95 (ms) | Full P95 (ms) | Base completed | Full completed |\n| --- | --- | ---: | ---: | ---: | ---: |\n'
    for stage,label in [('ebooks','Books'),('minizinc','MiniZinc')]:
        for family in ORDER:
            m = chosen[family]
            base,full = (output['suites'][stage][m][p] for p in ['base','full'])
            def ms(x): return f'> {cap:.2f}' if x>=cap else f'{x:.4f}'
            overview += f'| {label} | {family} | {ms(base["p95_ms"])} | {ms(full["p95_ms"])} | {base["completed"]}/{base["cases"]} | {full["completed"]}/{full["cases"]} |\n'
    root_ranges = {}
    for stage in ['ebooks','minizinc']:
        counts = [output['suites'][stage][m]['full']['root_certified_cases'] for m in chosen.values()]
        root_ranges[stage] = str(min(counts)) if min(counts)==max(counts) else f'{min(counts)}–{max(counts)}'
    overview += f'\nFull configurations certify **{root_ranges["ebooks"]}/{len(protocol["evaluation_cases"])} book cases** at the root, versus **{root_ranges["minizinc"]}/{len(protocol["minizinc_cases"])} MiniZinc cases**. These calls remain timed. This helps explain the suite-level difficulty difference under the same deadline and timing scope.\n'
    text = text.replace('<!-- effect-overview -->',overview)
    text += '\n## Interpretation and limits\n\nP50/P95 use one median per case; incomplete timing repetitions are censored at the common limit. Paired ratios are geometric means of per-case time ratios on cases completed by both configurations; values above 1 mean slower than full. The pair count and completion counts must be read alongside the ratio, since unsolved cases are excluded from that paired statistic. Aggregate ratios alone do not establish statistical significance or an isolated causal effect in the presence of interactions.\n\n'
    text += 'Root certificates represent preprocessing that already proves optimality; their cost is timed. Memory percentiles include observed timeout peaks and are not bounds on memory needed to finish. A configuration missing any memory telemetry has its aggregate memory withheld. Instrumented memory timings are not substituted for uninstrumented runtime. Raw records retain failures, individual runs and solver statistics.\n\n'
    text += 'Source hashes, release-binary hashes, Rust version, machine details and protocol/selection hashes are recorded in every raw file. The existing abstract Lean proof covers the abstract Pareto reductions, not an end-to-end proof of all solver implementations. Every returned exact layout is checked against the fixed reference optimum, and all frozen configurations have independent exhaustive-width regression tests.\n\n'
    text += '## Reproduce\n\nUse macOS for the RSS collector and a full Git clone containing the frozen protocol commit. Preserve the published records before rerunning: the harness refuses to overwrite existing results. Selection is recomputed from the new validation measurements, so another machine may select different implementations.\n\n```sh\nmkdir -p .tools\nmv docs/ablation .tools/ablation-published\npython3 scripts/ablation_protocol.py\npython3 scripts/benchmark_ablation.py validation\npython3 scripts/benchmark_ablation.py select\npython3 scripts/benchmark_ablation.py minizinc\npython3 scripts/benchmark_ablation.py ebooks\npython3 scripts/benchmark_ablation.py minizinc --mode memory\npython3 scripts/benchmark_ablation.py ebooks --mode memory\npython3 scripts/report_ablation.py\n```\n\nTo regenerate tables from the published measurements without rerunning solvers, run only `python3 scripts/report_ablation.py`. The legacy `report_native.py --suite ebooks|minizinc` command generates the earlier comparison; running it replaces the corresponding README table with that separate experiment.\n\n'
    text += '[Protocol](ablation-protocol.json) · [Locked selection](ablation/selection.json) · [Summary and raw-file hashes](ablation-summary.json) · [Raw records](ablation/)\n\n[Optimization benchmarking guidelines](https://arxiv.org/abs/1709.08242) · [Ablation analysis](https://www.cs.ubc.ca/labs/algorithms/Projects/Ablation/) · [Performance profiles](https://doi.org/10.1007/S101070100263)\n'
    (ROOT/'docs/ablation-summary.json').write_text(json.dumps(output,indent=2)+'\n')
    (ROOT/'docs/ablation-report.md').write_text(text)
    (ROOT/'README.md').write_text(readme)
    print('Audited and generated both controlled tables, all ablations and performance profiles.')


if __name__ == '__main__': main()
