"""원본 이미지에서 추출 후보 자동 생성.

classify_rows의 출력을 받아 분류:
- BOLD (thick >= 0.80): 메인 표제어 → 자동 제외
- THIN (thick < 0.80): 추출 후보 → 사용자 확인
- GREEN: 자동 제외

검정 행은 한 줄도 빠뜨리지 않고 모두 후보 분류한다.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify_rows import classify

# bold vs thin 경계
BOLD_THICK_THRESHOLD = 0.80


def categorize(rows):
    bold = []
    thin = []
    green = []
    for r in rows:
        if r["color"] == "green":
            green.append(r)
        elif r["dark_ratio"] >= BOLD_THICK_THRESHOLD:
            bold.append(r)
        else:
            thin.append(r)
    return bold, thin, green


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    args = parser.parse_args(argv)
    rows = classify(Path(args.image))
    bold, thin, green = categorize(rows)

    print(f"=== {Path(args.image).name} ===")
    print(f"총 {len(rows)} 행 (검정 {len(bold) + len(thin)}, 녹색 {len(green)})\n")

    print(f"[A] 추출 후보 (THIN 검정, 굵기 thick<{BOLD_THICK_THRESHOLD}): {len(thin)}개")
    for r in thin:
        print(f"    y={r['y0']:>4}-{r['y1']:>4} thick={r['dark_ratio']:.2f} h={r['height']}")

    print(f"\n[B] 자동 제외 BOLD (메인 표제어, thick>={BOLD_THICK_THRESHOLD}): {len(bold)}개")
    for r in bold:
        print(f"    y={r['y0']:>4}-{r['y1']:>4} thick={r['dark_ratio']:.2f}")

    print(f"\n[C] 자동 제외 GREEN: {len(green)}개")
    for r in green:
        print(f"    y={r['y0']:>4}-{r['y1']:>4} G-avg={r['g_avg']:+.1f}")

    print(f"\n>> 추출 후보 {len(thin)}개 모두 시각 확인 후 단어/뜻 식별 필요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
