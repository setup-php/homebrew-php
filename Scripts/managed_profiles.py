"""Native host images and routing labels for the managed Homebrew pools."""
import re

from runner_pool import validate_host

TARGET = 'shivammathur/homebrew-php'
PROFILES = {
    'macos15': {
        'prefix': 'runner-pool-hb-macos15-', 'arch': 'arm64', 'platform': 'macos-15-arm64',
        'image': 'nscloud-macos-sequoia-stable-arm64-4x7',
        'labels': ('macos-15', 'macos-15-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
    'macos26': {
        'prefix': 'runner-pool-hb-macos26-', 'arch': 'arm64', 'platform': 'macos-26',
        'image': 'nscloud-macos-tahoe-arm64-4x7',
        'labels': ('macos-26', 'macos-26-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
    'xcode27': {
        'prefix': 'runner-pool-hb-xcode27-', 'arch': 'arm64', 'platform': 'xcode-27',
        'image': 'nscloud-macos-goldengate-arm64-4x7',
        'labels': ('xcode-27', 'macos-27', 'macos-27-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
}

# ubuntu-latest jobs use 24.04 x64. The two numbered labels must stay on
# Jammy even when a container supplies the build userland.
for key, image, label, platform, arch in (
    ('linux-x64', 'nscloud-ubuntu-24.04-amd64-4x8', 'ubuntu-latest', 'ubuntu-latest', 'x64'),
    ('linux22-x64', 'nscloud-ubuntu-22.04-amd64-4x8', 'ubuntu-22.04', 'ubuntu-22.04', 'x64'),
    ('linux-arm64', 'nscloud-ubuntu-22.04-arm64-4x8', 'ubuntu-22.04-arm', 'ubuntu-22.04', 'arm64'),
):
    PROFILES[key] = {
        'prefix': f'runner-pool-hb-{key}-', 'arch': arch, 'platform': platform,
        'image': image, 'labels': (label,), 'system': 'Linux',
        'workflow': 'managed-runner.yml', 'limit': 60,
    }


def capacity_group(key):
    profile = PROFILES[key]
    return 'macos' if profile['system'] == 'macOS' else profile['arch']


def identify(name):
    for key, profile in PROFILES.items():
        match = re.fullmatch(profile['prefix'] + r's([1-9][0-9]?)-[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', name)
        if match and int(match[1]) <= profile['limit']:
            return key, int(match[1])
    return None


def labels(key):
    profile = PROFILES[key]
    return ['self-hosted', profile['system'], 'X64' if profile['arch'] == 'x64' else 'ARM64', *profile['labels']]


def validate(key, system, machine, version):
    profile = PROFILES[key]
    validate_host(profile['platform'], profile['arch'], system, machine, version)
