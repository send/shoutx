"""Publish one ID-bound native release. Invoked only by the tag publish job."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(type(value) is int and value > 0, 'Invalid API object ID')
    return value


def file_digest(source):
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


class GitHub:
    def api(self, method, endpoint, body=None, missing=False):
        args = ['gh', 'api', '--hostname', 'github.com', '--include',
                '--method', method, endpoint]
        if body is not None:
            args += ['--input', '-']
        result = subprocess.run(args, input=None if body is None else json.dumps(body),
                                text=True, capture_output=True, timeout=60)
        headers, separator, payload = result.stdout.partition('\n\n')
        status = re.match(r'HTTP/\S+ (\d{3})\b', headers)
        require(separator and status, 'Missing API response status')
        code = int(status[1])
        if missing and code == 404:
            return None
        require(result.returncode == 0 and 200 <= code < 300, 'GitHub API failed')
        return json.loads(payload) if payload.strip() else None

    def upload(self, repo, release_id, path):
        # Names were checked against the fixed artifact set; no URL from API data.
        endpoint = f'https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={path.name}'
        result = subprocess.run(['gh', 'api', '--hostname', 'github.com', '--method', 'POST',
                                 endpoint, '-H', 'Content-Type: application/octet-stream',
                                 '--input', str(path)], capture_output=True, timeout=120)
        require(result.returncode == 0, 'Asset upload failed; retain draft for retry')
        return json.loads(result.stdout)

    def download_digest(self, repo, asset_id):
        import tempfile
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(['gh', 'api', '--hostname', 'github.com',
                                     f'repos/{repo}/releases/assets/{asset_id}',
                                     '-H', 'Accept: application/octet-stream'],
                                    stdout=output, stderr=subprocess.PIPE, timeout=120)
            require(result.returncode == 0, 'Asset download failed')
            size = output.tell()
            output.seek(0)
            digest = file_digest(output)
        return size, digest


def listing(api, endpoint):
    rows = []
    for page in range(1, 101):
        part = api.api('GET', f'{endpoint}?per_page=100&page={page}')
        require(isinstance(part, list), 'Invalid API list')
        rows.extend(part)
        if len(part) < 100:
            require(len({identifier(row['id']) for row in rows}) == len(rows), 'Duplicate API IDs')
            return rows
    raise ValueError('Incomplete API list')


def local_assets(directory, tag):
    names = {f'shoutx-{tag}-{target}.tar.gz' for target in (
        'x86_64-unknown-linux-musl', 'aarch64-unknown-linux-musl',
        'x86_64-apple-darwin', 'aarch64-apple-darwin')}
    names.add(f'shoutx-{tag}-x86_64-pc-windows-msvc.zip')
    require({p.name for p in directory.iterdir()} == names | {'SHA256SUMS'}, 'Unexpected local assets')
    result = {}
    for name in sorted(names | {'SHA256SUMS'}):
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'Invalid local asset')
        with path.open('rb') as source:
            digest = file_digest(source)
        result[name] = (path.stat().st_size, digest)
    expected = ''.join(f'{result[name][1]}  {name}\n' for name in sorted(names)).encode()
    require((directory / 'SHA256SUMS').read_bytes() == expected, 'Invalid checksum manifest')
    return result


def publish(api, env, directory, admission):
    repo, tag, sha = env['GITHUB_REPOSITORY'], env['TAG'], env['GITHUB_SHA']
    require(repo == 'send/shoutx', 'Unexpected repository')
    require(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?', tag) and len(tag) <= 56,
            'Invalid release tag')
    require(re.fullmatch(r'[a-f0-9]{40}', sha), 'Invalid source SHA')
    prerelease = '-' in tag
    require(env['PRERELEASE'] == str(prerelease).lower(), 'Prerelease mismatch')
    expected = local_assets(directory, tag)
    base = f'repos/{repo}/'

    def check_tag():
        obj = api.api('GET', base + f'git/ref/tags/{tag}')['object']
        for _ in range(8):
            if obj['type'] != 'tag':
                break
            obj = api.api('GET', base + f"git/tags/{obj['sha']}")['object']
        require(obj['type'] == 'commit' and obj['sha'] == sha, 'Tag no longer matches source')

    def matches():
        return [row for row in listing(api, base + 'releases') if row['tag_name'] == tag]

    def validate(row, release_id, draft):
        require(row['id'] == release_id and row['tag_name'] == tag and row['draft'] is draft,
                'Release identity/state changed')
        require(row['immutable'] is (not draft), 'Unexpected immutable state')

    check_tag()
    candidates = matches()
    require(len(candidates) <= 1, 'Multiple releases match tag; manual cleanup required')
    if candidates:
        selected = candidates[0]
        release_id = identifier(selected['id'])
        validate(selected, release_id, True)
    else:
        selected = api.api('POST', base + 'releases', {
            'tag_name': tag, 'target_commitish': sha, 'name': tag,
            'draft': True, 'prerelease': prerelease,
            'generate_release_notes': True, 'make_latest': 'false'})
        release_id = identifier(selected['id'])
        validate(selected, release_id, True)
    endpoint = base + f'releases/{release_id}'

    def check_draft():
        validate(api.api('GET', endpoint), release_id, True)

    def unique():
        rows = matches()
        require(len(rows) == 1 and rows[0]['id'] == release_id, 'Release selection is no longer unique')
        validate(rows[0], release_id, True)

    unique()
    check_tag()
    check_draft()
    for asset in listing(api, endpoint + '/assets'):
        check_draft()
        api.api('DELETE', base + f"releases/assets/{identifier(asset['id'])}")
    for name in expected:
        check_draft()
        asset = api.upload(repo, release_id, directory / name)
        identifier(asset['id'])
        require(asset['name'] == name and asset['state'] == 'uploaded', 'Unexpected uploaded asset')

    def verify_assets():
        assets = listing(api, endpoint + '/assets')
        require(len(assets) == len(expected) and {a['name'] for a in assets} == set(expected),
                'Unexpected remote assets')
        for asset in assets:
            require(asset['state'] == 'uploaded', 'Incomplete remote asset')
            require(api.download_digest(repo, identifier(asset['id'])) == expected[asset['name']],
                    'Remote asset bytes differ')

    check_draft()
    verify_assets()
    admission(sha)
    check_tag()
    if not prerelease:
        latest = api.api('GET', base + 'releases/latest', missing=True)
        if latest is not None:
            require(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', latest['tag_name']), 'Unsupported latest tag')
            version = lambda value: tuple(map(int, value[1:].split('.')))
            require(version(latest['tag_name']) <= version(tag), 'Refusing latest rollback')
    unique()
    check_draft()
    api.api('PATCH', endpoint, {'draft': False, 'prerelease': prerelease,
                                'make_latest': 'false' if prerelease else 'true'})
    published = api.api('GET', endpoint)
    validate(published, release_id, False)
    require(published['prerelease'] is prerelease, 'Published prerelease mismatch')
    check_tag()
    verify_assets()
    return release_id


def admission(sha):
    subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('check-stdout-release.py')),
                    '--sha', sha], check=True, timeout=180)


if __name__ == '__main__':
    try:
        release_id = publish(GitHub(), os.environ, Path('dist'), admission)
        print(f'Published and verified release ID {release_id}')
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        sys.exit('Release publication failed; inspect retained draft/state before retrying')
