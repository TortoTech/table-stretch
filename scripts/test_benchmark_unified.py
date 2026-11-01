#!/usr/bin/env python3
"""Regression tests for the benchmark protocol, independent of MiniZinc."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest

from benchmark_unified import ROOT, interpret, run_process, verify


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.instance = {'table': json.loads((ROOT/'examples/table.json').read_text()), 'reference_height': 3}
        self.layout = {'column_widths': [7,3], 'row_heights': [2,1], 'total_height': 3, 'optimal': True}

    def test_deadline_kills_descendants(self):
        code = """import subprocess, sys, time
p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
print(p.pid, flush=True)
time.sleep(20)
"""
        raw = run_process([sys.executable, '-c', code], 400)
        self.assertTrue(raw['timeout'])
        self.assertTrue(raw['lines'])
        pid = int(raw['lines'][0][1])
        try:
            proc = subprocess.run(['ps','-o','stat=','-p',str(pid)], capture_output=True, text=True)
            self.assertTrue(proc.returncode != 0 or proc.stdout.strip().startswith('Z'), proc.stdout)
        finally:
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass

    def test_result_without_exit_is_not_optimal_completion(self):
        result = json.dumps({'kind':'result','status':'optimal','layout':self.layout})
        code = f'import time; print({result!r}, flush=True); time.sleep(20)'
        raw = run_process([sys.executable, '-c', code], 200)
        self.assertTrue(raw['lines'])
        run = interpret(raw, self.instance, 'pareto')
        self.assertEqual(run['status'], 'timeout')
        self.assertFalse(run['layout']['optimal'])

    def test_finished_result_and_no_output_timeout(self):
        result = json.dumps({'kind':'result','status':'optimal','layout':self.layout})
        raw = run_process([sys.executable, '-c', f'print({result!r})'], 2000)
        self.assertEqual(interpret(raw, self.instance, 'pareto')['status'], 'optimal')
        raw = run_process([sys.executable, '-c', 'import time; time.sleep(20); print(1)'], 100)
        self.assertTrue(raw['timeout'])
        self.assertEqual(raw['lines'], [])

    def test_invalid_layouts_are_rejected(self):
        verify(self.instance['table'], self.layout, 3)
        for change in [{'column_widths':[5,5]}, {'row_heights':[6,1]}, {'total_height':2}, {'column_widths':[7,2]}]:
            with self.assertRaises(AssertionError):
                verify(self.instance['table'], {**self.layout, **change}, 3)


if __name__ == '__main__':
    unittest.main()
