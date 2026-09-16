# -*- coding: utf-8 -*-
"""將圖片中除了指定顏色（#7F7F7F / #323232 / #0066CC）以外的所有顏色改為 #7F7F7F。"""

from PIL import Image
import os


KEEP_COLORS = {
    (0x7F, 0x7F, 0x7F),   # #7F7F7F
    (0x32, 0x32, 0x32),   # #323232
    (0x00, 0x66, 0xCC),   # #0066CC
}
REPLACE_WITH = (0x7F, 0x7F, 0x7F)  # #7F7F7F


def convert_image(src, dst=None):
    if dst is None:
        base, ext = os.path.splitext(src)
        dst = f"{base}_converted{ext}"

    img = Image.open(src).convert("RGB")
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y][:3]
            if pixel not in KEEP_COLORS:
                pixels[x, y] = REPLACE_WITH

    img.save(dst)
    print(f"完成！已儲存至 '{dst}'")
    return dst


if __name__ == "__main__":
    src = r"C:\Users\Windows\Desktop\Data\1.png"
    convert_image(src)