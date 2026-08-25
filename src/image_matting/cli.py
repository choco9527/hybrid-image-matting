from __future__ import annotations

import argparse
from pathlib import Path

from .core import MattingError, process_batch, process_image


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid Apple-mask and Pillow image matting")
    parser.add_argument("input", type=Path, help="input image or directory")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output PNG or directory")
    parser.add_argument("--batch", action="store_true", help="process supported images in input directory")
    parser.add_argument("--apple-cli", default="apple-matting-cli", help="subject-mask executable")
    parser.add_argument("--erode-radius", type=int, default=5, help="subject-mask erosion radius in pixels")
    parser.add_argument("--white-threshold", type=int, default=245, help="minimum RGB value for white background")
    parser.add_argument("--white-tolerance", type=int, default=18, help="maximum RGB channel spread for white")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    options = {
        "apple_cli": args.apple_cli,
        "erode_radius": args.erode_radius,
        "white_threshold": args.white_threshold,
        "white_tolerance": args.white_tolerance,
    }
    try:
        if args.batch:
            successes, failures = process_batch(args.input, args.output, **options)
            print(f"Processed {successes} image(s); {failures} failure(s)")
            raise SystemExit(1 if failures else 0)
        process_image(args.input, args.output, **options)
        print(f"OK {args.output}")
    except (FileNotFoundError, NotADirectoryError, MattingError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}") from error

