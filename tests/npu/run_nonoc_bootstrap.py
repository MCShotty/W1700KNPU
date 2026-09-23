#!/usr/bin/env python3
"""Revalidate integrated firmware sources without overwriting old receipts."""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import test_bootstrap_control_v2 as boot

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.local/merge-nonoc-20260923/firmware-tests'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['bootstrap', 'composition'])
    parser.add_argument('--resume-build', action='store_true')
    args = parser.parse_args()
    boot.BUILD = WORK / 'bootstrap-build'
    boot.control.BUILD = WORK / 'control-regression-build'
    boot.OUT = WORK / 'bootstrap-results'
    if args.suite == 'bootstrap':
        assert (args.resume_build or not boot.BUILD.exists()) and not boot.OUT.exists()
        boot.main()
    else:
        import test_bootstrap_v2_composition as composition
        composition.BUILD = WORK / 'composition-build'
        composition.OUT = WORK / 'composition-results'
        assert not composition.BUILD.exists() and not composition.OUT.exists()
        assert (boot.OUT / 'bootstrap-control-v2.json').is_file()
        sys.argv = [sys.argv[0]]
        composition.main()


if __name__ == '__main__':
    main()
