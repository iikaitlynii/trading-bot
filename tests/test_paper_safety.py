"""Public entrypoints must never mutate or silently restart legacy accounts."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import paper_trader as stock
import crypto_paper_trader as crypto
import forward_shadow as forward


class PaperSafetyTests(unittest.TestCase):
    def test_legacy_accounts_fail_before_network_and_remain_byte_exact(self):
        for module,folder in [(stock,'paper'),(crypto,'crypto_paper'),(forward,'research_lab/forward')]:
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                previous=os.getcwd();os.chdir(tmp)
                try:
                    Path(folder).mkdir(parents=True)
                    paths=[Path(folder)/name for name in ('state.json','journal.csv','performance.csv')]
                    for path in paths:path.write_bytes(b'Unresolved original bytes\r\n')
                    before=[p.read_bytes() for p in paths]
                    with patch('simulation_v2.runner.accepted',side_effect=AssertionError('no input access')):
                        with self.assertRaisesRegex(ValueError,'BLOCKED'):module.main()
                    self.assertEqual(before,[p.read_bytes() for p in paths])
                    self.assertFalse(Path('simulation-v2').exists())
                finally:os.chdir(previous)

    def test_no_legacy_files_still_requires_complete_accepted_inputs(self):
        from simulation_v2.runner import run
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):run('stock',root=Path(tmp))
            self.assertFalse((Path(tmp)/'simulation-v2').exists())
