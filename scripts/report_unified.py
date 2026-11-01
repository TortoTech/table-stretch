#!/usr/bin/env python3
"""Generate the primary unified benchmark report and README table."""
import json
import math
from pathlib import Path
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

from benchmark_unified import METHODS, ROOT, sha, verify

NAMES = {'pareto':'**Pareto DP（优化后，当前默认）**', 'pareto_baseline':'Pareto DP（优化前对照）', 'astar2011':'A* 2011（Rust）',
         'html':'W3C 比例法（启发式）', 'cp2011_gecode':'配置 CP / Gecode（旧适配，列宽搜索）',
         'lcg2011_chuffed':'配置 LCG / Chuffed（旧适配，混合搜索）',
         'lcg2015_cellfree':'cell-free LCG / Chuffed（旧适配，无 RCSV）',
         'mip2015_unary':'基础 unary MIP / HiGHS', 'mip2015_onehot':'基础 one-hot MIP / HiGHS',
         'cp2011_chuffed_seq':'2011 cp-w / Chuffed（最小格高搜索适配）',
         'lcg2011_chuffed_seq':'2011 cp-seq / Chuffed（最小格高搜索适配）',
         'lcg2015_rcsv':'2015 cpcf / Chuffed（RCSV 简单表格适配）',
         'mip2015_cellfree':'2015 mipcf / HiGHS（RCSV＋unary 适配）'}


def quantile(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(len(values)*p)-1)] if values else None


def describe(values):
    return {'median': statistics.median(values), 'p95': quantile(values, .95),
            'max': max(values)} if values else None


def median_phase(cases, *keys):
    values = []
    for case in cases:
        per_run = []
        for run in case['runs']:
            value = run['phases']
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            if value is not None:
                per_run.append(value)
        if per_run:
            values.append(statistics.median(per_run))
    return statistics.median(values) if values else None


def fmt(value, divisor=1):
    return '—' if value is None else f'{value/divisor:.3f}'


def main():
    rows = [json.loads(line) for line in (ROOT/'docs/benchmark-unified.jsonl').read_text().splitlines()]
    env, records = rows[0], rows[1:]
    methods = env['methods']
    assert set(methods) in (set(METHODS), set(METHODS) | {'pareto_baseline'})
    native_methods = [m for m in methods if m in ('pareto_baseline','pareto','astar2011','html')]
    external_methods = [m for m in methods if m not in native_methods]
    inputs_path = ROOT/'docs/benchmark-unified-inputs.json'
    assert sha(inputs_path) == env['input_manifest_sha256']
    inputs = {(r['sample_index'],r['width']):r for r in json.loads(inputs_path.read_text())}
    expected = {tuple(pair) for pair in env['selection']}
    n, repeats = len(expected), env['repeats']
    assert len(records) == n*len(methods)
    grouped = {m: [r for r in records if r['algorithm']==m] for m in methods}
    for method, cases in grouped.items():
        assert {(r['sample_index'],r['width']) for r in cases} == expected
        for case in cases:
            instance = inputs[case['sample_index'],case['width']]
            assert case['input_sha256'] == instance['input_sha256']
            assert len(case['runs']) == repeats
            for run in case['runs']:
                assert run['status'] in ('optimal', 'heuristic', 'timeout')
                assert run['status'] != 'heuristic' or method == 'html'
                if run['status'] != 'timeout':
                    assert run['wall_ns'] <= env['timeout_ms']*1e6
                if run['layout']:
                    verify(instance['table'],run['layout'],instance['reference_height'])
    common = expected.copy()
    for m in methods:
        common &= {(r['sample_index'],r['width']) for r in grouped[m] if r['all_completed']}
    summary = {'cases': n, 'repeats': repeats, 'common_completed_cases':len(common),
               'common_selection':sorted(common), 'methods':{}}
    for m, cases in grouped.items():
        runs = [run for r in cases for run in r['runs']]
        capped = [statistics.median(min(run['wall_ns']/1e6,env['timeout_ms']) for run in r['runs']) for r in cases]
        completed = [r['wall_median_ns']/1e6 for r in cases if r['all_completed']]
        common_cases = [r for r in cases if (r['sample_index'],r['width']) in common]
        timeouts = [r for r in runs if r['status']=='timeout']
        gaps = [r['gap'] for r in timeouts if r['gap'] is not None]
        summary['methods'][m] = {
            'completed_cases': sum(r['all_completed'] for r in cases),
            'optimal_cases': sum(r['all_optimal'] for r in cases),
            'timeout_runs': len(timeouts), 'capped_wall_ms':describe(capped),
            'successful_wall_ms':describe(completed),
            'common_wall_ms':describe([r['wall_median_ns']/1e6 for r in common_cases]),
            'native_total_ms':describe([statistics.median(sum(run['phases']['native'].values()) for run in r['runs'])/1e6 for r in cases if r['all_completed']]) if m in native_methods else None,
            'native_stats':{key:describe([statistics.median(run['layout']['stats'].get(key,0) for run in r['runs']) for r in cases if r['all_completed']]) for key in ('generated','comparisons','peak_frontier','bound_pruned','terminal_evaluations')} if m in native_methods else None,
            'par2_ms': statistics.mean(2*env['timeout_ms'] if r['status']!='optimal' else r['wall_ns']/1e6 for r in runs) if m!='html' else None,
            'timeout_gap':describe(gaps), 'timeout_missing_feasible':sum(r['layout'] is None for r in timeouts),
            'equal_reference_cases': sum(all(run['layout'] and run['layout']['total_height']==r['reference_height'] for run in r['runs']) for r in cases),
            'phase_common': {
                'read_ns':median_phase(common_cases,'read_ns'), 'fallback_ns':median_phase(common_cases,'fallback_ns'),
                'native_prepare_ns':median_phase(common_cases,'native','prepare_ns'),
                'native_search_ns':median_phase(common_cases,'native','search_ns'),
                'native_finalize_ns':median_phase(common_cases,'native','finalize_ns'),
                'export_ns':median_phase(common_cases,'export_ns'),
                'flat_seconds':median_phase(common_cases,'engine_statistics','flatTime'),
                'init_seconds':median_phase(common_cases,'engine_statistics','initTime'),
                'solve_seconds':median_phase(common_cases,'engine_statistics','solveTime')}}
    data = summary['methods']
    table = '| 方法 | 完成场景 | 超时运行 | 端到端 P50（ms） | P95（ms） | PAR-2（ms） |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
    for m in methods:
        s=data[m]
        table+=f"| {NAMES[m]} | {s['completed_cases']}/{n} | {s['timeout_runs']}/{n*repeats} | {fmt(s['capped_wall_ms']['median'])} | {fmt(s['capped_wall_ms']['p95'])} | {fmt(s['par2_ms'])} |\n"
    date = datetime.fromisoformat(env['utc']).astimezone(ZoneInfo('US/Pacific')).strftime('%Y-%m-%d')
    rust_version = env['rustc'].splitlines()[0].split()[1]
    participants = f'{len(methods)-bool(env.get("baseline"))} 种方法' + ('及 1 个优化前对照' if env.get('baseline') else '')
    lead = f"""实测日期：{date}（US/Pacific）。{env['machine']}、{env['memory_bytes']//2**30} GiB 内存、{env['platform']}、Rust {rust_version}，release 构建、单线程。

**{participants}使用统一标准重测**：同一组 {n} 个复杂/多样场景、同一份曲线 JSON、相同的 Rust worker 协议；每次从启动进程前到进程退出及输出收完计时。输入读取、验证、方法自身预处理、模型编译、搜索、最终拉伸与输出全部计入；每次总墙钟限时 **{env['timeout_ms']/1000:g} 秒**。Rust 搜索次数限制在本次基准中关闭，生产库默认值不变。每场景/方法预热 1 次、测量 {repeats} 次，各方法按固定种子打乱顺序，串行运行。

场景沿用此前外部测试的选择，来自 25 本书、317 个真实表格的 2332 个宽度场景，包含此前全部 8 个 Pareto 搜索超限案例。这是复杂场景子集，不是全书库的随机抽样。

**研究对齐审计已更正方法标注**：旧配置 CP 不等于论文的 cp-w，旧 cell-free 缺少 RCSV，两个基础 MIP 不代表论文的 mipcf。此次保留旧版本，并加入最小单元格高度搜索、无学习 Chuffed、RCSV 与共享 unary cell-free MIP 对照。仍是当前工具链上的简单表格适配，非历史实现完整复现；详见[逐项审计](docs/research-audit.md)。

**本轮同时修复超时清理后重测**：旧版仅清理 worker 进程组，可能留下另建进程组的 Chuffed，干扰后续计时。现在冻结并清理整个存活进程树。本轮数据取代此前可能受干扰的计时；模型前后比较均使用本轮结果。
"""
    definitions = f"""“完成场景”要求 {repeats} 次均在时限内完成；精确方法须证明最优，W3C 仅要求返回可行解。P50/P95 在**全部 {n} 个场景**上统计：先取每场景 {repeats} 次耗时的中位数，再取跨场景分位数；超时按 {env['timeout_ms']} ms 截断。PAR-2 对全部 {n*repeats} 次运行取平均：成功用实际耗时，超时罚为 {2*env['timeout_ms']} ms，越小越好；启发式不参与该精确求解评分。不能把截断耗时当作超时任务真正完成所需时间。
"""
    native_p50 = [data[m]['capped_wall_ms']['median'] for m in METHODS[:3]]
    result_text = f"""当前默认 Pareto 完成 **{data['pareto']['completed_cases']}/{n}** 个场景，A* 完成 **{data['astar2011']['completed_cases']}/{n}**；所有已证明最优的结果均与参考最优高度一致。W3C 比例法在 {n-data['html']['equal_reference_cases']}/{n} 个场景未达到最优高度。Rust 三种方法的端到端 P50 为 {min(native_p50):.3f}–{max(native_p50):.3f} ms，其中已计入进程及输入输出成本；搜索差异另见阶段诊断。耗时表示当前实现的部署成本，不能据此推断原论文历史实现的速度。

所有方法都从预先构造的相同尺寸曲线开始，因此共同排除文本曲线构造、字体 shaping、EPUB 解压和绘制。超时保留截止时刻前收到的最佳可行布局，不标记为最优。MiniZinc 统一使用 `-O0`，相关编译器回归见[算法说明](docs/algorithms.md#编译优化回归)。
"""
    optimization = ''
    if env.get('baseline'):
        before, after = data['pareto_baseline'], data['pareto']
        optimization = f"优化前后在**同一轮交错测量**：Pareto 端到端 P95 从 **{before['capped_wall_ms']['p95']:.3f} ms** 降至 **{after['capped_wall_ms']['p95']:.3f} ms**；原生求解阶段（准备＋搜索＋拉伸）P95 从 **{before['native_total_ms']['p95']:.3f} ms** 降至 **{after['native_total_ms']['p95']:.3f} ms**。这些是各自分位数，不是逐场景加速比。优化前 worker 来自提交 `{env['baseline']['commit'][:7]}`，源码与二进制身份保存在元数据中。\n"
    readme_section = '## 当前 benchmark\n\n'+lead+'\n'+table+'\n'+definitions+'\n'+optimization+'\n'+result_text+"\n详情与复现：[统一报告](docs/benchmark-unified.md) · [原始记录](docs/benchmark-unified.jsonl) · [相同输入及哈希](docs/benchmark-unified-inputs.json) · [汇总](docs/benchmark-unified-summary.json)。[旧报告](docs/benchmark.md)保留历史库函数计时，不再作为跨方法的主对比。\n\n"
    readme_path=ROOT/'README.md'
    readme=readme_path.read_text()
    start,end=readme.index('## 当前 benchmark'),readme.index('## 运行')
    readme_path.write_text(readme[:start]+readme_section+readme[end:])
    report='# 统一端到端 benchmark\n\n'+lead.replace('(docs/','(')+'\n'+table+'\n'+definitions+'\n'+result_text.replace('(docs/','(')
    if optimization:
        report+='\n## Pareto 优化前后\n\n'+optimization
        report+='\n末列直接完成、上下界剪枝、前沿原地删除、延迟分配和父节点索引均计入新版本求解。算法仍保持精确最优；同高解的列宽选择可能改变。原生阶段的下表使用全部成功场景，单位 ms，与后文共同子集的分项表范围不同。\n\n'
        report+='| 实现 | 原生阶段 P50 | 原生阶段 P95 | 支配比较次数 P95 | 最大前沿 P95 |\n| --- | ---: | ---: | ---: | ---: |\n'
        for m in ('pareto_baseline','pareto','astar2011'):
            s=data[m]
            # A* comparisons count cell minimality tests, not DP dominance.
            comparisons = f"{s['native_stats']['comparisons']['p95']:,.0f}" if m!='astar2011' else '—'
            report+=f"| {NAMES[m]} | {fmt(s['native_total_ms']['median'])} | {fmt(s['native_total_ms']['p95'])} | {comparisons} | {s['native_stats']['peak_frontier']['p95']:,.0f} |\n"
        corpus_path = ROOT/'docs/benchmark-rust-optimized.jsonl'
        if corpus_path.exists():
            corpus = [json.loads(line) for line in corpus_path.read_text().splitlines()]
            assert all(r['status']=='completed' for r in corpus if r['kind']=='worker')
            corpus_cases = [r for r in corpus if r['kind']=='case' and r['algorithm']=='pareto']
            corpus_refs = {(r['sample_index'],r['width']):r['height'] for r in corpus if r['kind']=='case' and r['algorithm']=='astar2011' and r['status']=='optimal'}
            assert len(corpus_cases)==2332
            assert all(r['status']=='optimal' and r['height']==corpus_refs[r['sample_index'],r['width']] for r in corpus_cases)
            report+='\n另外在 **317 个真实表格、2332 个宽度场景** 上使用生产默认限制运行新版 Pareto 与 A*，全部完成且最优高度一致；从原始词宽重算行高验证内容可容纳。这是[全书库差分与库函数诊断](benchmark-rust-optimized.jsonl)，其函数耗时不混入端到端主表。\n'
    report+='\n## 相同成功子集\n\n'
    report+=f'下表固定为全部 {len(methods)} 个被测实现都完成的 **{len(common)} 个相同场景**，没有按方法删去不同的困难实例。它仍是有条件统计，主表的超时与 PAR-2 不可省略。单位 ms。\n\n'
    report+='| 方法 | 端到端 P50 | P95 | 最慢场景中位数 |\n| --- | ---: | ---: | ---: |\n'
    for m in methods:
        s=data[m]['common_wall_ms']
        report+=f"| {NAMES[m]} | {fmt(s['median'])} | {fmt(s['p95'])} | {fmt(s['max'])} |\n"
    report+='\n## 超时后的可行解\n\n所有方法在求解前运行相同的 W3C 可行布局作为兜底，成本全部计入，worker 不把该布局传入搜索器。优化后的 Pareto 会在自己的计时准备阶段独立计算可行解上界；其他方法保持原实现。外部求解器另外读取中间解；原生 Pareto/A* 当前没有中间解接口。以下是这个返回协议的质量，不把它当作纯搜索算法的 anytime 能力比较。相对差距为 `(返回高度−最优高度)/最优高度`。差距为零仅表示事后与参考答案一致，不表示被测求解器在截止前证明了最优。\n\n'
    report+='| 方法 | 超时次数 | 未取得可行解 | 超时差距 P50 | 最大差距 |\n| --- | ---: | ---: | ---: | ---: |\n'
    for m in methods:
        s=data[m]
        if s['timeout_runs']:
            gap=s['timeout_gap']
            report+=f"| {NAMES[m]} | {s['timeout_runs']} | {s['timeout_missing_feasible']} | {fmt(gap['median']*100) if gap else '—'}% | {fmt(gap['max']*100) if gap else '—'}% |\n"
    if not any(s['timeout_runs'] for s in data.values()):
        report+='| 全部方法 | 0 | 0 | — | — |\n'
    report+='\n## 阶段耗时诊断\n\n与上一节相同的共同成功子集。先取每场景重复测量的中位数，再取跨场景中位数。阶段统计只用于解释开销，主排名始终使用同一父进程计时器的端到端耗时。各阶段中位数之和不一定等于总耗时中位数。\n\n'
    report+='原生阶段由 Rust `Instant` 计时。准备包括验证、候选离散化、A* 的面积下界预处理，以及新版 Pareto 的上下界准备；搜索包括搜索状态初始化，不含最终拉伸。输入 JSON 读取和公共兜底另外计入端到端。为便于阅读，此表单位为 **µs**；极短阶段可能低于计时器分辨率，显示 0 不表示没有工作。\n\n'
    report+='| 原生方法 | 准备 | 搜索/比例分配 | 最终拉伸 |\n| --- | ---: | ---: | ---: |\n'
    for m in native_methods:
        s=data[m]['phase_common']
        report+=f"| {NAMES[m]} | {fmt(s['native_prepare_ns'],1e3)} | {fmt(s['native_search_ns'],1e3)} | {fmt(s['native_finalize_ns'],1e3)} |\n"
    report+='\n外部模型导出包含验证、转换和临时 JSON 写入；编译/初始化/搜索是引擎自身的统计，阶段边界、时钟和精度并不完全一致，不据此计算与原生搜索的倍数。Chuffed 的 `solveTime` 精度为毫秒；`0` 不表示零成本，`—` 表示未报告。单位 ms。\n\n'
    report+='| 外部方法 | 模型导出 | flatTime | initTime | solveTime |\n| --- | ---: | ---: | ---: | ---: |\n'
    for m in external_methods:
        s=data[m]['phase_common']
        report+=f"| {NAMES[m]} | {fmt(s['export_ns'],1e6)} | {fmt(s['flat_seconds'],.001)} | {fmt(s['init_seconds'],.001)} | {fmt(s['solve_seconds'],.001)} |\n"
    report+='''
## 可复现协议

- 输入是 `Table` 的完整阶梯曲线。清单固定源表位置、容器宽度、列上下限、曲线、参考高度和规范 JSON 的 SHA-256；每个场景的全部方法读取完全相同的文件字节，方法特有的预处理在计时内完成。
- 当前各方法使用同一 `unified_worker`，旧版对照使用旧提交构建的同协议 worker。父进程在 `Popen` 前读单调时钟，收完 stdout/stderr 并等待退出后停止。参考答案校验在计时后统一进行；worker 内的解解析、校验、拉伸和序列化在计时内。临时目录和通用输入文件在计时前准备；MiniZinc 专用输入文件在计时内生成。
- 统一限制为单线程、每次 1 秒总墙钟；不再使用 Rust 的 2000 万比较限制，也不再给予外部求解器“编译完后额外 1 秒”。所有方法都不另外设置内存配额。超时冻结并清理整个存活进程树（包含求解器另建的进程组），清理后才运行下一方法；清理耗时另存，不进入 PAR-2。只接受截止前完整收到的输出行，输出了最优结果但未按时退出也按超时处理。
- 外部引擎：MiniZinc 2.10.1、Gecode 6.4.0、Chuffed 0.14.0、HiGHS 1.15.1；单线程、种子 1、`-O0 --intermediate-solutions`，旧 Chuffed 适配使用 `-f --vsids`（混合搜索）；新增 cp-w/cp-seq 固定最小格高搜索，新增 cpcf 固定 VSIDS；逐方法参数写入元数据。逐次新建进程，预热后测量，未清空操作系统文件缓存。方法顺序用种子 1 打乱；没有并发运行被测任务。
- 每个最优解均与参考高度比较，所有可行解独立重算原始曲线上的行高，检查列上下限、恰好填满容器、目标和可行性。参考高度来自原有 A* 全语料运行；原生算法另有全整数宽度穷举差分测试，九种外部模型通过 144 个独立穷举模型/实例组合（包括编译器回归、不可行实例、硬下限落在断点间）。这些检查不等于证明求解器实现对所有输入正确。
- 当前输入是从真实 EPUB 内容提取的简化词宽/CJK 字符宽模型。不支持的合并单元格未入选；不含真实字体/CSS 排版成本，不能外推为任意表格的实时保证。

```sh
# 在仓库根目录，安装 Rust 与包含 Gecode/Chuffed/HiGHS 的 MiniZinc。
# 构建优化前对照（工作树目录首次创建）：
git worktree add --detach .tools/pareto-before-source 104c545
cargo build --locked --release --manifest-path .tools/pareto-before-source/Cargo.toml --example unified_worker
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc \\
  --baseline-worker .tools/pareto-before-source/target/release/examples/unified_worker
python3 scripts/report_unified.py
bash scripts/check.sh
```

计时脚本当前针对 macOS（环境信息使用 `sysctl`，超时清理使用 POSIX 信号和 `ps` 父子关系快照）。可省略 `--minizinc` 并将可执行路径写入 `.tools/minizinc-path.txt`。默认直接使用已提交的输入清单；`--rebuild-inputs` 从历史原始数据重建相同选择。测试运行可用 `--cases 1 --repeats 1 --output /tmp/smoke.jsonl`。正式报告要求完整场景集合，参数与源码/二进制哈希均存于首行元数据。

数据：[逐次记录与状态](benchmark-unified.jsonl) · [输入清单](benchmark-unified-inputs.json) · [统计汇总](benchmark-unified-summary.json) · [算法及研究范围](algorithms.md)。历史不同计时口径的结果保留在[旧报告](benchmark.md)，不混入本表。
'''
    (ROOT/'docs/benchmark-unified.md').write_text(report)
    (ROOT/'docs/benchmark-unified-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(table)
    print(f'Common completed cases: {len(common)}')


if __name__ == '__main__':
    main()
