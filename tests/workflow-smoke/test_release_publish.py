"""Release state-machine tests: no credentials, network or actual releases."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'scripts/publish-release.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SHA = 'a' * 40
TAG = 'v0.4.0'
BASE = 'repos/send/shoutx/'


class FakeAPI:
    def __init__(self):
        self.releases = []
        self.assets = {}
        self.calls = []
        self.next_id = 1000
        self.tag = {'type': 'commit', 'sha': SHA}
        self.latest = None
        self.hook = lambda *args: None

    def draft(self, release_id=42, **updates):
        row = dict(id=release_id, tag_name=TAG, draft=True, immutable=False,
                   prerelease=False, body='Maintainer notes', name='Custom title')
        row.update(updates)
        self.releases.append(row)
        return row

    def api(self, method, endpoint, body=None, **kwargs):
        self.calls.append((method, endpoint, copy.deepcopy(body)))
        self.hook(method, endpoint, body)
        path = endpoint.removeprefix(BASE)
        if path.startswith('git/ref/tags/'):
            return {'object': copy.deepcopy(self.tag)}
        if path.startswith('git/tags/'):
            return {'object': {'type': 'commit', 'sha': SHA}}
        if path == 'releases/latest':
            return self.latest
        if path.startswith('releases?'):
            page = int(path.split('page=')[-1])
            return copy.deepcopy(self.releases[(page-1)*100:page*100])
        if path == 'releases' and method == 'POST':
            return copy.deepcopy(self.draft(77, tag_name=body['tag_name'], prerelease=body['prerelease']))
        if method == 'DELETE':
            self.assets.pop(int(path.split('/')[-1]))
            return None
        release_id = int(path.split('/')[1])
        row = next(r for r in self.releases if r['id'] == release_id)
        if '/assets?' in path:
            page = int(path.split('page=')[-1])
            assets = [dict(id=i, name=a[1], state='uploaded') for i, a in self.assets.items() if a[0] == release_id]
            return assets[(page-1)*100:page*100]
        if method == 'PATCH':
            row.update({k: v for k, v in body.items() if k != 'make_latest'})
            row['immutable'] = not row['draft']
        return copy.deepcopy(row)

    def upload(self, repo, release_id, path):
        self.calls.append(('UPLOAD', release_id, path.name))
        self.hook('UPLOAD', release_id, path.name)
        self.next_id += 1
        self.assets[self.next_id] = (release_id, path.name, path.read_bytes())
        return dict(id=self.next_id, name=path.name, state='uploaded')

    def download_digest(self, repo, asset_id):
        self.calls.append(('DOWNLOAD', asset_id, None))
        self.hook('DOWNLOAD', asset_id, None)
        data = self.assets[asset_id][2]
        return len(data), hashlib.sha256(data).hexdigest()


class PublishTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.env = dict(GITHUB_REPOSITORY='send/shoutx', TAG=TAG, GITHUB_SHA=SHA, PRERELEASE='false')
        self.api = FakeAPI()
        self.admitted = []
        names = [f'shoutx-{TAG}-{target}.tar.gz' for target in (
            'aarch64-apple-darwin', 'aarch64-unknown-linux-musl',
            'x86_64-apple-darwin', 'x86_64-unknown-linux-musl')]
        names.append(f'shoutx-{TAG}-x86_64-pc-windows-msvc.zip')
        for name in names:
            (self.directory / name).write_bytes(name.encode())
        self.manifest()

    def manifest(self):
        paths = sorted(p for p in self.directory.iterdir() if p.name != 'SHA256SUMS')
        (self.directory / 'SHA256SUMS').write_bytes(''.join(
            f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in paths).encode())

    def publish(self, admission=None):
        return p.publish(self.api, self.env, self.directory, admission or self.admitted.append)

    def mutations(self):
        return [c for c in self.api.calls if c[0] in ('POST', 'PATCH', 'DELETE', 'UPLOAD')]

    def test_initial_creation_captures_id_and_preserves_checks(self):
        self.assertEqual(self.publish(), 77)
        self.assertEqual(self.admitted, [SHA])
        mutations = self.mutations()
        self.assertEqual(sum(c[0] == 'POST' for c in mutations), 1)
        self.assertTrue(all(c[1] == 77 for c in mutations if c[0] == 'UPLOAD'))
        self.assertEqual(mutations[-1], ('PATCH', BASE + 'releases/77',
                                        dict(draft=False, prerelease=False, make_latest='true')))
        self.assertTrue(self.api.releases[0]['immutable'])

    def test_existing_draft_is_discovered_on_later_page_and_reused(self):
        for i in range(100):
            self.api.draft(100+i, tag_name=f'other-{i}')
        row = self.api.draft()
        for i in range(101):
            self.api.assets[300+i] = (42, f'old-{i}', b'old')
        self.assertEqual(self.publish(), 42)
        self.assertFalse(any(c[0] == 'POST' for c in self.api.calls))
        self.assertEqual(sum(c[0] == 'DELETE' for c in self.api.calls), 101)
        self.assertEqual(row['body'], 'Maintainer notes')
        self.assertEqual(row['name'], 'Custom title')
        self.assertEqual(len(self.api.assets), 6)

    def test_published_or_ambiguous_matches_never_mutate(self):
        for rows in ((dict(draft=False, immutable=True),), ({}, {}),
                     ({}, dict(draft=False, immutable=True))):
            with self.subTest(rows=rows):
                self.api = FakeAPI()
                for i, values in enumerate(rows):
                    self.api.draft(i+1, **values)
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual(self.mutations(), [])

    def test_listing_errors_do_not_mean_absence(self):
        self.api.hook = lambda method, endpoint, body: (_ for _ in ()).throw(ValueError('API failure')) if 'releases?' in endpoint else None
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.mutations(), [])

    def test_missing_wrong_or_deep_tag_prevents_mutation(self):
        self.api.tag = {'type': 'commit', 'sha': 'b'*40}
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.mutations(), [])

    def test_annotated_tag_is_resolved(self):
        self.api.tag = {'type': 'tag', 'sha': 'b'*40}
        self.assertEqual(self.publish(), 77)

    def test_upload_failure_retains_draft_and_retry_reuses_same_id(self):
        def fail(method, endpoint, body):
            if method == 'UPLOAD' and len(self.api.assets) == 2:
                raise ValueError('Upload interrupted')
        self.api.hook = fail
        with self.assertRaises(ValueError):
            self.publish()
        self.assertTrue(self.api.releases[0]['draft'])
        self.api.hook = lambda *args: None
        self.assertEqual(self.publish(), 77)
        self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_failed_admission_never_publishes(self):
        with self.assertRaises(ValueError):
            self.publish(lambda sha: (_ for _ in ()).throw(ValueError('Not admitted')))
        self.assertFalse(any(c[0] == 'PATCH' for c in self.api.calls))

    def test_lost_create_response_is_not_retried_and_later_run_reuses_draft(self):
        original = self.api.api
        def lost(method, endpoint, body=None, **kwargs):
            result = original(method, endpoint, body, **kwargs)
            if method == 'POST':
                raise ValueError('Response lost after server created draft')
            return result
        self.api.api = lost
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(len(self.api.releases), 1)
        self.api.api = original
        self.assertEqual(self.publish(), 77)
        self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_tag_drift_after_admission_blocks_publication(self):
        with self.assertRaises(ValueError):
            self.publish(lambda sha: self.api.tag.update(sha='b'*40))
        self.assertFalse(any(c[0] == 'PATCH' for c in self.api.calls))

    def test_wrong_id_or_tag_on_read_blocks_mutation(self):
        for key, value in (('id', 999), ('tag_name', 'v9.0.0')):
            self.api = FakeAPI()
            self.api.draft()
            original = self.api.api
            def wrong(method, endpoint, body=None, **kwargs):
                row = original(method, endpoint, body, **kwargs)
                if endpoint == BASE+'releases/42':
                    row[key] = value
                return row
            self.api.api = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.publish()
            self.assertEqual(self.mutations(), [])

    def test_incomplete_listing_stops_without_creation(self):
        original = self.api.api
        def endless(method, endpoint, body=None, **kwargs):
            if endpoint.startswith(BASE+'releases?'):
                return [dict(id=i+1, tag_name='other') for i in range(100)]
            return original(method, endpoint, body, **kwargs)
        self.api.api = endless
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.mutations(), [])

    def test_failed_immutable_assertion_does_not_attempt_cleanup(self):
        original = self.api.api
        def mutable(method, endpoint, body=None, **kwargs):
            result = original(method, endpoint, body, **kwargs)
            if method == 'PATCH':
                self.api.releases[0]['immutable'] = False
            return result
        self.api.api = mutable
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.mutations()[-1][0], 'PATCH')

    def test_latest_rollback_or_unknown_latest_blocks_publication(self):
        for tag in ('v0.5.0', 'moving-tag'):
            self.api = FakeAPI()
            self.api.latest = {'tag_name': tag}
            with self.assertRaises(ValueError):
                self.publish()
            self.assertFalse(any(c[0] == 'PATCH' for c in self.api.calls))

    def test_prerelease_does_not_move_latest(self):
        self.env.update(TAG='v0.4.0-rc.1', PRERELEASE='true')
        for path in list(self.directory.iterdir()):
            if path.name != 'SHA256SUMS':
                path.rename(path.with_name(path.name.replace(TAG, self.env['TAG'])))
        self.manifest()
        self.publish()
        self.assertEqual(self.mutations()[-1][2]['make_latest'], 'false')
        self.assertFalse(any(c[1] == BASE+'releases/latest' for c in self.api.calls))

    def test_state_change_before_asset_mutation_blocks_it(self):
        row = self.api.draft()
        self.api.assets[99] = (42, 'old', b'old')
        def change(method, endpoint, body):
            if endpoint == BASE+'releases/42':
                row.update(draft=False, immutable=True)
        self.api.hook = change
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.mutations(), [])

    def test_new_duplicate_before_publication_blocks_it(self):
        with self.assertRaises(ValueError):
            self.publish(lambda sha: self.api.draft(88))
        self.assertFalse(any(c[0] == 'PATCH' for c in self.api.calls))

    def test_mismatching_downloaded_bytes_block_publication(self):
        self.api.download_digest = lambda *args: (1, '0'*64)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse(any(c[0] == 'PATCH' for c in self.api.calls))

    def test_wrong_local_manifest_stops_before_network(self):
        (self.directory/'SHA256SUMS').write_bytes(b'wrong')
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.api.calls, [])

    def test_workflow_has_single_publisher_and_tests(self):
        workflow = (ROOT/'.github/workflows/release.yml').read_text()
        self.assertIn('run: python3 -B scripts/publish-release.py', workflow)
        self.assertIn('run: python3 -B tests/workflow-smoke/test_release_publish.py', workflow)
        for command in ('gh release create', 'gh release upload', 'gh release edit', 'gh release download'):
            self.assertNotIn(command, workflow)


class TransportTests(unittest.TestCase):
    def test_upload_and_download_are_id_bound_and_binary_safe(self):
        result = SimpleNamespace(returncode=0, stdout=b'{"id":123}')
        with patch.object(p.subprocess, 'run', return_value=result) as run:
            self.assertEqual(p.GitHub().upload('send/shoutx', 77, Path('dist/SHA256SUMS')), {'id': 123})
            self.assertIn('https://uploads.github.com/repos/send/shoutx/releases/77/assets?name=SHA256SUMS', run.call_args.args[0])
            self.assertIn('dist/SHA256SUMS', run.call_args.args[0])
        data = b'\x00\x1b\xffrelease-bytes'
        def download(args, **kwargs):
            self.assertIn('repos/send/shoutx/releases/assets/123', args)
            self.assertIn('Accept: application/octet-stream', args)
            kwargs['stdout'].write(data)
            return SimpleNamespace(returncode=0)
        with patch.object(p.subprocess, 'run', side_effect=download):
            self.assertEqual(p.GitHub().download_digest('send/shoutx', 123),
                             (len(data), hashlib.sha256(data).hexdigest()))

    def test_http_errors_are_not_treated_as_missing(self):
        for code in (403, 429, 500):
            result = SimpleNamespace(returncode=1, stdout=f'HTTP/2.0 {code}\nX-Test: a\n\n{{}}')
            with patch.object(p.subprocess, 'run', return_value=result), self.assertRaises(ValueError):
                p.GitHub().api('GET', 'repos/send/shoutx/releases/latest', missing=True)
        result = SimpleNamespace(returncode=1, stdout='HTTP/2.0 404\n\n{}')
        with patch.object(p.subprocess, 'run', return_value=result):
            self.assertIsNone(p.GitHub().api('GET', 'repos/send/shoutx/releases/latest', missing=True))
            with self.assertRaises(ValueError):
                p.GitHub().api('GET', 'repos/send/shoutx/releases')

    def test_create_is_draft_and_response_id_is_returned(self):
        result = SimpleNamespace(returncode=0, stdout='HTTP/2.0 201 Created\n\n{"id":77}')
        with patch.object(p.subprocess, 'run', return_value=result) as run:
            self.assertEqual(p.GitHub().api('POST', BASE+'releases', {'draft': True}), {'id': 77})
            self.assertEqual(json.loads(run.call_args.kwargs['input']), {'draft': True})


if __name__ == '__main__':
    unittest.main()
