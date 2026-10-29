# -*- coding: utf-8 -*-
"""
把 dist/final/2022 的 23 张县市长选举地图 PNG + 指定 MP3 合成 4K MP4。
（直接用现成看板 PNG，不重新渲染/构建；旧版从 dist/dist_png/2022 取图，可用 --img-dir 指回去。）

时间轴：
  1. 按「全国 + 22 县市」指定顺序展示，7 张重点图停留 16.0s，
     其余 15 张停留 9.5s，最后一张（连江县）10.17s；
  2. 最前面额外加 3.0s 开场：画面停在全国图，声音完全静音；
  3. 画面转场默认用 0.5s「淡黑转场」（fadeblack），不会让两张地图的文字
     在交叉淡化时叠在一起；时间轴按 24fps 帧对齐，避免累计漂移；
  4. 音乐从第 3.0s 开始，单轨播完，3.0s 处 0.5s 淡入、结尾 2s 淡出。

用法:
  python make_2022_county_video.py
  python make_2022_county_video.py --transition fade     # 改回直接交叉淡化
  python make_2022_county_video.py --crf 18 --name xxx.mp4
  python make_2022_county_video.py --no-music
"""
import argparse
import os
import shutil
import subprocess
import sys

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

VIDEO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../Video（本檔在 src/tools/）
IMG_DIR = os.path.join(VIDEO_ROOT, "dist", "final", "2022")  # 直接使用现成看板 PNG，不重新构建
OUT_DIR = os.path.join(VIDEO_ROOT, "dist", "final", "2022")
MUSIC = os.path.join(VIDEO_ROOT, "(演唱版)蔡小虎-愛人醉落去(DIY卡拉OK字幕)_mp3.mp3")

W, H = 3840, 2160
FPS = 24
FADE = 0.5        # 转场时长
TRANSITION = "fadeblack"  # 淡黑转场：地图文字不会叠在一起；可改 fade 直接交叉淡化
INTRO_SILENCE = 3.0       # 片头静音秒数（画面先停在全国图）
VIDEO_FADE_IN = 0.5       # 画面从黑场淡入
TAIL_OUT = 2.0            # 全片音乐结尾淡出
HEAD_IN = 0.5             # 音乐开始后的淡入

# 顺序即播放顺序：(标签, 图片文件名, 停留秒数)
# 7 张重点图 = 全国、台北、新北、桃园、台中、高雄、台南，各 16.0s；
# 其余 15 张 9.5s；最后一张连江县 10.17s。
# 另加 3.0s 片头静音，成片约 256.67s（歌曲 253.65s + 3s 开场）。
SEGMENTS = [
    ("全国", "全國.png", 16.0),
    ("台北市", "臺北市.png", 16.0),
    ("新北市", "新北市.png", 16.0),
    ("基隆市", "基隆市.png", 9.5),
    ("宜兰县", "宜蘭縣.png", 9.5),
    ("桃园市", "桃園市.png", 16.0),
    ("新竹县", "新竹縣.png", 9.5),
    ("新竹市", "新竹市.png", 9.5),
    ("苗栗县", "苗栗縣.png", 9.5),
    ("台中市", "臺中市.png", 16.0),
    ("彰化县", "彰化縣.png", 9.5),
    ("南投县", "南投縣.png", 9.5),
    ("云林县", "雲林縣.png", 9.5),
    ("嘉义县", "嘉義縣.png", 9.5),
    ("嘉义市", "嘉義市.png", 9.5),
    ("台南市", "臺南市.png", 16.0),
    ("高雄市", "高雄市.png", 16.0),
    ("屏东县", "屏東縣.png", 9.5),
    ("花莲县", "花蓮縣.png", 9.5),
    ("台东县", "臺東縣.png", 9.5),
    ("澎湖县", "澎湖縣.png", 9.5),
    ("金门县", "金門縣.png", 9.5),
    ("连江县", "連江縣.png", 10.17),
]


def segment_frames():
    """各图实际输入帧数；第一张额外加上片头静音停留。"""
    frames = [int(round(d * FPS)) for _l, _i, d in SEGMENTS]
    frames[0] += int(round(INTRO_SILENCE * FPS))
    return frames


def fade_frames():
    return int(round(FADE * FPS))


def total_frames():
    """成片总帧数 = 各图输入帧数和 - 转场重叠帧数。"""
    return sum(segment_frames()) - fade_frames() * (len(SEGMENTS) - 1)


def total_duration():
    return round(total_frames() / FPS, 4)


def xfade_offset(k):
    """第 k 个转场（1-based）在输出时间轴上的起点（秒，帧对齐）。"""
    frames = sum(segment_frames()[:k]) - k * fade_frames()
    return frames / FPS


def build_filter(n, total, with_music, transition):
    parts = []
    for i in range(n):
        parts.append(
            f"[{i}:v]scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS},"
            f"format=yuv420p[f{i}]"
        )

    prev = "f0"
    for k in range(1, n):
        out = f"x{k}" if k < n - 1 else "vx"
        parts.append(
            f"[{prev}][f{k}]xfade=transition={transition}:"
            f"duration={fade_frames() / FPS:.4f}:"
            f"offset={xfade_offset(k):.4f}[{out}]"
        )
        prev = out

    # 片头从黑场淡入；片头静音期间画面仍停在全国图。
    parts.append(f"[{prev}]fade=t=in:st=0:d={VIDEO_FADE_IN}[vout]")

    alabel = None
    if with_music:
        music_len = round(total - INTRO_SILENCE, 4)
        delay_ms = int(round(INTRO_SILENCE * 1000))
        parts.append(
            f"[{n}:a]aformat=sample_rates=48000:sample_fmts=fltp:"
            f"channel_layouts=stereo,asetpts=PTS-STARTPTS,"
            f"atrim=0:{music_len:.4f},asetpts=PTS-STARTPTS,"
            f"adelay={delay_ms}|{delay_ms}:all=1,"
            f"afade=t=in:st={INTRO_SILENCE:.4f}:d={HEAD_IN},"
            f"afade=t=out:st={max(total - TAIL_OUT, 0):.4f}:d={TAIL_OUT},"
            f"alimiter=limit=0.891:attack=5:release=50[afin]"
        )
        alabel = "afin"
    return ";".join(parts), alabel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--img-dir", default=IMG_DIR,
                    help="看板 PNG 目录，默认 dist/final/2022（直接使用现成图片）")
    ap.add_argument("--name", default="2022縣市長選舉_3840x2160_配樂版.mp4")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow",
                    help="x264 编码预设，越慢同 crf 画质越好（veryfast/fast/medium/slow/slower）")
    ap.add_argument("--tune", default="stillimage",
                    help="x264 tune，静止看板图用 stillimage；不需要则传 none")
    ap.add_argument("--transition", default=TRANSITION,
                    help="xfade 转场类型，默认 fadeblack（淡黑）；可用 fade、fadewhite 等")
    ap.add_argument("--no-music", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    img_dir = args.img_dir
    raw = os.path.join(args.out, "_raw_tmp.mp4")
    n = len(SEGMENTS)
    frames = segment_frames()
    total = total_duration()

    for label, img_name, _d in SEGMENTS:
        img = os.path.join(img_dir, img_name)
        if not os.path.isfile(img):
            sys.exit(f"缺图: {img}")
    if not args.no_music and not os.path.isfile(MUSIC):
        sys.exit(f"缺音乐: {MUSIC}")

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-stats"]
    for (_label, img_name, _dur), nframes in zip(SEGMENTS, frames):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{nframes / FPS:.4f}",
                "-i", os.path.join(img_dir, img_name)]
    if not args.no_music:
        cmd += ["-i", MUSIC]

    fc, alabel = build_filter(n, total, not args.no_music, args.transition)
    cmd += ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", args.preset]
    if args.tune and args.tune != "none":
        cmd += ["-tune", args.tune]
    cmd += ["-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart"]
    if alabel:
        cmd += ["-map", f"[{alabel}]", "-c:a", "aac", "-b:a", "192k"]
    cmd.append(raw)

    print("片头静音 %.1f 秒；画面总时长 %.2f 秒 (%d:%05.2f)；转场 %s / %.2fs"
          % (INTRO_SILENCE, total, total // 60, total % 60, args.transition, FADE))
    subprocess.run(cmd, check=True)

    dst = os.path.join(args.out, args.name)
    shutil.move(raw, dst)
    print("完成:", dst, "%.1f MB" % (os.path.getsize(dst) / 1048576))


if __name__ == "__main__":
    main()
