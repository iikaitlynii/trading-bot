"""Use the browser installed by the pinned Playwright package, never a host default.

Canonical pixel tests run in the digest-pinned Ubuntu image in agent-ci.yml.
BROWSER_EXECUTABLE is an explicit diagnostic override; assertions still run.
"""
from importlib.metadata import version
import os

PLAYWRIGHT_VERSION = '1.62.0'


def launch_chromium(playwright):
    actual = version('playwright')
    if actual != PLAYWRIGHT_VERSION:
        raise RuntimeError(f'Playwright {actual} differs from {PLAYWRIGHT_VERSION}; install tests/browser-requirements.txt')
    options = {'args': ['--no-sandbox']}
    if os.environ.get('BROWSER_EXECUTABLE'):
        options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
    return playwright.chromium.launch(**options)
