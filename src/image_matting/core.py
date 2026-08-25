from __future__ import annotations

from collections import deque
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageFilter


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class MattingError(RuntimeError):
    """Raised when the external subject-mask step cannot complete."""


def _is_near_white(pixel: tuple[int, int, int, int], threshold: int, tolerance: int) -> bool:
    red, green, blue, _ = pixel
    return min(red, green, blue) >= threshold and max(red, green, blue) - min(red, green, blue) <= tolerance


def erode_mask(mask: Image.Image, radius: int) -> Image.Image:
    """Shrink a white-on-black subject mask by the requested pixel radius."""
    if radius < 0:
        raise ValueError("erode radius cannot be negative")
    if radius == 0:
        return mask.convert("L")
    return mask.convert("L").filter(ImageFilter.MinFilter(radius * 2 + 1))


def remove_connected_white_background(
    image: Image.Image,
    protected_mask: Image.Image,
    *,
    white_threshold: int = 245,
    white_tolerance: int = 18,
) -> Image.Image:
    """Make border-connected near-white pixels transparent.

    Pixels covered by the protected mask are excluded from the flood fill, so
    white details inside the detected subject remain opaque.
    """
    rgba = image.convert("RGBA")
    protection = protected_mask.convert("L")
    if rgba.size != protection.size:
        raise ValueError("image and protected mask must have the same dimensions")
    if not 0 <= white_threshold <= 255:
        raise ValueError("white threshold must be between 0 and 255")
    if not 0 <= white_tolerance <= 255:
        raise ValueError("white tolerance must be between 0 and 255")

    width, height = rgba.size
    pixels = rgba.load()
    protection_pixels = protection.load()
    candidate = bytearray(width * height)

    for y in range(height):
        row = y * width
        for x in range(width):
            index = row + x
            if protection_pixels[x, y] == 0 and _is_near_white(pixels[x, y], white_threshold, white_tolerance):
                candidate[index] = 1

    background = bytearray(width * height)
    queue: deque[int] = deque()

    for x in range(width):
        queue.extend((x, (height - 1) * width + x))
    for y in range(1, height - 1):
        queue.extend((y * width, y * width + width - 1))

    while queue:
        index = queue.popleft()
        if not candidate[index] or background[index]:
            continue
        background[index] = 1
        x = index % width
        y = index // width
        if x > 0:
            queue.append(index - 1)
        if x + 1 < width:
            queue.append(index + 1)
        if y > 0:
            queue.append(index - width)
        if y + 1 < height:
            queue.append(index + width)

    alpha = bytearray(rgba.getchannel("A").tobytes())
    for index, should_remove in enumerate(background):
        if should_remove:
            alpha[index] = 0

    result = rgba.copy()
    result.putalpha(Image.frombytes("L", rgba.size, bytes(alpha)))
    return result


def _subject_mask_from_output(matte_path: Path, expected_size: tuple[int, int]) -> Image.Image:
    with Image.open(matte_path) as matte:
        if matte.size != expected_size:
            raise MattingError(
                f"matte size {matte.size} does not match source size {expected_size}"
            )
        if "A" not in matte.getbands():
            raise MattingError("apple-matting-cli output does not contain an alpha channel")
        return matte.convert("RGBA").getchannel("A").copy()


def process_image(
    input_path: Path,
    output_path: Path,
    *,
    apple_cli: str = "apple-matting-cli",
    erode_radius: int = 5,
    white_threshold: int = 245,
    white_tolerance: int = 18,
) -> None:
    """Process one input image and write a transparent PNG."""
    executable = shutil.which(apple_cli) if "/" not in apple_cli else apple_cli
    if not executable:
        raise MattingError(f"cannot find subject-mask executable: {apple_cli}")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output must not overwrite the input image")

    with Image.open(input_path) as source:
        source_rgba = source.convert("RGBA")

    with tempfile.TemporaryDirectory(prefix="image-matting-") as temporary_dir:
        temporary = Path(temporary_dir)
        normalized_input = temporary / "input.png"
        matte_output = temporary / "matte.png"
        source_rgba.save(normalized_input, "PNG")
        command = [executable, str(normalized_input), "-o", str(matte_output)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise MattingError(f"subject-mask command failed: {details}")
        if not matte_output.exists():
            raise MattingError("subject-mask command completed without creating a matte")

        mask = _subject_mask_from_output(matte_output, source_rgba.size)
        protected = erode_mask(mask, erode_radius)
        result = remove_connected_white_background(
            source_rgba,
            protected,
            white_threshold=white_threshold,
            white_tolerance=white_tolerance,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "PNG")


def process_batch(
    input_dir: Path,
    output_dir: Path,
    **options: object,
) -> tuple[int, int]:
    """Process supported files in a directory, returning (successes, failures)."""
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    files = sorted(path for path in input_dir.iterdir() if path.suffix.lower() in SUPPORTED_SUFFIXES)
    successes = 0
    failures = 0
    for input_path in files:
        output_path = output_dir / f"{input_path.stem}.png"
        try:
            process_image(input_path, output_path, **options)
        except Exception as error:  # Keep processing the rest of a batch.
            failures += 1
            print(f"FAILED {input_path.name}: {error}")
        else:
            successes += 1
            print(f"OK     {input_path.name} -> {output_path}")
    return successes, failures

