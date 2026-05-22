"""원본 이미지에서 좌측 컬럼의 각 텍스트 행을 자동 분류.

출력: 행 단위로 (y_start, y_end, color, weight_score)
- color: 'green' (G-max(R,B) >= 5) | 'black'
- weight_score: 행 내 어두운 픽셀 밀도 (높으면 bold 후보)

이 도구는 사람의 시각 판단 오류(녹색을 검정으로 오인, bold를 thin으로 오인 등)를
줄이기 위한 보조 검증용. cleaned 이미지가 아닌 ORIGINAL 이미지를 분석한다.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

# 좌측 컬럼 영역
LEFT_X_START = 50
LEFT_X_END = 480
# 배경 제외 (글자 + 안티엘리어싱 모두 포함)
NONWHITE_MAX = 220
# 진하게 어두운 픽셀 (글자 코어)
DARK_MAX = 150
# 녹색 판정 (둘 중 하나라도 충족하면 녹색):
# 1) 행 글자 픽셀의 G - max(R,B) 평균이 GREEN_AVG_THRESHOLD 이상
# 2) 녹색 픽셀(G > max(R,B) + 2) 비율이 GREEN_PIX_PCT 이상
GREEN_AVG_THRESHOLD = 3.0
GREEN_PIX_PCT = 0.15
# 행 검출: 글자 픽셀 N개 이상 있는 행을 텍스트 행으로 간주
MIN_PIXELS_PER_ROW = 20
# 행 병합: 연속된 텍스트 행 사이 빈 줄 갭이 이 픽셀 이하면 같은 단어로 병합
MAX_GAP_PX = 12


def find_text_rows(pixels_per_row: np.ndarray) -> List[Tuple[int, int]]:
    """행별 글자 픽셀 수에서 텍스트 행 구간을 찾는다."""
    in_row = False
    start = 0
    gap = 0
    rows: List[Tuple[int, int]] = []
    for y, n in enumerate(pixels_per_row):
        if n >= MIN_PIXELS_PER_ROW:
            if not in_row:
                start = y
                in_row = True
            gap = 0
        elif in_row:
            gap += 1
            if gap > MAX_GAP_PX:
                rows.append((start, y - gap))
                in_row = False
    if in_row:
        rows.append((start, len(pixels_per_row) - 1))
    return rows


def classify(image_path: Path) -> List[dict]:
    """이미지의 좌측 컬럼을 행 단위로 분류.

    배경 아닌 모든 픽셀(NONWHITE_MAX 이하)을 글자 후보로 보고,
    그 픽셀들의 G - max(R,B) 중앙값으로 녹색/검정 판정.
    이러면 옅은 녹색도 잡힘.
    """
    img = np.array(Image.open(image_path).convert("RGB"))
    left = img[:, LEFT_X_START:LEFT_X_END]
    r = left[..., 0].astype(int)
    g = left[..., 1].astype(int)
    b = left[..., 2].astype(int)
    maxc = np.maximum(np.maximum(r, g), b)
    # 글자 픽셀 = 배경(흰색)이 아닌 모든 픽셀
    char_pix = maxc < NONWHITE_MAX
    # 어두운 픽셀 (bold/thin 구분용)
    dark = maxc < DARK_MAX

    pix_per_row = char_pix.sum(axis=1)
    rows = find_text_rows(pix_per_row)

    width = left.shape[1]
    results = []
    for y0, y1 in rows:
        if y1 - y0 < 5:
            continue
        cp = char_pix[y0:y1 + 1]
        d = dark[y0:y1 + 1]
        if cp.sum() < MIN_PIXELS_PER_ROW:
            continue
        # 색상 판정: 모든 글자 픽셀 기준 (평균 + 녹색 비율 둘 중 하나로 판정)
        gminus = (g[y0:y1 + 1] - np.maximum(r[y0:y1 + 1], b[y0:y1 + 1]))[cp]
        avg_g = float(gminus.mean())
        median_g = int(np.median(gminus))
        green_pct = float((gminus > 2).mean())
        is_green = (avg_g >= GREEN_AVG_THRESHOLD) or (green_pct >= GREEN_PIX_PCT)
        color = "green" if is_green else "black"
        # 무게 점수: 진하게 어두운 픽셀 비율 (bold는 더 진함)
        row_height = y1 - y0 + 1
        dark_density = d.sum() / (row_height * width)
        char_density = cp.sum() / (row_height * width)
        # bold/thin 추정: 어두운 픽셀 비율이 전체 글자 픽셀 비율 대비 얼마나 높은지
        dark_ratio = d.sum() / max(cp.sum(), 1)
        results.append({
            "y0": y0,
            "y1": y1,
            "height": row_height,
            "color": color,
            "g_avg": round(avg_g, 1),
            "g_median": median_g,
            "green_pct": round(green_pct * 100, 0),
            "dark_density": round(dark_density, 3),
            "char_density": round(char_density, 3),
            "dark_ratio": round(dark_ratio, 2),
        })
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="원본 이미지 경로")
    args = parser.parse_args(argv)
    rows = classify(Path(args.image))
    print(f"{'#':>3} {'y0':>5} {'y1':>5} {'h':>3} {'color':>6} {'G-avg':>5} {'green%':>6} {'dark%':>5} {'thick':>5}")
    print("-" * 64)
    for i, r in enumerate(rows, 1):
        mark = "★" if r["color"] == "black" else " "
        print(f"{i:>3} {r['y0']:>5} {r['y1']:>5} {r['height']:>3} {r['color']:>6} {r['g_avg']:>+5.1f} {r['green_pct']:>5.0f}% {r['dark_density']*100:>4.1f}% {r['dark_ratio']:>5.2f} {mark}")
    print(f"\n총 {len(rows)} 행 (검정 {sum(1 for r in rows if r['color']=='black')}, 녹색 {sum(1 for r in rows if r['color']=='green')})")
    print("★ = 검정 (추출 후보, bold 메인표제어는 별도 시각 판단)")
    print("thick = 어두운/글자 픽셀 비율. 1.0 근처 = bold, 0.5 이하 = 옅은 thin 가능성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
