from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts'))
from hosted_profiles import PREFIX, PROFILES, identify, labels, matching_profile, plan_launches
from runner_pool import validate_host


def name(key, slot):
    return f'{PREFIX}{key}-s{slot}-20261121-120000-aabbcc'


def job(ident, key):
    return {'id': ident, 'labels': labels(key), 'status': 'queued', 'runner_name': ''}


class HostedProfilesTests(unittest.TestCase):
    def test_total_and_macos_limits_leave_room_for_both_architectures(self):
        jobs = [job(i, 'linux-x64') for i in range(40)]
        jobs += [job(100 + i, 'linux-arm64') for i in range(40)]
        jobs += [job(200 + i, 'macos26') for i in range(10)]
        planned, _, deferred = plan_launches(set(), [], jobs)
        self.assertEqual(len(planned), 60)
        self.assertEqual(sum(PROFILES[key]['macos'] for key, _ in planned), 5)
        self.assertTrue(any(key == 'linux-arm64' for key, _ in planned))
        self.assertEqual(deferred['macos26'], 5)

    def test_running_reserved_and_idle_hosts_are_counted(self):
        protected = {name('macos15', n) for n in range(1, 6)}
        protected.add(name('linux-arm64', 1))
        runners = [{'name': n, 'status': 'online', 'busy': True, 'labels': []} for n in protected]
        planned, _, _ = plan_launches(protected, runners, [job(1, 'macos26'), job(2, 'linux-x64')], 7)
        self.assertEqual(planned, [('linux-x64', 1)])
        self.assertEqual(plan_launches({name('linux-arm64', 1)}, [], [job(1, 'linux-arm64')])[0], [])

    def test_existing_external_idle_runner_covers_one_job(self):
        runner = {'name': 'permanent', 'status': 'online', 'busy': False,
                  'labels': [{'name': label} for label in labels('macos15')]}
        self.assertEqual(plan_launches(set(), [runner], [job(1, 'macos15'), job(2, 'macos15')])[0], [('macos15', 1)])

    def test_empty_or_ambiguous_demand_does_not_launch(self):
        self.assertEqual(plan_launches(set(), [], [])[0], [])
        for requested in [[], ['self-hosted'], ['macOS'], ['ubuntu-22.04-arm', 'X64']]:
            self.assertIsNone(matching_profile({'labels': requested}))
        self.assertEqual(plan_launches(set(), [], [job(1, 'macos15')], 0, 0)[0], [])
        with self.assertRaises(ValueError):
            plan_launches(set(), [], [], 61)
        with self.assertRaises(ValueError):
            plan_launches(set(), [], [], 60, 6)

    def test_labels_preserve_native_os_and_architecture(self):
        for key, system, machine, version in [
            ('macos15', 'Darwin', 'arm64', '15.8.3'),
            ('macos26', 'Darwin', 'arm64', '26.7.3'),
            ('xcode27', 'Darwin', 'arm64', '27.2'),
            ('linux-x64', 'Linux', 'x86_64', '24.04'),
            ('linux22-x64', 'Linux', 'x86_64', '22.04'),
            ('linux-arm64', 'Linux', 'aarch64', '22.04'),
        ]:
            profile = PROFILES[key]
            self.assertEqual(identify(name(key, 60)), (key, 60))
            self.assertEqual(matching_profile(job(1, key)), key)
            validate_host(profile['platform'], profile['arch'], system, machine, version)
            with self.assertRaises(ValueError):
                validate_host(profile['platform'], profile['arch'], system, machine, '99.0')
        self.assertIsNone(identify(name('macos15', 61)))


if __name__ == '__main__':
    unittest.main()
