import unittest

from PIL import Image, ImageDraw

from image_matting.core import erode_mask, remove_connected_white_background


class BackgroundRemovalTests(unittest.TestCase):
    def test_removes_border_white_but_preserves_protected_white_and_island(self) -> None:
        image = Image.new("RGBA", (11, 11), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((3, 3, 7, 7), fill=(200, 50, 50, 255))
        draw.point((5, 5), fill=(255, 255, 255, 255))
        draw.rectangle((1, 1, 1, 1), fill=(30, 80, 200, 255))

        protection = Image.new("L", image.size, 0)
        ImageDraw.Draw(protection).rectangle((4, 4, 6, 6), fill=255)
        result = remove_connected_white_background(image, protection)

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((5, 5))[3], 255)
        self.assertEqual(result.getpixel((1, 1))[3], 255)

    def test_erode_mask_reduces_subject_area(self) -> None:
        mask = Image.new("L", (9, 9), 0)
        ImageDraw.Draw(mask).rectangle((1, 1, 7, 7), fill=255)
        eroded = erode_mask(mask, 1)

        self.assertEqual(eroded.getpixel((1, 1)), 0)
        self.assertEqual(eroded.getpixel((2, 2)), 255)


if __name__ == "__main__":
    unittest.main()

