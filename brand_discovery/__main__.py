import argparse
import os
from pathlib import Path
from .collector import run, validate_private_root

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--private-root', required=True)
    p.add_argument('--limit', type=int, default=30)
    p.add_argument('--seconds', type=int, default=1800)
    args = p.parse_args()
    # Only the owner-reviewed bounded manual project build may collect in Actions.
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('LAYER_APPROVED_DATA_BUILD') != 'true':
        p.error('Collection requires explicit approved project data-build mode.')
    if not 1 <= args.limit <= 500 or not 1 <= args.seconds <= 14400:
        p.error('Limit must be 1..500 and seconds 1..14400.')
    os.umask(0o077)
    try:
        root = validate_private_root(args.private_root, Path(__file__).resolve().parents[1])
        run(root, args.limit, args.seconds)
    except Exception:
        # No paths, names, URLs, response bodies or exception detail to console.
        raise SystemExit('Collection stopped. Inspect private inputs/checkpoints locally.')

if __name__ == '__main__':
    main()
