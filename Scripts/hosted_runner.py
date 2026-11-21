"""Serve one PHP build on a disposable GitHub-hosted macOS or Linux VM."""
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile

from hosted_profiles import PROFILES, identify, labels
from managed_profiles import TARGET
from managed_runner import serve_job
from runner_pool import child_environment, download_runner, validate_host


def serve():
    os.umask(0o077)
    token = os.environ.pop('RUNNER_REGISTRATION_TOKEN')
    name = os.environ.pop('POOL')
    key = os.environ.pop('HOSTED_PROFILE')
    identity = identify(name)
    if identity is None or identity[0] != key or not re.fullmatch(r'[A-Za-z0-9_]+', token):
        raise ValueError('Invalid hosted runner configuration')
    profile = PROFILES[key]
    system = platform.system()
    version = platform.freedesktop_os_release()['VERSION_ID'] if system == 'Linux' else platform.mac_ver()[0]
    validate_host(profile['platform'], profile['arch'], system, platform.machine(), version)
    if key == 'xcode27':
        xcode = subprocess.check_output(['xcodebuild', '-version'], text=True)
        if not re.match(r'Xcode 27(?:\.|\s)', xcode):
            raise ValueError('Expected Xcode 27')
    print(f'Host verified: {system} {version}, {platform.machine()}.', flush=True)
    env = child_environment(os.environ)
    directory = Path(tempfile.mkdtemp(prefix='hosted-php-runner-', dir=os.environ['RUNNER_TEMP']))

    def interrupted(signum, frame):
        raise InterruptedError('Host workflow interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        download_runner(directory, profile['arch'], profile['platform'])
        with (directory / 'host.log').open('wb') as log:
            subprocess.run([
                './config.sh', '--unattended', '--ephemeral', '--url', f'https://github.com/{TARGET}',
                '--token', token, '--name', name, '--work', '_work',
                '--no-default-labels', '--labels', ','.join(labels(key)),
            ], cwd=directory, env=env, stdout=log, stderr=log, timeout=120, check=True)
            token = ''
            print(f'Registered ephemeral {key} runner for one job.', flush=True)
            serve_job(directory, env, log)
    finally:
        subprocess.run(['sudo', 'rm', '-rf', '--', str(directory)], check=False)


if __name__ == '__main__':
    try:
        serve()
    except BaseException as error:
        print(f'::error::Hosted runner failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
