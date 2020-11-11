#!/usr/bin/env python3

import argparse
import sys
import re
import subprocess
import shutil

from ledfx.consts import MAJOR_VERSION, MINOR_VERSION

def write_version(major, minor):
    with open('ledfx/consts.py') as fil:
        content = fil.read()

    content = re.sub('MAJOR_VERSION = .*\n',
                     'MAJOR_VERSION = {}\n'.format(major),
                     content)
    content = re.sub('MINOR_VERSION = .*\n',
                     'MINOR_VERSION = {}\n'.format(minor),
                     content)

    with open('ledfx/consts.py', 'wt') as fil:
        content = fil.write(content)

def execute_command(command):
    return subprocess.check_output(command.split(' ')).decode('UTF-8').rstrip()

def main():
    parser = argparse.ArgumentParser(
        description="Release a new version of LedFx")
    parser.add_argument('type', help="The type of release",
        choices=['major', 'minor'])
    parser.add_argument('branch', help="Branch",
        choices=['master', 'dev'])
    parser.add_argument('--no_bump', action='store_true',
        help='Create a version bump commit.')
    
    arguments = parser.parse_args()

    branch = execute_command("git rev-parse --abbrev-ref HEAD")
    if branch != "master":
        print("Releases must be pushed from the master branch.")
        return

    current_commit = execute_command("git rev-parse HEAD")
    master_commit = execute_command("git rev-parse master@{upstream}")
    if current_commit != master_commit:
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
        if arguments.type == 'major':
            major += 1
            minor = 0
        elif arguments.type == 'minor':
            minor += 1

        # Write the new version to consts.py
        write_version(major, minor)

        subprocess.run([
           'git', 'commit', '-am', 'Version Bump for Release {}.{}'.format(major, minor)])
        subprocess.run(['git', 'push', 'origin', 'master'])

    shutil.rmtree("dist", ignore_errors=True)
    subprocess.run(['python', 'setup.py', 'sdist', 'bdist_wheel'])
    subprocess.run(['python', '-m', 'twine', 'upload', 'dist/*', '--skip-existing'])


if __name__ == '__main__':
    main()
