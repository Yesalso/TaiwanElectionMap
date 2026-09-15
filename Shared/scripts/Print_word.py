# -*- coding: utf-8 -*-
"""
仿地图代码输出方式：生成纯黑文字、透明背景图片
使用 Matplotlib 绘制，OpenCV 二值化 + 透明度转换，无抗锯齿
字体：MingLiU（优先），字号30pt，黑色，居中
输出：C:/Users/Windows/Desktop/Output/1.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import cv2
from io import BytesIO

# ============ 配置 ============
out_path = r"C:\Users\Windows\Desktop\Output\13.png"
FONT_SIZE = 64         # 字号（点）
BINARY_THRESHOLD = 200  # 二值化阈值（与地图代码一致）
DPI = 100
LINE_SPACING_FACTOR = 1.5  # 行间距为字体大小的倍数
PADDING = 20            # 边距（点）
# ==============================

# 确保输出目录存在
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# ----- 文字内容（按行分割） -----
lines = [
    "第十一屆全國不分區及僑居國外國民立法委員選舉","在高雄市各村（里）得票領先之政黨得票比例圖"
]

# ----- 查找 MingLiU 字体（仿地图代码） -----
def find_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            return n
    return None

font_name = find_font()
print("使用字体：", font_name)

# ----- 计算每行文字尺寸 -----
fig_temp = plt.figure(figsize=(1, 1), dpi=DPI)
ax_temp = fig_temp.add_subplot(111)
ax_temp.axis('off')
# 需要先绘制一次以获取渲染器
fig_temp.canvas.draw()
renderer = fig_temp.canvas.get_renderer()

line_widths = []
line_heights = []
max_width = 0
for line in lines:
    t = ax_temp.text(0, 0, line, fontsize=FONT_SIZE, fontfamily=font_name)
    bbox = t.get_window_extent(renderer=renderer)
    w = bbox.width
    h = bbox.height
    line_widths.append(w)
    line_heights.append(h)
    if w > max_width:
        max_width = w
plt.close(fig_temp)

# 计算总高度：行高 + 行间距
line_spacing = FONT_SIZE * LINE_SPACING_FACTOR
total_height = sum(line_heights) + (len(lines)-1) * line_spacing

# 确定画布尺寸（点）
fig_width_pt = max_width + 2 * PADDING
fig_height_pt = total_height + 2 * PADDING

# 转换为英寸
fig_width_in = fig_width_pt / DPI
fig_height_in = fig_height_pt / DPI

# 创建实际图形（白色背景）
fig = plt.figure(figsize=(fig_width_in, fig_height_in), dpi=DPI, facecolor='white')
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, fig_width_pt)
ax.set_ylim(0, fig_height_pt)
ax.set_facecolor('white')
ax.axis('off')

# 绘制文字（黑色，居中）
y = PADDING + total_height  # 从底部向上绘制
for i, line in enumerate(lines):
    width = line_widths[i]
    height = line_heights[i]
    x = (fig_width_pt - width) / 2
    y -= height  # 先减高度
    ax.text(x, y, line, fontsize=FONT_SIZE, ha='left', va='bottom',
            fontfamily=font_name, color='black')
    y -= line_spacing  # 再减行间距

# ----- 保存为内存 PNG -----
buf = BytesIO()
plt.savefig(buf, format='png', dpi=DPI, facecolor='white', pad_inches=0)
plt.close(fig)
buf.seek(0)

# ----- 二值化 -----
# 读取为灰度图
img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
# 二值化：白色(255)背景，黑色(0)文字
_, bin_img = cv2.threshold(img, BINARY_THRESHOLD, 255, cv2.THRESH_BINARY)

# ----- 将白色背景转为透明 -----
# 创建四通道图像（BGRA），文字为黑色，背景透明
height, width = bin_img.shape
result = np.zeros((height, width, 4), dtype=np.uint8)
# 文字为黑色（B=0, G=0, R=0）
result[:, :, 0] = 0  # B
result[:, :, 1] = 0  # G
result[:, :, 2] = 0  # R
# Alpha通道：白色（背景）->0透明，黑色（文字）->255不透明
alpha = np.where(bin_img == 255, 0, 255).astype(np.uint8)
result[:, :, 3] = alpha

# 保存为PNG（保留透明度）
cv2.imwrite(out_path, result, [cv2.IMWRITE_PNG_COMPRESSION, 9])

print(f"✅ 图片已保存至：{out_path}")