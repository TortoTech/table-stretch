#!/usr/bin/env python3
"""Summarize retained timings; never turn a timeout into an optimal result."""
import json
import math
from pathlib import Path
import statistics
from collections import Counter


def quantiles(values):
    values = sorted(values)
    if not values: return None
    return {'count': len(values), 'p50_ms': statistics.median(values),
            'p95_ms': values[math.ceil(.95*len(values))-1],
            'p99_ms': values[math.ceil(.99*len(values))-1], 'max_ms': values[-1]}


def main():
    native = [json.loads(l) for l in Path('docs/benchmark-rust.jsonl').read_text().splitlines()]
    external = [json.loads(l) for l in Path('docs/benchmark-external.jsonl').read_text().splitlines()]
    tables = {r['sample_index']: r for r in native if r['kind']=='table'}
    cases = [r for r in native if r['kind']=='case']
    ext = [r for r in external if r['kind']=='case']
    selection = {tuple(k) for k in external[0]['selection']}
    methods = list(dict.fromkeys(r['algorithm'] for r in ext))
    assert len(ext)==len(selection)*len(methods), 'external comparison incomplete'
    assert all(r['status']=='completed' for r in native if r['kind']=='worker')
    summary = {'native_environment': native[0], 'external_environment': {k:external[0][k] for k in ['minizinc','repeats','timeout_ms','threads','seed','compiler_optimization']},
               'tables':len(tables), 'cases':len(cases)//3, 'native':{}, 'selected':{}, 'common':{}}
    lines = ['# 扩大书库实测与研究算法对比', '',
             f"实测环境：{native[0]['cpu']}，{native[0]['platform']}，{native[0]['rustc']}。", '',
             '完整数据：317 个表格、25 本 EPUB、7241 个单元格；比初版新增 301 个表格。最多 10 列、150 行，最长单元格 441 个 tokens。包含 368 个按 CJK 字符模型测量的单元格。70 个合并单元格表格不支持，未混入计时。另有 13 个 XML 文档解析失败，不声称覆盖其内容。', '',
             '扫描 67 本 EPUB 得到 827 个 table；317 个可用，414 个不满足矩形测试尺寸（至少 2 行 2 列等），70 个跨格，24 个非文本，2 个行列不齐。本次没有因长文本上限排除表格。数据是完整符合过滤条件的集合，未按算法成功与否筛选。', '',
             '每表选最小宽、最小宽加 8/24/64、伸缩区间的 10%/25%/50%/75%、最大内容宽，截断并去重，共 2332 个场景。26 个表格只有一个可选宽度，因此总集合中包含简单样本。', '',
             '## 全部场景：Rust', '',
             'Release 构建；逐表独立进程、单线程，每个算法/宽度先预热一次、测五次。以下分位数来自每场景五次计时的中位数；单位为 ms。失败场景不混入成功耗时分位数，另列计数。', '',
             '| 方法 | 最优/可行完成 | 超限 | P50 | P95 | P99 | 最慢成功 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for method in ['pareto','astar2011','html']:
        group = [r for r in cases if r['algorithm']==method]
        good = [r for r in group if r['status'] in {'optimal','heuristic'}]
        q = quantiles([r['solve']['median_ns']/1e6 for r in good])
        summary['native'][method] = {'statuses':dict(Counter(r['status'] for r in group)), 'successful_time':q}
        lines.append(f"| {method} | {len(good)}/{len(group)} | {len(group)-len(good)} | {q['p50_ms']:.6f} | {q['p95_ms']:.6f} | {q['p99_ms']:.6f} | {q['max_ms']:.6f} |")
    lines += ['', '`html` 的完成表示可行启发式结果，不表示最优；其 `optimal` 标记始终为 false。A* 与 Pareto 共同成功的全部场景目标相同。每个成功输出重新从原始 token 宽度断行计算行高，并检查总宽、上下限、精确算法不劣于基线。', '']
    lookup_quality = {(r['algorithm'],r['sample_index'],r['width']):r for r in cases}
    html = [r for r in cases if r['algorithm']=='html']
    worse = [r for r in html if r['height'] > lookup_quality['astar2011',r['sample_index'],r['width']]['height']]
    summary['html_suboptimal_cases'] = len(worse)
    lines += [f"比例启发式在 {len(worse)}/{len(html)} 个场景上严格高于最优布局；其速度不能等价为相同质量下的性能优势。", '']
    prep = quantiles([t['profile_build']['median_ns']/1e6 for t in tables.values()])
    summary['profile_build'] = prep
    lines += [f"单表曲线构造另计：P50 {prep['p50_ms']:.6f} ms，P95 {prep['p95_ms']:.6f} ms，最大 {prep['max_ms']:.6f} ms。以上不含 EPUB 解压、字体 shaping、CSS 处理或 torto 实际绘制。", '',
              '## 相同复杂子集：全部方法', '',
              f'选择 {len(selection)} 个场景：先包含全部 Pareto 超限案例，再按列数、行数、断点数各选代表，并加入慢例。选择清单存于外部结果文件首行；不代表全书库随机分布。外部模型预热一次、计时三次，搜索限时 1 秒，进程兜底再加 10 秒。', '',
              '| 方法 | 最优完成/案例数（HTML仅可行） | 成功端到端 P50 | 成功端到端 P95 | 引擎 solveTime P50 |',
              '| --- | ---: | ---: | ---: | ---: |']
    common = set(selection)
    for method in ['pareto','astar2011']:
        common &= {(r['sample_index'],r['width']) for r in cases if r['algorithm']==method and r['status']=='optimal'}
    for method in methods:
        common &= {(r['sample_index'],r['width']) for r in ext if r['algorithm']==method and r['all_optimal']}
    for method in ['pareto','astar2011','html']+methods:
        if method in methods:
            group = [r for r in ext if r['algorithm']==method]
            good = [r for r in group if r['all_optimal']]
            times = [r['wall_median_ns']/1e6 for r in good]
            engine = [statistics.median(x['statistics']['solveTime'] for x in r['runs'])*1000 for r in good if all('solveTime' in x.get('statistics',{}) for x in r['runs'])]
            statuses = dict(Counter(x['status'] for r in group for x in r['runs']))
            same = [r['wall_median_ns']/1e6 for r in good if (r['sample_index'],r['width']) in common]
        else:
            group = [r for r in cases if r['algorithm']==method and (r['sample_index'],r['width']) in selection]
            good = [r for r in group if r['status'] in {'optimal','heuristic'}]
            times = [r['solve']['median_ns']/1e6 for r in good]
            engine = []
            statuses = dict(Counter(r['status'] for r in group))
            same = [r['solve']['median_ns']/1e6 for r in good if (r['sample_index'],r['width']) in common]
        q = quantiles(times); e = quantiles(engine)
        summary['selected'][method] = {'statuses':statuses,'completed':len(good),'cases':len(group),'wall':q,'engine':e}
        summary['common'][method] = quantiles(same)
        engine_text = '—' if e is None else ('<1 ms（统计分辨率）' if e['p50_ms']==0 else f"{e['p50_ms']:.3f}")
        lines.append(f"| {method} | {len(good)}/{len(group)} | {q['p50_ms']:.6f} | {q['p95_ms']:.6f} | {engine_text} |")
    summary['common_cases'] = len(common)
    lines += ['', '注意：Rust 列是库函数完整耗时；外部端到端列包括进程启动、MiniZinc 编译与求解。引擎时间只供理解开销来源，不能直接当作与 Rust 完全同范围的计时。Chuffed 的毫秒统计存在量化。外部最优结果均与同场景 A* 结果核对。', '',
              f'全部精确方法共同成功的场景有 {len(common)} 个；对应同一子集的端到端分位数保存在 `benchmark-summary.json` 的 `common`，避免成功子集不同造成误读。', '',
              '外部编译统一使用 `-O0`，避开独立穷举发现的默认编译优化回归。已通过 70 个模型/小实例的独立穷举检查，详见算法说明。', '', '## 超限与困难案例', '', '| 书名 | 行×列 | 宽度 | Pareto 状态 | Pareto 返回耗时 ms | A* 耗时 ms |', '| --- | --- | ---: | --- | ---: | ---: |']
    lookup = {(r['algorithm'],r['sample_index'],r['width']):r for r in cases}
    for r in cases:
        if r['algorithm']=='pareto' and r['status']!='optimal':
            t=tables[r['sample_index']];a=lookup['astar2011',r['sample_index'],r['width']]
            lines.append(f"| {t['book']} | {t['rows']}×{t['columns']} | {r['width']} | {r['status']} | {r['solve']['median_ns']/1e6:.3f} | {a['solve']['median_ns']/1e6:.3f} |")
    lines += ['', '外部未能在所有重复中证明最优的场景：', '']
    for r in ext:
        if not r['all_optimal']:
            t=tables[r['sample_index']]
            runs=[{'status': x['status'], 'height': x.get('solution',{}).get('height')} for x in r['runs']]
            lines.append(f"- {r['algorithm']}：{t['book']}，{t['rows']}×{t['columns']}，宽度 {r['width']}；{runs}")
    if all(r['all_optimal'] for r in ext): lines.append('无。')
    lines += ['', 'Pareto 的上述 8 个限制是比较次数达到 2000 万；外部 LCG 未完成来自 1 秒搜索限时。两者都不是搜索证明了不可行；不会输出伪最优结果。当前 Pareto 实现的成对支配扫描是明显瓶颈。宽松预算乃至不换行宽度也可能触发此瓶颈，因为尚无全局高度下界提前结束。', '',
              '## 复现与边界', '',
              '参见 [研究算法实现说明](algorithms.md)、`scripts/benchmark_corpus.py`、`scripts/compare_solvers.py`、`scripts/report_benchmarks.py`。原始 JSONL 包含单次计时、引擎统计、状态、版本和哈希。', '',
              '真实来源保留书名、SHA-256、章节和表格序号，但布局度量仍为简化英文词宽/CJK 字符宽模型，空白和段落被归一化。不是实际 torto 字体/CSS 渲染测试，也不能从最多 10 列的样本推出任意大表格的实时性。']
    Path('docs/benchmark.md').write_text('\n'.join(lines)+'\n')
    Path('docs/benchmark-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'native_environment','external_environment'}},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
