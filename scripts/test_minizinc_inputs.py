#!/usr/bin/env python3
"""Check DZN import semantics independently against the original configurations."""
import json
import unittest

from build_minizinc_inputs import SOURCE, OUTPUT, parse_dzn, convert, configurations, verify_original
from benchmark_unified import canonical, sha
import hashlib


class MiniZincImportTests(unittest.TestCase):
    def test_padding_order_and_dominated_configurations(self):
        data = parse_dzn('''pixelwidth=30; rows=2; cols=2; maxconfig=4;
          width=array3d(ROWS,COLS,CONFIGS,[8,3,5,-1, 7,2,2,-1, 6,1,-1,-1, 4,2,-1,-1]);
          height=array3d(ROWS,COLS,CONFIGS,[2,7,8,-1, 1,6,9,-1, 2,5,-1,-1, 1,3,-1,-1]);''')
        table = convert(data)
        self.assertEqual(table['columns'][0]['cells'][0]['steps'],
                         [dict(width=3, height=7), dict(width=8, height=2)])
        self.assertEqual(table['columns'][1]['cells'][0]['steps'],
                         [dict(width=2, height=6), dict(width=7, height=1)])
        self.assertEqual(table['columns'][0]['cells'][1]['steps'][0], dict(width=1, height=5))

    def test_reject_mismatched_padding_and_dimensions(self):
        data = dict(pixelwidth=10, rows=1, cols=1, maxconfig=1, width=[-1], height=[2])
        with self.assertRaises(ValueError):
            convert(data)
        with self.assertRaises(ValueError):
            parse_dzn('pixelwidth=10; rows=1; cols=1; maxconfig=2; '
                      'width=array3d(ROWS,COLS,CONFIGS,[1]); height=array3d(ROWS,COLS,CONFIGS,[2]);')

    def test_all_sources_and_every_curve_breakpoint(self):
        source = json.loads((SOURCE/'source.json').read_text())
        inputs = json.loads(OUTPUT.read_text())
        self.assertEqual(len(inputs), 26)
        for name, entry in source['files'].items():
            self.assertEqual(sha(SOURCE/name), entry['sha256'])
        for item in inputs:
            data = parse_dzn((SOURCE/item['source_file']).read_text())
            table = convert(data)
            self.assertEqual(table, item['table'])
            self.assertEqual(hashlib.sha256(canonical(table)).hexdigest(), item['input_sha256'])
            for c, col in enumerate(table['columns']):
                for r, cell in enumerate(col['cells']):
                    configs = configurations(data, r, c)
                    # Both sides are constant between configuration widths.
                    probes = {0, data['pixelwidth']}
                    probes.update(x for w, _ in configs for x in [w-1, w])
                    for width in probes:
                        expected = min((h for w, h in configs if w <= width), default=None)
                        actual = [s['height'] for s in cell['steps'] if s['width'] <= width]
                        self.assertEqual(actual[-1] if actual else None, expected)

    def test_reference_witnesses_against_raw_dzn(self):
        inputs = json.loads(OUTPUT.read_text())
        audit = json.loads((OUTPUT.parent/'minizinc-validation.json').read_text())
        self.assertEqual(audit['input_manifest_sha256'], sha(OUTPUT))
        self.assertEqual(len(audit['cases']), len(inputs))
        for item, case in zip(inputs, audit['cases']):
            self.assertEqual(case['source_file'], item['source_file'])
            data = parse_dzn((SOURCE/item['source_file']).read_text())
            witnesses = [a for a in case['attempts'] if a['status'] == 'optimal']
            self.assertGreaterEqual(len(witnesses), 2)
            self.assertEqual([a['method'] for a in witnesses], item['reference_verified_by'])
            for result in witnesses:
                verify_original(data, result['layout'])
                self.assertEqual(result['layout']['total_height'], item['reference_height'])


if __name__ == '__main__':
    unittest.main()
