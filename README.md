# Hybrid Image Matting

This project turns the current white-background illustration workflow into a
standalone command-line tool:

1. Normalize JPG input to PNG with Pillow.
2. Ask `apple-matting-cli` for a subject mask.
3. Erode the subject mask to reduce white matte around the outline.
4. Detect near-white pixels connected to the image border.
5. Remove only those pixels from the alpha channel.
6. Write an RGBA PNG without changing the source image.

The protection mask is the important part: white areas inside the protected
subject, such as a cat's belly or face, are kept. Colored decorations are also
kept because they are not classified as white background.

## Requirements

- macOS with `apple-matting-cli` available on `PATH`
- Python 3.11 or newer
- Pillow

The current Apple Vision backend is macOS-specific. The Python processing
layer can be reused on other platforms if another tool supplies a subject
mask.

## Install

Use the dedicated environment created for this workflow:

```bash
source /Users/choco/Documents/Codex/venvs/image-matting/bin/activate
cd /Volumes/Apple/WORK/my-project/image-matting
python -m pip install Pillow setuptools
python -m pip install -e .
```

## Usage

Process one image:

```bash
image-matting input.jpg -o output.png
```

Process a directory:

```bash
image-matting --batch ./input -o ./output
```

Useful tuning parameters:

```bash
image-matting input.jpg -o output.png \
  --erode-radius 5 \
  --white-threshold 245 \
  --white-tolerance 18
```

The default values are tuned for the current scanned/illustrated cat images.
They should be validated on a representative set before processing a new art
style.

If `apple-matting-cli` reports `Vision request failed`, the external Apple
Vision subject-mask step did not produce a mask. The Pillow background-removal
step cannot infer a subject mask by itself; fix the Apple CLI input/runtime or
provide a different mask-producing backend before processing the image.

## Tests

```bash
python -m unittest discover -s tests -v
```
