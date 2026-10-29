# -*- coding: utf-8 -*-
"""
2022 縣市長配樂影片質檢。

檢查：
  1. 容器時長、解析度、fps、編碼；
  2. 片頭前 3 秒是否為數位靜音；
  3. 3 秒後的音樂是否與源 MP3 對位；
  4. 23 段中點抽幀與源 PNG 的 SSIM（確認順序）。

用法:
  python verify_2022_county_video.py
  python verify_2022_county_video.py --video path/to/video.mp4
"""
import argparse
import os
import re
import subprocess
import sys

import numpy as np

import imageio_ffmpeg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_2022_county_video as m

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 8000


def pcm(path, start=0.0, length=30.0):
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(start),
         "-t", str(length), "-i", path, "-vn", "-ac", "1", "-ar", str(SR),
         "-f", "f32le", "-"],
        capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def stream_info(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    text = r.stderr
    duration = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    video = re.search(r"Video:\s*([^,]+).*?(\d+)x(\d+).*?([\d.]+) fps", text)
    audio = re.search(r"Audio:\s*([^,]+).*?(\d+) Hz,\s*([^,]+)", text)
    return duration, video, audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(
        m.OUT_DIR, "2022縣市長選舉_3840x2160_配樂版.mp4"))
    ap.add_argument("--skip-ssim", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        sys.exit(f"找不到成片: {args.video}")

    ok = True
    duration, video, audio = stream_info(args.video)
    print("檔案:", args.video)
    print("容器時長:", "%.3f s" % (
        int(duration.group(1)) * 3600 + int(duration.group(2)) * 60
        + float(duration.group(3))) if duration else "?")
    print("影像:", video.groups() if video else "?")
    print("音訊:", audio.groups() if audio else "?")
    print("預期畫面: %d 幀 / %.2f s, %dx%d, %dfps"
          % (m.total_frames(), m.total_duration(), m.W, m.H, m.FPS))

    intro = pcm(args.video, 0, max(m.INTRO_SILENCE - 0.05, 0))
    peak = float(np.max(np.abs(intro))) if len(intro) else 0.0
    print("片頭最大振幅: %.8f (%s)" % (peak, "PASS" if peak < 1e-5 else "FAIL"))
    ok &= peak < 1e-5

    a = pcm(args.video, m.INTRO_SILENCE, 30)
    b = pcm(m.MUSIC, 0, 30)
    n = min(len(a), len(b))
    best = None
    for lag in range(-800, 801):
        x, y = (a[lag:n], b[:n - lag]) if lag >= 0 else (a[:n + lag], b[-lag:n])
        c = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-12))
        if best is None or c > best[1]:
            best = (lag, c)
    print("音樂起點: 偏移 %.1f ms, 相關 %.6f (%s)"
          % (best[0] / SR * 1000, best[1], "PASS" if best[1] > 0.99 else "FAIL"))
    ok &= best[1] > 0.99

    if not args.skip_ssim:
        offsets = [m.xfade_offset(k) for k in range(1, len(m.SEGMENTS))]
        worst = 1.0
        for i, (label, img, _d) in enumerate(m.SEGMENTS):
            start = 0.0 if i == 0 else offsets[i - 1] + m.FADE
            end = m.total_duration() if i == len(m.SEGMENTS) - 1 else offsets[i]
            t = (start + end) / 2
            # 直接解碼成片與源 PNG 比對；不要先存 PNG，避免多一次色彩範圍轉換。
            r = subprocess.run(
                [FFMPEG, "-hide_banner", "-nostats", "-ss", f"{t:.3f}",
                 "-i", args.video, "-i", os.path.join(m.IMG_DIR, img),
                 "-lavfi",
                 "[0:v]scale=640:360[a];[1:v]scale=640:360[b];[a][b]ssim",
                 "-frames:v", "1", "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace")
            mm = re.search(r"All:([\d.]+)", r.stderr)
            score = float(mm.group(1)) if mm else 0.0
            worst = min(worst, score)
            print("  %02d %-4s t=%7.3f SSIM=%.4f %s"
                  % (i + 1, label, t, score, "PASS" if score > 0.98 else "FAIL"))
            ok &= score > 0.98
        print("最低 SSIM: %.4f" % worst)

    print("結果:", "全部通過" if ok else "有項目未通過")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
