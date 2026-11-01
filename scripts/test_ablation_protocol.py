#!/usr/bin/env python3
import json
import unittest

from ablation_protocol import ROOT, build, profiles
from benchmark_ablation import summarize


class ProtocolTests(unittest.TestCase):
    def test_frozen_grouping_and_no_geometry_leakage(self):
        p = build()
        self.assertEqual(p, json.loads((ROOT/'docs/ablation-protocol.json').read_text()))
        a, b = set(p['validation_books']), set(p['evaluation_books'])
        self.assertFalse(a & b)
        inputs = json.loads((ROOT/'docs/benchmark-library-inputs.json').read_text())
        self.assertEqual(set(p['validation_cases']) | set(p['evaluation_cases']), set(range(len(inputs))))
        seen = {}
        for role, ids in [('validation',p['validation_cases']),('evaluation',p['evaluation_cases'])]:
            for index in ids:
                case = inputs[index]
                for key in [('sample',case['sample_index']),('geometry',case['input_sha256']),('book',case['book_sha256'])]:
                    self.assertEqual(seen.setdefault(key,role),role)

    def test_profile_dependencies_and_mandatory_mechanisms(self):
        self.assertTrue(profiles('astar2011')['base']['area_bound'])
        self.assertFalse(profiles('pareto')['base']['area_bound'])
        for m in ['cp2011','lcg2015','mip2015_cellfree']:
            p = profiles(m)['without_incumbent']
            self.assertFalse(p['row_caps'])
            self.assertFalse(p['root_certificate'])

    def test_failed_repetition_does_not_count_as_complete(self):
        records = [dict(case=5,runs=[dict(status='optimal',wall_ns=1_000_000),
            dict(status='timeout',wall_ns=None),dict(status='timeout',wall_ns=1_200_000_000)])]
        self.assertEqual(summarize(records,[5],3,1000),dict(completed=0,cases=1,p50_ms=1000,p95_ms=1000))


if __name__ == '__main__': unittest.main()
