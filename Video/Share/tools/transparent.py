"""
将 PNG 图片中的纯白色部分变为透明
依赖: pip install pillow numpy
"""

import numpy as np
from PIL import Image


def white_to_transparent(input_path: str,
                         output_path: str,
                         threshold: int = 250) -> None:
    """
    把图片中接近纯白的像素设为全透明。

    :param input_path:  输入图片路径
    :param output_path: 输出 PNG 路径
    :param threshold:   阈值 (0-255)。RGB 三个通道都 >= 该值时视为白色。
                        255 表示只处理纯白，250 可以容忍轻微噪点/压缩痕迹。
    """
    # 1. 打开并转成带透明通道的 RGBA 模式
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)          # shape: (H, W, 4)

    rgb = arr[:, :, :3]          # R, G, B

    # 2. 找出"白色"像素：三个通道都 >= threshold
    white_mask = np.all(rgb >= threshold, axis=-1)

    # 3. 把这些像素的 alpha 设为 0（完全透明）
    arr[white_mask, 3] = 0

    # 4. 保存（PNG 支持透明通道）
    Image.fromarray(arr, mode="RGBA").save(output_path, "PNG")
    print(f"完成: {output_path}  共处理 {white_mask.sum()} 个白色像素")


if __name__ == "__main__":
    white_to_transparent("input.png", "output.png", threshold=250)