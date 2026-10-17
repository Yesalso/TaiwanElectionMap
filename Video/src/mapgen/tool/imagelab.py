#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imagelab.py —— 參數化的圖像處理實驗室。

從 _legacy_build_vote_map.py、_legacy_build_assets.py 搬遷並參數化而來。
提供：
- resize_rgba()       : 預乘 alpha 面積平均縮圖
- erase_bands()       : 擦除地圖標題列與圖例列（比例可由 meta.json 指定或自動偵測）
- circle_asset()      : 幾何切圓去背（市徽/黨徽/當選標誌）
- edge_report()       : 邊緣自檢（抓針孔、鋸齒、跑色）
"""

import os
import cv2
import numpy as np
from PIL import Image


# ===================== 通用工具 =====================

def load_rgba(path):
    """載入圖片為 RGBA numpy array (H, W, 4)，值域 0-255"""
    img = Image.open(path).convert("RGBA")
    return np.array(img)


def save_rgba(arr, path):
    """儲存 RGBA numpy array 為 PNG"""
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(path)


def bgr_to_rgba(bgr):
    """OpenCV BGR -> RGBA"""
    if bgr.shape[2] == 3:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    return cv2.cvtColor(bgr, cv2.COLOR_BGRA2RGBA)


# ===================== 1. 預乘 Alpha 面積平均縮圖 =====================

def resize_rgba(src, dst, max_width=None, max_height=None, max_side=None):
    """
    預乘 Alpha 面積平均縮圖（area interpolation），避免白邊/黑邊。
    
    Args:
        src: 來源檔案路徑
        dst: 目的檔案路徑
        max_width: 最大寬度
        max_height: 最大高度
        max_side: 最大邊長（若指定，等同 max_width=max_height=max_side）
    """
    img = load_rgba(src)
    h, w = img.shape[:2]
    
    if max_side:
        max_width = max_height = max_side
    
    if max_width and w > max_width:
        scale = max_width / w
        new_w, new_h = max_width, int(h * scale)
    elif max_height and h > max_height:
        scale = max_height / h
        new_w, new_h = int(w * scale), max_height
    else:
        save_rgba(img, dst)
        return
    
    # 預乘 alpha
    rgb = img[:, :, :3].astype(np.float32)
    alpha = img[:, :, 3:4].astype(np.float32) / 255.0
    premul = rgb * alpha
    
    # 分別縮放 RGB（預乘）與 Alpha
    premul_small = cv2.resize(premul, (new_w, new_h), interpolation=cv2.INTER_AREA)
    alpha_small = cv2.resize(alpha, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # 還原
    alpha_small = np.clip(alpha_small, 1e-6, 1.0)
    rgb_small = (premul_small / alpha_small).clip(0, 255).astype(np.uint8)
    alpha_small = (alpha_small * 255).astype(np.uint8)
    
    result = np.dstack([rgb_small, alpha_small])
    save_rgba(result, dst)
    print(f"  resize_rgba: {w}x{h} -> {new_w}x{new_h}  (saved to {dst})")


# ===================== 2. 擦除標題列/圖例列 =====================

def _detect_dark_band(img, scan_from_top=True, band_height_ratio=0.1):
    """
    偵測深色帶狀區域（標題列通常在右上、深色像素密度高）。
    回傳 (y_start, y_end) 相對座標 0-1。
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
    alpha = img[:, :, 3]
    
    # 只看右半邊
    right_half = gray[:, w//2:]
    right_alpha = alpha[:, w//2:]
    
    # 有效像素（非透明）
    valid = right_alpha > 128
    
    # 計算每列的深色像素密度（灰度 < 64 且非透明）
    dark_ratio = np.zeros(h)
    for y in range(h):
        row_valid = valid[y]
        if row_valid.any():
            dark_ratio[y] = (gray[y, w//2:][row_valid] < 64).mean()
    
    # 找連續高密度區段
    band_thresh = 0.3
    in_band = dark_ratio > band_thresh
    
    bands = []
    start = None
    for y, v in enumerate(in_band):
        if v and start is None:
            start = y
        elif not v and start is not None:
            bands.append((start, y))
            start = None
    if start is not None:
        bands.append((start, h))
    
    if not bands:
        return None
    
    # 取最長的帶
    longest = max(bands, key=lambda b: b[1] - b[0])
    y0, y1 = longest
    return (y0 / h, y1 / h)


def _detect_legend_band(img, scan_from_bottom=True, band_height_ratio=0.15):
    """
    偵測右下角圖例帶（有規則色塊）。
    回傳 (y_start, y_end) 相對座標 0-1。
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
    alpha = img[:, :, 3]
    
    # 看右側 40% 區域、底部 30% 區域
    x0 = int(w * 0.6)
    y0 = int(h * 0.7)
    roi = gray[y0:, x0:]
    roi_alpha = alpha[y0:, x0:]
    
    valid = roi_alpha > 128
    if not valid.any():
        return None
    
    # 找水平投影的週期性（色塊間距）
    h_proj = np.zeros(roi.shape[0])
    for y in range(roi.shape[0]):
        row = roi[y][valid[y]]
        if len(row) > 10:
            # 標準差大 = 有顏色變化 = 可能是色階
            h_proj[y] = row.std()
    
    # 找連續高變異區段
    threshold = np.percentile(h_proj[h_proj > 0], 70) if (h_proj > 0).any() else 0
    in_band = h_proj > threshold
    
    bands = []
    start = None
    for y, v in enumerate(in_band):
        if v and start is None:
            start = y
        elif not v and start is not None:
            bands.append((start, y))
            start = None
    if start is not None:
        bands.append((start, roi.shape[0]))
    
    if not bands:
        return None
    
    longest = max(bands, key=lambda b: b[1] - b[0])
    by0, by1 = longest
    return ((y0 + by0) / h, (y0 + by1) / h)


def erase_bands(src, dst, title_band=None, legend_band=None, auto_detect=True):
    """
    擦除地圖的標題列與圖例列（設為透明）。
    
    Args:
        src: 來源檔案
        dst: 目的檔案
        title_band: (top_ratio, bottom_ratio) 標題帶相對座標，None 表示自動偵測
        legend_band: (top_ratio, bottom_ratio) 圖例帶相對座標，None 表示自動偵測
        auto_detect: 是否自動偵測
    """
    img = load_rgba(src)
    h, w = img.shape[:2]
    
    if auto_detect:
        if title_band is None:
            title_band = _detect_dark_band(img, scan_from_top=True)
            if title_band:
                print(f"  偵測到標題帶：{title_band[0]:.3f}~{title_band[1]:.3f} ({int(title_band[0]*h)}~{int(title_band[1]*h)}px)")
        if legend_band is None:
            legend_band = _detect_legend_band(img)
            if legend_band:
                print(f"  偵測到圖例帶：{legend_band[0]:.3f}~{legend_band[1]:.3f} ({int(legend_band[0]*h)}~{int(legend_band[1]*h)}px)")
    
    # 預設值（相容舊版硬編碼比例）
    if title_band is None:
        title_band = (0.0, 0.08)  # 頂部 8%
    if legend_band is None:
        legend_band = (0.85, 1.0)  # 底部 15%
    
    # 擦除：將 alpha 設為 0
    for band_name, (yt, yb) in [("標題", title_band), ("圖例", legend_band)]:
        y0, y1 = int(yt * h), int(yb * h)
        y0 = max(0, y0)
        y1 = min(h, y1)
        if y1 > y0:
            img[y0:y1, :, 3] = 0
            print(f"  擦除{band_name}帶：{y0}~{y1}px")
    
    save_rgba(img, dst)


# ===================== 3. 幾何切圓去背 =====================

def circle_asset(src, dst, edge_fill="auto", output_size=None):
    """
    將方形圖片切成圓形（透明背景）。
    
    Args:
        src: 來源檔案
        dst: 目的檔案
        edge_fill: 邊緣填充色
            - "auto": 自動偵測圓周單一色並填補
            - (r, g, b): 指定 RGB
            - None: 不填補（保留原像素）
        output_size: 輸出尺寸 (w, h)，None 保持原大小
    """
    img = load_rgba(src)
    h, w = img.shape[:2]
    r = min(w, h) // 2
    cx, cy = w // 2, h // 2
    
    # 建立圓形遮罩
    y, x = np.ogrid[:h, :w]
    mask = (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2
    
    # 邊緣抗鋸齒：模糊遮罩邊緣
    mask_float = mask.astype(np.float32)
    mask_float = cv2.GaussianBlur(mask_float, (3, 3), 0.5)
    mask_float = np.clip(mask_float, 0, 1)
    
    # 套用遮罩
    result = img.copy()
    result[:, :, 3] = (result[:, :, 3] * mask_float).astype(np.uint8)
    
    # 邊緣填色
    if edge_fill:
        if edge_fill == "auto":
            # 偵測圓周像素的主要顏色
            ring_mask = ((x - cx) ** 2 + (y - cy) ** 2 >= (r - 2) ** 2) & \
                       ((x - cx) ** 2 + (y - cy) ** 2 <= r ** 2) & \
                       (img[:, :, 3] > 128)
            if ring_mask.any():
                edge_color = img[ring_mask][:, :3].mean(axis=0).astype(np.uint8)
                edge_fill = tuple(int(c) for c in edge_color)
            else:
                edge_fill = (255, 255, 255)
        
        # 在圓外 1-2 像素填入邊緣色（避免白暈）
        outer_ring = ((x - cx) ** 2 + (y - cy) ** 2 >= r ** 2) & \
                     ((x - cx) ** 2 + (y - cy) ** 2 <= (r + 2) ** 2)
        result[outer_ring, :3] = edge_fill
        result[outer_ring, 3] = 255
    
    # 裁切到正方形
    x0, x1 = cx - r, cx + r
    y0, y1 = cy - r, cy + r
    result = result[y0:y1, x0:x1]
    
    # 縮放
    if output_size:
        result_pil = Image.fromarray(result.astype(np.uint8), "RGBA")
        result_pil = result_pil.resize(output_size, Image.Resampling.LANCZOS)
        result = np.array(result_pil)
    
    save_rgba(result, dst)
    print(f"  circle_asset: {w}x{h} -> 圓形 {2*r}x{2*r}" + (f" -> {output_size}" if output_size else ""))


# ===================== 4. 邊緣自檢 =====================

def edge_report(src, sample_step=1):
    """
    檢查圖片邊緣品質：
    - 針孔：圓內 alpha 為 0 的孤立像素
    - 鋸齒：邊緣銳度不足
    - 跑色：邊緣像素顏色與內部差異過大
    
    回傳 dict，含各項指標。
    """
    img = load_rgba(src)
    h, w = img.shape[:2]
    alpha = img[:, :, 3]
    
    # 假設圖片已是圓形，找圓心半徑
    ys, xs = np.where(alpha > 128)
    if len(xs) == 0:
        return {"error": "無有效像素"}
    
    cx, cy = xs.mean(), ys.mean()
    r = min(xs.max() - cx, cx - xs.min(), ys.max() - cy, cy - ys.min())
    
    # 建立環狀採樣區
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    
    # 內環（距圓心 0.9r ~ 0.95r）
    inner_ring = (dist >= 0.9 * r) & (dist <= 0.95 * r) & (alpha > 128)
    # 外環（距圓心 1.0r ~ 1.05r）
    outer_ring = (dist >= 1.0 * r) & (dist <= 1.05 * r)
    
    report = {}
    
    # 1. 針孔檢查：內環 alpha 應全 > 200
    inner_alpha = alpha[inner_ring]
    if len(inner_alpha) > 0:
        pinholes = (inner_alpha < 200).sum()
        report["pinhole_count"] = int(pinholes)
        report["pinhole_ratio"] = pinholes / len(inner_alpha)
    else:
        report["pinhole_count"] = 0
        report["pinhole_ratio"] = 0
    
    # 2. 外環應全透明
    outer_alpha = alpha[outer_ring]
    if len(outer_alpha) > 0:
        leak = (outer_alpha > 10).sum()
        report["edge_leak_count"] = int(leak)
        report["edge_leak_ratio"] = leak / len(outer_alpha)
    else:
        report["edge_leak_count"] = 0
        report["edge_leak_ratio"] = 0
    
    # 3. 邊緣銳度：內外環 alpha 差值
    if len(inner_alpha) > 0 and len(outer_alpha) > 0:
        report["edge_sharpness"] = float(inner_alpha.mean() - outer_alpha.mean())
    else:
        report["edge_sharpness"] = 0
    
    # 4. 色彩一致性：內環顏色標準差
    inner_rgb = img[inner_ring][:, :3]
    if len(inner_rgb) > 0:
        report["color_std"] = float(inner_rgb.std())
    else:
        report["color_std"] = 0
    
    return report


# ===================== CLI =====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="imagelab - 圖像處理工具")
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    # resize
    p_resize = sub.add_parser("resize", help="預乘 Alpha 面積平均縮圖")
    p_resize.add_argument("src")
    p_resize.add_argument("dst")
    p_resize.add_argument("--max-width", type=int)
    p_resize.add_argument("--max-height", type=int)
    p_resize.add_argument("--max-side", type=int)
    
    # erase
    p_erase = sub.add_parser("erase", help="擦除標題/圖例帶")
    p_erase.add_argument("src")
    p_erase.add_argument("dst")
    p_erase.add_argument("--title", nargs=2, type=float, metavar=("TOP", "BOTTOM"),
                         help="標題帶比例 (如 0.0 0.08)")
    p_erase.add_argument("--legend", nargs=2, type=float, metavar=("TOP", "BOTTOM"),
                         help="圖例帶比例 (如 0.85 1.0)")
    p_erase.add_argument("--no-auto", action="store_true", help="停用自動偵測")
    
    # circle
    p_circle = sub.add_parser("circle", help="切圓去背")
    p_circle.add_argument("src")
    p_circle.add_argument("dst")
    p_circle.add_argument("--edge-fill", default="auto", help="邊緣填充色: auto/none/R,G,B")
    p_circle.add_argument("--size", nargs=2, type=int, metavar=("W", "H"))
    
    # edge-report
    p_edge = sub.add_parser("edge-report", help="邊緣品質檢查")
    p_edge.add_argument("src")
    
    args = parser.parse_args()
    
    if args.cmd == "resize":
        resize_rgba(args.src, args.dst, args.max_width, args.max_height, args.max_side)
    elif args.cmd == "erase":
        title = tuple(args.title) if args.title else None
        legend = tuple(args.legend) if args.legend else None
        erase_bands(args.src, args.dst, title, legend, not args.no_auto)
    elif args.cmd == "circle":
        edge_fill = args.edge_fill
        if edge_fill == "none":
            edge_fill = None
        elif edge_fill != "auto" and "," in edge_fill:
            edge_fill = tuple(map(int, edge_fill.split(",")))
        size = tuple(args.size) if args.size else None
        circle_asset(args.src, args.dst, edge_fill, size)
    elif args.cmd == "edge-report":
        report = edge_report(args.src)
        for k, v in report.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()