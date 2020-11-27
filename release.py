#!/usr/bin/env python3

import argparse
import re
import subprocess
import shutil

from ledfx.consts import MAJOR_VERSION, MICRO_VERSION, MINOR_VERSION


def write_version(major, minor, micro):
    with open('ledfx/consts.py') as fil:
        content = fil.read()

    content = re.sub('MAJOR_VERSION = .*\n',
                     'MAJOR_VERSION = {}\n'.format(major),
                     content)
    content = re.sub('MINOR_VERSION = .*\n',
                     'MINOR_VERSION = {}\n'.format(minor),
                     content)
    content = re.sub('MICRO_VERSION = .*\n',
                     'MICRO_VERSION = {}\n'.format(micro),
                     content)

    with open('ledfx/consts.py', 'wt') as fil:
        content = fil.write(content)


def execute_command(command):
    return subprocess.check_output(command.split(' ')).decode('UTF-8').rstrip()


def main():
    parser = argparse.ArgumentParser(
        description="Release a new version of LedFx")
    parser.add_argument('type', help="The type of release",
                        choices=['major', 'minor', 'micro'])
    parser.add_argument('branch', help="Branch",
                        choices=['dev'])
    parser.add_argument('--no-bump', action='store_true',
                        help='Create a version bump commit.')

    arguments = parser.parse_args()

    branch = arguments.branch
    current_branch = execute_command("git rev-parse --abbrev-ref HEAD")
    if current_branch != "dev":  # Temporary sanity check
        print("Releases may only be pushed from the dev branch at this time.")
        if current_branch != "master":
            print("Releases must be pushed from the master branch.")
            return

    current_commit = execute_command("git rev-parse HEAD")
    # Push to dev branch only for now.
    branch_commit = execute_command("git rev-parse dev@{upstream}")
    if current_commit != branch_commit:
        print("Release must be pushed when up-to-date with origin.")
        return

    git_diff = execute_command("git diff HEAD")
    if git_diff:
        print("Release must be pushed without any staged changes.")
        return

    if not arguments.no_bump:
        # Bump the version based on the release type
        major = MAJOR_VERSION
        minor = MINOR_VERSION
        micro = MICRO_VERSION
        if arguments.type == 'major':
            major += 1
            minor = 0
            micro = 0
        elif arguments.type == 'minor':
            minor += 1
            micro = 0
        elif arguments.type == 'micro':
            micro += 1

        # Write the new version to consts.py
        write_version(major, minor, micro)

        subprocess.run(['git',
                        'commit',
                        '-am',
                        'Version Bump for Release {}.{}.{}'.format(major,
                                                                   minor,
                                                                   micro)])
        subprocess.run(['git', 'push', 'origin', branch])

    shutil.rmtree("dist", ignore_errors=True)
    subprocess.run(['python', 'setup.py', 'sdist', 'bdist_wheel'])
    subprocess.run(['python', '-m', 'twine', 'upload',
                    'dist/*', '--skip-existing'])


if __name__ == '__main__':
    main()
