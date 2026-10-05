#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 PNG 图片中的纯白像素改为透明 —— 地图 / 图例透明化的唯一实现。

依赖：
    pip install pillow numpy

这是一支低阶实现档，**没有 CLI**。唯一的调用方是
`NewSolution/tool/build_assets.py` 的 `build_white()`（threshold=12）。
要整批转档请用：

    python tool/build_assets.py --kind map --force

成品一律写进 `NewSolution/png/processed/`，不回写 `png/` 的原图。

★ 前提（改绘图参数前务必看一眼）：本判准是「逐通道区间」——
  三条通道都 >= 255 - threshold 才算白。它对
  `Converge_to_map_taipei.py` 的产物是精确的：四层绘图全部
  `antialiased=False`，画面里除了精确的 (255,255,255) 没有任何近白像素，
  所以 threshold 0 / 12 / 30 的遮罩实测完全相同。
  一旦栅格出现近白混色（有人打开抗锯齿、改 DPI 或换 matplotlib 版本），
  这条逐通道门槛会比欧氏距离「宽」（threshold 12 可吃到欧氏 20.8），
  可能开始侵蚀 `#EAF6FF` 这类最浅的填色档，而且肉眼几乎看不出来。
  动过绘图参数就重跑 build_assets 并比对 processed/ 的 md5。
"""

import numpy as np
from PIL import Image


def white_to_transparent(input_path: str,
                         output_path: str,
                         threshold: int = 0) -> None:
    """
    将图片中的白色像素设置为透明。
    :param input_path:  输入 PNG 路径
    :param output_path: 输出 PNG 路径
    :param threshold:   容差 (0~255)。0 表示只处理精确的纯白 (255,255,255)；
                        例如设为 10，则 RGB 都 >= 245 的像素也会变透明。
    """
    # 1. 打开并统一转为 RGBA（保证有 alpha 通道）
    img = Image.open(input_path).convert("RGBA")
    # 2. 转成 numpy 数组，形状 (H, W, 4)
    data = np.array(img)
    r, g, b, a = data[..., 0], data[..., 1], data[..., 2], data[..., 3]
    # 3. 找出“白色”像素的掩码
    limit = 255 - threshold
    white_mask = (r >= limit) & (g >= limit) & (b >= limit)
    # 4. 把这些像素的 alpha 设为 0
    data[..., 3] = np.where(white_mask, 0, a)
    # 5. 保存为 PNG（PNG 才支持透明通道）
    #    optimize=True 只是压缩旗标、不改任何像素：不加的话 2022 的 map.png
    #    会从 148.0 KB 涨到 159.3 KB（+7.6%），加了才与既有成品位元组相同。
    Image.fromarray(data, mode="RGBA").save(output_path, "PNG", optimize=True)
    print(f"完成：{white_mask.sum()} 个像素已变为透明 -> {output_path}")


if __name__ == "__main__":
    white_to_transparent("input.png", "output.png", threshold=0)
