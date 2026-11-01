#!/usr/bin/env python3
import copy
import unittest

from benchmark_memory import parse_rss
from report_memory import summarize


def fixture():
    env = dict(methods=['cp2011'],repeats=3,timeout_ms=1000)
    inputs = [dict(sample_index=i,width=10,input_sha256=str(i)) for i in range(2)]
    records = []
    for i, values in enumerate([[10,20,300],[30,40,500]]):
        runs = [dict(status='timeout',layout=None,memory_available=True,
                     heap_baseline_bytes=100,heap_peak_bytes=100+v,
                     heap_extra_peak_bytes=v,heap_end_bytes=100,rss_peak_bytes=1000+v)
                for v in values]
        records.append(dict(case=i,algorithm='cp2011',sample_index=i,width=10,
                            input_sha256=str(i),runs=runs))
    return env, records, inputs


class MemoryTests(unittest.TestCase):
    def test_macos_rss_is_bytes_and_not_footprint(self):
        self.assertEqual(parse_rss('  123456 maximum resident set size\n  99999 peak memory footprint\n'),123456)

    def test_missing_ambiguous_and_zero_rss_fail(self):
        for text in ['', '0 maximum resident set size',
                     '1 maximum resident set size\n2 maximum resident set size']:
            with self.assertRaises(ValueError):
                parse_rss(text)

    def test_timeouts_included_and_repetitions_reduced_per_case(self):
        s = summarize(*fixture())['cp2011']
        self.assertEqual((s['completed'],s['measured']),(0,2))
        self.assertEqual(s['metrics']['heap_extra_peak_bytes'],dict(p50=30,p95=40,maximum=40))

    def test_missing_telemetry_withholds_aggregates(self):
        env, records, inputs = fixture()
        records[0]['runs'][1] = dict(status='timeout',layout=None,memory_available=False)
        s = summarize(env,records,inputs)['cp2011']
        self.assertEqual(s['measured'],1)
        self.assertTrue(all(v is None for v in s['metrics'].values()))

    def test_duplicate_cases_and_bad_accounting_fail(self):
        env, records, inputs = fixture()
        duplicates = [records[0],copy.deepcopy(records[0])]
        with self.assertRaises(AssertionError):
            summarize(env,duplicates,inputs)
        records[0]['runs'][0]['heap_extra_peak_bytes'] = 900
        with self.assertRaises(AssertionError):
            summarize(env,records,inputs)


if __name__=='__main__':
    unittest.main()
