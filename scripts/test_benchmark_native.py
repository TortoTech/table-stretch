#!/usr/bin/env python3
"""Exercise the persistent worker watchdog and late-result policy."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from benchmark_native import Worker

FAKE = '''
import json, sys, time
for line in sys.stdin:
    r = json.loads(line)
    if r['algorithm'] == 'partial':
        print('{', end='', flush=True)
        time.sleep(60)
    if r['algorithm'] == 'closed':
        import os
        os.close(1)
        time.sleep(60)
    if r['algorithm'] == 'hang':
        time.sleep(60)
    print(json.dumps(dict(id=r['id'], wall_ns=20_000_000 if r['algorithm']=='late' else 1,
                         status='optimal', layout={'sentinel': True}, phases={})), flush=True)
'''
POPEN = subprocess.Popen


def fake_process(*args, **kwargs):
    return POPEN([sys.executable, '-u', '-c', FAKE], **kwargs)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = Worker(Path('unused'), 10)
        self.addCleanup(self.worker.close)
        patcher = patch('benchmark_native.subprocess.Popen', side_effect=fake_process)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_calls_reuse_one_process(self):
        first = self.worker.run(0, 'ok')
        pid = self.worker.proc.pid
        second = self.worker.run(1, 'ok')
        self.assertEqual(pid, self.worker.proc.pid)
        self.assertEqual(first['worker_generation'], second['worker_generation'])
        self.assertEqual(second['status'], 'optimal')

    def test_late_optimum_is_discarded(self):
        result = self.worker.run(0, 'late')
        self.assertEqual(result['status'], 'timeout')
        self.assertIsNone(result['layout'])
        self.assertIsNone(result['phases'])
        self.assertEqual(result['wall_ns'], 20_000_000)

    def test_partial_response_still_has_a_deadline(self):
        result = self.worker.run(0, 'partial')
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['error'], 'hard watchdog')
        self.assertIsNone(self.worker.proc)

    def test_closed_output_does_not_wait_forever_for_process_exit(self):
        result = self.worker.run(0, 'closed')
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(self.worker.proc)

    def test_hung_worker_is_reaped_and_restarted(self):
        result = self.worker.run(0, 'hang')
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['error'], 'hard watchdog')
        self.assertIsNone(self.worker.proc)
        next_result = self.worker.run(1, 'ok')
        self.assertEqual(next_result['status'], 'optimal')
        self.assertEqual(next_result['worker_generation'], 2)


if __name__ == '__main__':
    unittest.main()
