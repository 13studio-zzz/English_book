"""영어단어책 스캔본 색상 분리 전처리.

HSV 색 공간에서 어두운 녹색 픽셀을 식별하여 흰색으로 치환한다.
입력 디렉토리의 모든 PNG (또는 --only로 특정 파일)를 처리.

검증된 파라미터:
- Hue: 80° ~ 170° (어두운 녹색 ~ 청록)
- Saturation: >= 0.15 (회색 텍스트 제외)
- Value: < 0.7 (밝은 배경 제외)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

HUE_MIN_DEG = 80
HUE_MAX_DEG = 170
SAT_MIN = 0.20
VAL_MAX = 0.7
# 안티엘리어싱 노이즈 제외: G가 R, B보다 의미있게(>= 6) 큰 픽셀만 녹색 후보
GREEN_DOMINANCE_MIN = 6


def compute_hsv(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RGB(uint8) 배열에서 H(0-360), S(0-1), V(0-1) 계산."""
    rgb_f = rgb.astype(np.float32) / 255.0
    r, g, b = rgb_f[..., 0], rgb_f[..., 1], rgb_f[..., 2]
    maxc = np.max(rgb_f, axis=-1)
    minc = np.min(rgb_f, axis=-1)
    delta = maxc - minc

    v = maxc
    s = np.where(maxc > 0, delta / np.maximum(maxc, 1e-6), 0.0)

    h = np.zeros_like(maxc)
    nz = delta > 0
    mr = (maxc == r) & nz
    mg = (maxc == g) & nz
    mb = (maxc == b) & nz
    h[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6
    h[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2
    h[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4
    h = h * 60.0
    return h, s, v


def remove_green(rgb: np.ndarray) -> np.ndarray:
    """녹색 픽셀을 흰색으로 치환한 새 배열 반환.

    조건 (모두 만족):
    1. HSV에서 hue가 녹색 범위
    2. saturation >= SAT_MIN
    3. value < VAL_MAX
    4. G - max(R, B) >= GREEN_DOMINANCE_MIN (안티엘리어싱 노이즈 제외)
    """
    h, s, v = compute_hsv(rgb)
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    g_dominance = g - np.maximum(r, b)
    mask = (
        (h >= HUE_MIN_DEG) & (h <= HUE_MAX_DEG)
        & (s >= SAT_MIN)
        & (v < VAL_MAX)
        & (g_dominance >= GREEN_DOMINANCE_MIN)
    )
    out = rgb.copy()
    out[mask] = [255, 255, 255]
    return out


def extract_index(filename: str) -> Optional[str]:
    """파일명에서 3자리 인덱스 추출 (예: '... 001.png' → '001')."""
    m = re.search(r"(\d{3})\.png$", filename)
    return m.group(1) if m else None


def process_one(src_path: Path, dst_dir: Path) -> Path:
    """단일 이미지 처리. dst_dir/NNN.png 로 저장."""
    idx = extract_index(src_path.name)
    if idx is None:
        raise ValueError(f"인덱스 추출 실패: {src_path.name}")
    img = np.array(Image.open(src_path).convert("RGB"))
    cleaned = remove_green(img)
    out_path = dst_dir / f"{idx}.png"
    Image.fromarray(cleaned).save(out_path)
    return out_path


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="영어단어책 색상 분리 전처리")
    parser.add_argument("--input", required=True, help="입력 디렉토리")
    parser.add_argument("--output", required=True, help="출력 디렉토리")
    parser.add_argument("--only", help="3자리 인덱스 (예: 001). 지정 시 해당 파일만 처리")
    args = parser.parse_args(argv)

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pngs = sorted(input_dir.glob("*.png"))
    if not pngs:
        print(f"입력 PNG 없음: {input_dir}", file=sys.stderr)
        return 1

    if args.only:
        pngs = [p for p in pngs if extract_index(p.name) == args.only]
        if not pngs:
            print(f"--only {args.only} 매칭 파일 없음", file=sys.stderr)
            return 1

    for src in pngs:
        out = process_one(src, output_dir)
        print(f"{src.name} → {out.name}")

    print(f"\n완료: {len(pngs)}개 처리, 출력 = {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
