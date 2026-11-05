"""Exercise the workflow publication script offline with a recording Git stub."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


class PublicationTests(unittest.TestCase):
    def test_failed_simulation_publishes_evidence_only(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/crypto-paper-trading.yml').read_text()
        step = workflow.split('      - name: Save crypto paper state\n', 1)[1]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1].split(
            '\n      - name:', 1)[0])
        for outcome in ('failure', 'skipped', 'success'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                stub = directory/'git'
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GIT_LOG"\n')
                stub.chmod(0o755)
                log = directory/'commands'
                environment = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                                   SIMULATION_OUTCOME=outcome, GIT_LOG=str(log))
                subprocess.run(['bash', '-e', '-c', script], env=environment,
                               cwd=directory, check=True, capture_output=True)
                commands = log.read_text().splitlines()
                self.assertIn('add research/datasets/ingested/', commands)
                account = [line for line in commands if line.startswith('add crypto_paper/')]
                self.assertEqual(bool(account), outcome == 'success')
                self.assertFalse(any(line.startswith('push') for line in commands))
