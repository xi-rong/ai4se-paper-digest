import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from paper_digest.storage import GitStore, Conflict, empty


class GitPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.remote, self.a, self.b = root / 'remote.git', root / 'a', root / 'b'
        self.run_git(root, 'init', '--bare', str(self.remote))
        self.run_git(root, 'clone', str(self.remote), str(self.a))
        self.run_git(self.a, 'checkout', '-b', 'digest-state')
        (self.a / 'state.json').write_text(json.dumps(empty()))
        self.run_git(self.a, 'add', 'state.json')
        self.run_git(self.a, '-c', 'user.name=Test', '-c', 'user.email=test@example.org', 'commit', '-m', 'init')
        self.run_git(self.a, 'push', 'origin', 'digest-state')
        self.run_git(root, 'clone', '--branch', 'digest-state', str(self.remote), str(self.b))
        self.cfg = {'branch': 'digest-state', 'path': 'state.json'}

    def run_git(self, cwd, *args):
        return subprocess.run(['git', *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def test_fresh_checkout_reads_prior_checkpoint_without_changing_working_files(self):
        a = GitStore(self.cfg, cwd=self.a)
        state, head = a.load()
        state['persistence_probe'] = {'id': 'first-cloud-task'}
        before = (self.a / 'state.json').read_bytes()
        a.save(state, head)
        b = GitStore(self.cfg, cwd=self.b)
        second, _ = b.load()
        self.assertEqual(second['persistence_probe']['id'], 'first-cloud-task')
        self.assertEqual((self.a / 'state.json').read_bytes(), before)

    def test_competing_cloud_tasks_reject_stale_push(self):
        a, b = GitStore(self.cfg, cwd=self.a), GitStore(self.cfg, cwd=self.b)
        first, h1 = a.load()
        second, h2 = b.load()
        first['probe'] = 'a'
        second['probe'] = 'b'
        a.save(first, h1)
        with self.assertRaises(Conflict):
            b.save(second, h2)
        self.assertEqual(b.load()[0]['probe'], 'a')


if __name__ == '__main__':
    unittest.main()
