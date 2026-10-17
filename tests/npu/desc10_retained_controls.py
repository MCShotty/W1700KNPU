"""Run the existing eight full-size faults from a real captured caller prefix."""
import argparse
import json
from pathlib import Path

from raw_pair_retained import run_controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    result = run_controls(args.pair, args.snapshot, args.output, workers=args.workers)
    print(json.dumps(dict(passed=result['passed'], retained_DESC10_faults=len(result['cases']),
        full_request_count=512, diagnostic_prefix=True,
        fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False)), flush=True)


if __name__ == '__main__': main()
