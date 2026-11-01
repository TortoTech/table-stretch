#!/usr/bin/env python3
"""Regression checks for censored cases and paired/profile denominators."""
import math
import unittest

from report_ablation import profile_points, results


def case(index, values):
    return dict(case=index, runs=[dict(status='optimal' if value else 'timeout',
        wall_ns=value, layout=dict(stats=dict(generated=0, terminal_evaluations=0, bound_pruned=1))
        if value else None) for value in values])


class ReportTests(unittest.TestCase):
    def test_performance_profiles_keep_unsolved_cases_and_ties(self):
        ratios, n = profile_points({
            'a':dict(case_ms={'0':1, '1':None, '2':None, '3':2}),
            'b':dict(case_ms={'0':2, '1':3, '2':None, '3':2})})
        self.assertEqual(n, 4)
        self.assertEqual(ratios['a'], [1, math.inf, math.inf, 1])
        self.assertEqual(ratios['b'], [2, 1, math.inf, 1])

    def test_pairing_requires_all_runs_and_missing_memory_is_not_zero(self):
        full = [case(0,[1_000_000]*3), case(1,[1_000_000]*3)]
        base = [case(0,[2_000_000]*3), case(1,[None,1_000_000,1_000_000])]
        timing = {('a','full'):full, ('a','base'):base}
        memory = {key:[dict(case=c['case'],runs=[dict(
            status=r['status'],memory_available=True,heap_extra_peak_bytes=1024,rss_peak_bytes=2048)
            for r in c['runs']]) for c in cases] for key,cases in timing.items()}
        memory['a','base'][0]['runs'][0]['memory_available'] = False
        summary = results(timing,memory,1000)['a']['base']
        self.assertEqual(summary['completed'],1)
        self.assertEqual(summary['paired_cases'],1)
        self.assertEqual(summary['paired_geomean_ratio_to_full'],2)
        self.assertIsNone(summary['case_ms']['1'])
        self.assertEqual(summary['memory_measured'],1)
        self.assertIsNone(summary['heap_extra_peak_bytes_p95'])
        self.assertIsNone(summary['rss_peak_bytes_p95'])


if __name__ == '__main__': unittest.main()
