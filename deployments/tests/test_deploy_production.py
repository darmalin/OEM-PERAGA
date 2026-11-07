"""Exercise release orchestration using real temporary Git repos and fake services.

Run: python3 -m unittest discover -s deployments/tests -v
No production Docker commands or network requests are made.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json,os,pathlib,sys,tarfile,io
a=sys.argv[1:]
with open(os.environ['COMMAND_LOG'],'a') as f: f.write(json.dumps(a)+'\n')
fail=os.environ.get('FAIL','')
if a[0]=='inspect':
 if '--format' in a: print(os.environ['PROD_DIR'])
 else: print(json.dumps([{'Image':'sha256:old','Id':a[-1]}]))
elif a[0]=='image': pass
elif a[0]=='commit': print('preserved')
elif a[0]=='run':
 out=a[a.index('-v')+1].rsplit(':/out',1)[0]
 dest=pathlib.Path(out)/pathlib.Path(a[a.index('czf')+1]).name
 with tarfile.open(dest,'w:gz') as t:
  content=b'files'; info=tarfile.TarInfo('fixture'); info.size=len(content); t.addfile(info,io.BytesIO(content))
elif a[0]=='compose':
 i=1
 while a[i].startswith('-'):
  i+=2
 c=a[i:]; op=c[0]
 if op=='config': print(json.dumps({'name':'ems-prod','services':{'api':{'environment':{'EMS_ENVIRONMENT':'production','EMS_PUBLIC_BASE_URL':'https://production.test'}}}}))
 elif op=='ps': print('existing-container')
 elif op=='build' and fail=='build': sys.exit(19)
 elif op=='run':
  if fail=='migration': sys.exit(20)
  print('buckets ready')
 elif op=='exec':
  if 'postgres' in c and 'sh' in c:
   if fail=='backup': sys.exit(21)
   sys.stdout.buffer.write(b'database backup fixture')
  elif 'pg_restore' in c: print('dump manifest')
  elif 'alembic' in c: print('0024 (head)')
'''


class DeployProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.staging = self.base / 'ems-staging'
        self.prod = self.base / 'ems-prod'
        self.remote = self.base / 'origin.git'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.log = self.base / 'commands.jsonl'
        self.staging.mkdir()
        self.git(self.staging, 'init', '-q', '-b', 'main')
        self.git(self.staging, 'config', 'user.name', 'Release Test')
        self.git(self.staging, 'config', 'user.email', 'release@example.test')
        shutil.copy2(ROOT / 'deploy-production.sh', self.staging)
        (self.staging / 'deployments/backup').mkdir(parents=True)
        shutil.copy2(ROOT / 'deployments/backup/backup.sh', self.staging / 'deployments/backup')
        (self.staging / '.gitignore').write_text('.env\n')
        (self.staging / 'compose.yaml').write_text('services: {}\n')
        (self.staging / 'app.txt').write_text('old\n')
        self.git(self.staging, 'add', '.')
        self.git(self.staging, 'commit', '-qm', 'initial')
        self.old = self.git(self.staging, 'rev-parse', 'HEAD').strip()
        self.git(self.base, 'init', '--bare', '-q', str(self.remote))
        self.git(self.staging, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.staging, 'push', '-q', '-u', 'origin', 'main')
        self.git(self.base, 'clone', '-q', '-b', 'main', str(self.remote), str(self.prod))
        self.git(self.prod, 'checkout', '-q', '--detach')
        (self.prod / '.env').write_text('COMPOSE_PROJECT_NAME=ems-prod\nCOMPOSE_FILE=compose.yaml\n')
        (self.prod / 'backups').mkdir()
        (self.prod / 'backups/keep.txt').write_text('existing backup')
        for name, body in {
            'docker': FAKE_DOCKER,
            'curl': '#!/bin/sh\nprintf \'{"status":"ok"}\\n\'\n',
            'sleep': '#!/bin/sh\nexit 0\n',
        }.items():
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        self.env = {
            **os.environ,
            'PATH': f'{self.bin}:{os.environ["PATH"]}',
            'PROD_DIR': str(self.prod),
            'COMMAND_LOG': str(self.log),
        }

    def git(self, directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args], text=True, stderr=subprocess.DEVNULL)

    def run_deploy(self, *args, fail=''):
        return subprocess.run(
            ['bash', str(self.staging / 'deploy-production.sh'), *args],
            env={**self.env, 'FAIL': fail}, capture_output=True, text=True, timeout=30,
        )

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def change(self):
        (self.staging / 'app.txt').write_text('new\n')

    def test_check_is_read_only_even_with_uncommitted_changes(self):
        self.change()
        result = self.run_deploy('--check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.staging, 'rev-parse', 'HEAD').strip(), self.old)
        self.assertFalse((self.base / 'backups').exists())
        self.assertFalse(any('build' in c or 'stop' in c for c in self.commands()))

    def test_same_commit_is_noop(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any('build' in c or 'stop' in c for c in self.commands()))

    def test_dirty_production_is_never_overwritten(self):
        (self.prod / 'app.txt').write_text('production edit')
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.prod / 'app.txt').read_text(), 'production edit')

    def test_no_commit_option_rejects_dirty_staging(self):
        self.change()
        result = self.run_deploy('--no-commit')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.staging, 'rev-parse', 'HEAD').strip(), self.old)

    def test_success_commits_pushes_backs_up_migrates_and_preserves_configuration(self):
        self.change()
        (self.staging / 'backups').mkdir()
        (self.staging / 'backups/local.dump').write_text('not source code')
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = self.git(self.staging, 'rev-parse', 'HEAD').strip()
        self.assertNotEqual(target, self.old)
        self.assertEqual(self.git(self.prod, 'rev-parse', 'HEAD').strip(), target)
        self.assertEqual(self.git(self.staging, 'ls-files', 'backups/'), '')
        self.assertEqual((self.prod / 'backups/keep.txt').read_text(), 'existing backup')
        release = next((self.base / 'backups/ems-prod').glob('release-*'))
        self.assertTrue((release / 'SUCCESS').exists())
        self.assertEqual((release / 'production.env').read_text(), (self.prod / '.env').read_text())
        self.assertTrue(next(release.glob('*.dump')).stat().st_size)
        calls = self.commands()
        build = next(i for i,c in enumerate(calls) if 'build' in c)
        stop = next(i for i,c in enumerate(calls) if 'stop' in c)
        migrate = next(i for i,c in enumerate(calls) if 'run' in c and 'migrate' in c)
        self.assertLess(build, stop)
        self.assertLess(stop, migrate)

    def test_build_failure_restores_previous_checkout_without_downtime(self):
        self.change()
        result = self.run_deploy(fail='build')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.prod, 'rev-parse', 'HEAD').strip(), self.old)
        self.assertFalse(any('stop' in c for c in self.commands()))

    def test_backup_failure_recovers_old_services_and_does_not_migrate(self):
        self.change()
        result = self.run_deploy(fail='backup')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.prod, 'rev-parse', 'HEAD').strip(), self.old)
        self.assertFalse(any('run' in c and 'migrate' in c for c in self.commands()))
        self.assertTrue(any(any('rollback.compose.json' in a for a in c) and 'up' in c for c in self.commands()))

    def test_migration_failure_stops_writers_without_restoring_database(self):
        self.change()
        result = self.run_deploy(fail='migration')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no database restore was attempted', result.stdout)
        self.assertFalse(any('pg_restore' in c and '--list' not in c for c in self.commands()))
        self.assertFalse(any('up' in c for c in self.commands()))
        release = next((self.base / 'backups/ems-prod').glob('release-*'))
        self.assertFalse((release / 'SUCCESS').exists())


if __name__ == '__main__':
    unittest.main()
