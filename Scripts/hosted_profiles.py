"""GitHub-hosted images that match the Homebrew job's native baseline."""
import re

from runner_pool import runner_labels

PROFILES = {
    'macos15': {'image': 'macos-15', 'platform': 'macos-15-arm64', 'arch': 'arm64', 'macos': True},
    'macos26': {'image': 'macos-26', 'platform': 'macos-26', 'arch': 'arm64', 'macos': True},
    'xcode27': {'image': 'xcode-27', 'platform': 'xcode-27', 'arch': 'arm64', 'macos': True},
    'linux-x64': {'image': 'ubuntu-24.04', 'platform': 'ubuntu-latest', 'arch': 'x64', 'macos': False},
    'linux-arm64': {'image': 'ubuntu-22.04-arm', 'platform': 'ubuntu-22.04', 'arch': 'arm64', 'macos': False},
}
PREFIX = 'runner-pool-gh-php-'


def identify(name):
    for key in PROFILES:
        match = re.fullmatch(re.escape(PREFIX + key) + r'-s([1-9][0-9]?)-[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', name)
        if match and int(match[1]) <= 60:
            return key, int(match[1])
    return None


def labels(key):
    profile = PROFILES[key]
    result = runner_labels(profile['platform'], profile['arch'])
    if key == 'macos15':
        result.append('macos-15')
    return result


def matching_profile(job):
    requested = {label.lower() for label in job.get('labels', [])}
    matches = [key for key in PROFILES if requested and requested <= {label.lower() for label in labels(key)}]
    return matches[0] if len(matches) == 1 else None


def plan_launches(protected, runners, jobs, capacity=60, macos_capacity=5):
    if not 0 <= capacity <= 60 or not 0 <= macos_capacity <= 5:
        raise ValueError('Hosted capacity must fit the 60 total / 5 macOS limits')
    registered = {r['name']: r for r in runners}
    consumed = {j.get('runner_name') for j in jobs if j['status'] != 'queued'}
    occupied = {key: set() for key in PROFILES}
    waiting = []
    for name in protected:
        key, slot = identify(name)
        occupied[key].add(slot)
        if name not in consumed and not registered.get(name, {}).get('busy', False):
            waiting.append({label.lower() for label in labels(key)})
    for runner in runners:
        if not identify(runner['name']) and runner['status'] == 'online' and not runner['busy']:
            waiting.append({label['name'].lower() for label in runner['labels']})
    total = len(protected)
    macos = sum(PROFILES[identify(name)[0]]['macos'] for name in protected)
    planned = []
    queued = {key: 0 for key in PROFILES}
    deferred = dict(queued)
    # Reserve macOS capacity before Linux fills the shared total allowance.
    candidates = [j for j in {j['id']: j for j in jobs}.values()
                  if j['status'] == 'queued' and not j.get('runner_name') and matching_profile(j)]
    candidates.sort(key=lambda j: (not PROFILES[matching_profile(j)]['macos'], j.get('created_at') or '', j['id']))
    for job in candidates:
        key = matching_profile(job)
        queued[key] += 1
        requested = {label.lower() for label in job['labels']}
        available = next((i for i, host in enumerate(waiting) if requested <= host), None)
        if available is not None:
            waiting.pop(available)
            continue
        is_macos = PROFILES[key]['macos']
        if total >= capacity or (is_macos and macos >= macos_capacity):
            deferred[key] += 1
            continue
        slot = next(n for n in range(1, 61) if n not in occupied[key])
        occupied[key].add(slot)
        planned.append((key, slot))
        total += 1
        macos += is_macos
    return planned, queued, deferred
