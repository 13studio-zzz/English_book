"""color_separator.py 테스트.
샘플 이미지(001)에서 알려진 녹색 위치가 흰색으로 치환되는지,
알려진 검정 위치는 그대로 유지되는지 확인.
"""
import subprocess
import sys
from pathlib import Path
from PIL import Image
import numpy as np

REPO = Path("/Users/dohyung/Desktop/13studio/English_book")
SCRIPT = REPO / "scripts" / "color_separator.py"
INPUT_DIR = Path("/Users/dohyung/Downloads/English")
OUTPUT_DIR = REPO / "cleaned"


def _run_separator(target: str) -> None:
    """color_separator.py 실행."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(INPUT_DIR),
         "--output", str(OUTPUT_DIR), "--only", target],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"스크립트 실패:\n{result.stderr}"


def _find_input(idx: str) -> Path:
    """idx (예: '001') 에 해당하는 입력 파일 찾기."""
    candidates = sorted(INPUT_DIR.glob(f"*{idx}.png"))
    assert candidates, f"이미지 {idx} 못 찾음"
    return candidates[0]


def test_output_file_created():
    """cleaned/001.png 파일이 생성된다."""
    _run_separator("001")
    out = OUTPUT_DIR / "001.png"
    assert out.exists(), f"{out} 생성 안 됨"


def test_green_pixels_become_white():
    """원본의 녹색 영역이 cleaned 이미지에서 흰색이 된다.

    'so that' 텍스트가 위치한 좌측 영역의 어두운 녹색 픽셀을 표본 검사한다.
    """
    _run_separator("001")
    src = np.array(Image.open(_find_input("001")).convert("RGB"))
    dst = np.array(Image.open(OUTPUT_DIR / "001.png").convert("RGB"))

    # 원본에서 어두운 녹색이었던 픽셀 찾기 (G > R + 10 이고 V < 0.5)
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    v = np.maximum(np.maximum(r, g), b) / 255.0
    green_mask = (g.astype(int) - r.astype(int) > 10) & (v < 0.5)

    # 좌측 절반에서 100개 이상의 녹색 픽셀이 있어야 표본 의미가 있음
    left_green = green_mask[:, : src.shape[1] // 2]
    assert left_green.sum() > 100, "좌측에 녹색 픽셀이 거의 없음"

    # cleaned 이미지에서 해당 좌표들이 흰색(>= 240)인지 확인
    cleaned_at_green = dst[:, : src.shape[1] // 2][left_green]
    is_white = (cleaned_at_green >= 240).all(axis=-1)
    white_ratio = is_white.mean()
    assert white_ratio > 0.95, (
        f"녹색이 흰색으로 치환된 비율이 낮음: {white_ratio:.2%}"
    )


def test_black_pixels_preserved():
    """원본의 검정 영역은 cleaned 이미지에서도 검정으로 유지된다.

    중성 검정 픽셀(R≈G≈B, V<0.3)을 표본 검사.
    """
    _run_separator("001")
    src = np.array(Image.open(_find_input("001")).convert("RGB"))
    dst = np.array(Image.open(OUTPUT_DIR / "001.png").convert("RGB"))

    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    is_neutral = (maxc.astype(int) - minc.astype(int)) < 10
    is_dark = maxc < 80
    black_mask = is_neutral & is_dark

    assert black_mask.sum() > 1000, "검정 픽셀이 너무 적음"

    # 원본 검정 좌표에서 cleaned도 어두워야 함 (V < 100)
    cleaned_at_black = dst[black_mask]
    cleaned_v = cleaned_at_black.max(axis=-1)
    dark_ratio = (cleaned_v < 100).mean()
    assert dark_ratio > 0.95, (
        f"검정 픽셀이 어둡게 유지된 비율이 낮음: {dark_ratio:.2%}"
    )
