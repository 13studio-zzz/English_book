# 영어단어책 어휘 추출 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영어단어책 스캔본 28장에서 좌측 첫 번째 묶음의 얇은 검정 영어단어와 한글 뜻만 추출하여 `vocabulary.xlsx`로 저장한다.

**Architecture:** 2단계 파이프라인. Stage 1은 Python(PIL+numpy) HSV 마스크로 녹색 픽셀을 흰색으로 치환하여 cleaned 이미지 28장 생성. Stage 2는 Claude Vision이 cleaned 이미지를 이미지별로 읽으며 얇은 검정 페어를 추출, 매 이미지마다 사용자 검토로 progress.json에 누적. Stage 3은 openpyxl로 .xlsx 작성.

**Tech Stack:** Python 3, Pillow, numpy, openpyxl, pytest, Claude Vision (Read tool)

---

## Task 1: 디렉토리 구조 및 의존성 셋업

**Files:**
- Create: `/Users/dohyung/Desktop/13studio/English_book/scripts/`
- Create: `/Users/dohyung/Desktop/13studio/English_book/cleaned/`
- Create: `/Users/dohyung/Desktop/13studio/English_book/data/`
- Create: `/Users/dohyung/Desktop/13studio/English_book/tests/`
- Create: `/Users/dohyung/Desktop/13studio/English_book/.gitignore`

- [ ] **Step 1: 디렉토리 생성**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
mkdir -p scripts cleaned data tests
```

Expected: 디렉토리 4개 생성됨, 에러 없음.

- [ ] **Step 2: .gitignore 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/.gitignore`:

```
# 대용량 생성물
cleaned/
*.xlsx

# Python
__pycache__/
*.pyc
.pytest_cache/

# OS
.DS_Store
```

- [ ] **Step 3: 의존성 확인 및 설치**

Run:
```bash
python3 -c "from PIL import Image; import numpy; import openpyxl; print('OK')" 2>&1
```

Expected: `OK` 또는 `ModuleNotFoundError: No module named 'openpyxl'`.

If openpyxl 미설치이면:
```bash
pip3 install openpyxl
```

재확인:
```bash
python3 -c "import openpyxl; print(openpyxl.__version__)"
```

Expected: 버전 번호 출력 (예: `3.1.x`).

- [ ] **Step 4: 입력 이미지 개수 확인**

Run:
```bash
ls /Users/dohyung/Downloads/English/*.png | wc -l
```

Expected: 28 (출력값이 28이 아니면 사용자에게 보고하고 진행 중단).

- [ ] **Step 5: Commit**

```bash
cd /Users/dohyung/Desktop/13studio/English_book
git add .gitignore
git commit -m "chore: 어휘 추출 디렉토리 구조 셋업"
```

---

## Task 2: 색상 분리 스크립트 — 실패 테스트 작성

**Files:**
- Create: `tests/test_color_separator.py`

- [ ] **Step 1: 테스트 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/tests/test_color_separator.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 -m pytest tests/test_color_separator.py -v
```

Expected: 모든 테스트 FAIL (`scripts/color_separator.py` 없음으로 인한 returncode != 0 또는 ModuleNotFoundError).

- [ ] **Step 3: Commit**

```bash
git add tests/test_color_separator.py
git commit -m "test: 색상 분리 스크립트 실패 테스트 추가"
```

---

## Task 3: 색상 분리 스크립트 구현

**Files:**
- Create: `scripts/color_separator.py`

- [ ] **Step 1: 스크립트 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/scripts/color_separator.py`:

```python
"""영어단어책 스캔본 색상 분리 전처리.

HSV 색 공간에서 어두운 녹색 픽셀을 식별하여 흰색으로 치환한다.
입력 디렉토리의 모든 PNG (또는 --only로 특정 파일)를 처리.

검증된 파라미터:
- Hue: 80° ~ 170° (어두운 녹색 ~ 청록)
- Saturation: >= 0.15 (회색 텍스트 제외)
- Value: < 0.7 (밝은 배경 제외)
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HUE_MIN_DEG = 80
HUE_MAX_DEG = 170
SAT_MIN = 0.15
VAL_MAX = 0.7


def compute_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    """녹색 픽셀을 흰색으로 치환한 새 배열 반환."""
    h, s, v = compute_hsv(rgb)
    mask = (h >= HUE_MIN_DEG) & (h <= HUE_MAX_DEG) & (s >= SAT_MIN) & (v < VAL_MAX)
    out = rgb.copy()
    out[mask] = [255, 255, 255]
    return out


def extract_index(filename: str) -> str | None:
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


def main(argv: list[str] | None = None) -> int:
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
```

- [ ] **Step 2: 테스트 실행으로 통과 확인**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 -m pytest tests/test_color_separator.py -v
```

Expected: 3개 테스트 모두 PASS.

- [ ] **Step 3: 시각 검증 (사용자 확인 단계)**

Run:
```bash
ls -la /Users/dohyung/Desktop/13studio/English_book/cleaned/001.png
```

이후 `cleaned/001.png`를 Read tool로 로드하여 사용자에게 보여주기. 좌측 첫 묶음에서:
- `so that`, `to do with`, `do without`, `income`, `come into`, `come up` 등 녹색 단어들 → **사라짐(흰색)** 확인
- `that`, `this`, `theirs` 등 검정 단어들 → **그대로 유지** 확인

사용자 승인 받고 다음으로.

- [ ] **Step 4: Commit**

```bash
git add scripts/color_separator.py
git commit -m "feat: HSV 마스크 기반 녹색 픽셀 제거 전처리 스크립트"
```

---

## Task 4: 28장 일괄 색상 분리 실행

**Files:**
- 생성: `cleaned/001.png ~ cleaned/028.png` (28장)

- [ ] **Step 1: 전체 일괄 처리**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 scripts/color_separator.py \
  --input /Users/dohyung/Downloads/English \
  --output cleaned
```

Expected: 28줄 출력 (`... .png → NNN.png`), 마지막 줄 `완료: 28개 처리...`.

- [ ] **Step 2: 출력 개수 검증**

Run:
```bash
ls cleaned/*.png | wc -l
```

Expected: `28`.

- [ ] **Step 3: 임의 샘플 시각 확인 (사용자 검토)**

Read tool로 `cleaned/014.png` (중간 인덱스) 로드하여 사용자에게 제시. 녹색이 사라졌고 검정은 유지되었는지 시각 확인. 문제 있으면 보고 후 중단.

---

## Task 5: 추출 데이터 저장소 초기화

**Files:**
- Create: `data/vocabulary_progress.json`
- Create: `data/extraction_log.md`

- [ ] **Step 1: progress.json 초기 파일 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/data/vocabulary_progress.json`:

```json
{
  "schema_version": 1,
  "last_processed_index": null,
  "images": {}
}
```

스키마:
- `images`: `{"001": [{"word": "theirs", "meaning": "그들의 것"}, ...], "002": [...], ...}`
- 이미지 처리 직후 해당 키 추가.
- `last_processed_index`: 마지막으로 사용자 승인 받은 이미지 인덱스 (재개 지점).

- [ ] **Step 2: extraction_log.md 초기 파일 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/data/extraction_log.md`:

```markdown
# 어휘 추출 로그

작업 시작: 2026-05-22

| 이미지 | 추출 수 | 단어 목록 | 비고 |
|--------|---------|-----------|------|
```

이미지마다 한 행 추가될 예정.

- [ ] **Step 3: Commit**

```bash
git add data/vocabulary_progress.json data/extraction_log.md
git commit -m "chore: 어휘 추출 진행 저장소 초기화"
```

---

## Task 6: 이미지별 Vision 추출 루프 (28회 반복)

> **참고:** 이 Task는 Claude(에이전트)가 직접 수행하는 인터랙티브 단계다.
> Python 스크립트가 아니라, Read tool로 cleaned 이미지를 읽고 시각적으로 페어를 식별한 뒤
> 사용자에게 텍스트 리스트로 제시하고 승인/수정을 받는 과정을 28번 반복한다.

**Files:**
- Modify: `data/vocabulary_progress.json` (매 이미지마다 추가)
- Modify: `data/extraction_log.md` (매 이미지마다 한 행 추가)

각 이미지 N (N = 001 ~ 028)에 대해 다음 단계를 반복:

- [ ] **Step 1: cleaned/N.png 로드**

Read tool로 `/Users/dohyung/Desktop/13studio/English_book/cleaned/N.png` 로드.

- [ ] **Step 2: 좌측 첫 번째 묶음 식별**

이미지를 보고 좌측에서 첫 번째 단어 묶음(맨 왼쪽 컬럼) 영역만 시각적으로 스캔.
중앙/우측 묶음은 무시. 헤더(예: 흐릿한 숫자, 워터마크)도 무시.

- [ ] **Step 3: 얇은 검정 페어 추출**

좌측 묶음 안에서 다음 규칙으로 페어 추출:
- **추출**: 얇은(regular weight) 검정 글자의 영어 단어 + 같은 줄 우측에 위치한 한글 뜻
- **제외**: 굵은(bold) 검정 글자 (메인 표제어)
- **제외**: 색상 분리 후에도 남은 회색/연한 글자가 있다면 사용자에게 보고

각 페어는 `{"word": "...", "meaning": "..."}` 형태로 메모.

- [ ] **Step 4: 사용자에게 텍스트 리스트로 제시**

다음 형식으로 출력:

```
이미지 N 추출 결과:
1. theirs : 그들의 것
2. ... : ...

승인하시겠습니까? (예 / 수정사항을 알려주세요)
```

페어가 0개면:
```
이미지 N: 좌측 묶음에 얇은 검정 단어 없음. 건너뜁니다. (확인)
```

- [ ] **Step 5: 사용자 응답 처리**

- "예" / 승인 → Step 6으로
- 수정사항 → 페어 목록 교정 후 다시 Step 4로 (재제시 → 재승인)

- [ ] **Step 6: progress.json 업데이트**

Edit tool로 `data/vocabulary_progress.json`을 읽고 다음을 반영:
- `images["N"]` 키에 확정 페어 배열 추가
- `last_processed_index`를 `"N"`으로 갱신

예시 (이미지 001 처리 후):
```json
{
  "schema_version": 1,
  "last_processed_index": "001",
  "images": {
    "001": [
      {"word": "theirs", "meaning": "그들의 것"}
    ]
  }
}
```

- [ ] **Step 7: extraction_log.md에 한 행 추가**

Edit tool로 표 하단에 추가:

```
| 001 | 1 | theirs | - |
```

빈 이미지면 `| 005 | 0 | - | 얇은 검정 없음 |`.

- [ ] **Step 8: Commit (5장마다 1회)**

매 5장 처리 후(N = 005, 010, 015, 020, 025, 028) 커밋:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
git add data/vocabulary_progress.json data/extraction_log.md
git commit -m "data: 어휘 추출 진행 이미지 ~N"
```

(왜 5장씩: 한 장당 커밋은 노이즈가 크고, 한 번에 28장 커밋은 중단 시 손실이 큼)

**전체 루프 종료 조건:** N = 028 까지 처리 완료, `last_processed_index == "028"`.

---

## Task 7: 엑셀 생성 스크립트 — 실패 테스트 작성

**Files:**
- Create: `tests/test_build_xlsx.py`

- [ ] **Step 1: 테스트 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/tests/test_build_xlsx.py`:

```python
"""build_xlsx.py 테스트.

샘플 progress.json으로 .xlsx를 생성하고 구조/내용을 검증.
"""
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

REPO = Path("/Users/dohyung/Desktop/13studio/English_book")
SCRIPT = REPO / "scripts" / "build_xlsx.py"


def _make_progress(tmp_path: Path) -> Path:
    """테스트용 progress.json 생성."""
    data = {
        "schema_version": 1,
        "last_processed_index": "003",
        "images": {
            "001": [{"word": "theirs", "meaning": "그들의 것"}],
            "002": [],
            "003": [
                {"word": "alpha", "meaning": "알파"},
                {"word": "beta", "meaning": "베타"}
            ]
        }
    }
    p = tmp_path / "progress.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _run_build(progress_path: Path, out_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--input", str(progress_path), "--output", str(out_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"build_xlsx 실패:\n{result.stderr}"


def test_xlsx_file_created(tmp_path):
    """.xlsx 파일이 생성된다."""
    progress = _make_progress(tmp_path)
    out = tmp_path / "vocab.xlsx"
    _run_build(progress, out)
    assert out.exists()


def test_xlsx_has_header(tmp_path):
    """첫 행은 한글 헤더 [단어, 뜻]."""
    progress = _make_progress(tmp_path)
    out = tmp_path / "vocab.xlsx"
    _run_build(progress, out)
    wb = load_workbook(out)
    ws = wb["Vocabulary"]
    assert ws.cell(row=1, column=1).value == "단어"
    assert ws.cell(row=1, column=2).value == "뜻"


def test_xlsx_rows_in_image_order(tmp_path):
    """데이터 행이 이미지 인덱스 순서(001 → 003)대로 정렬되며, 빈 이미지는 건너뛴다."""
    progress = _make_progress(tmp_path)
    out = tmp_path / "vocab.xlsx"
    _run_build(progress, out)
    wb = load_workbook(out)
    ws = wb["Vocabulary"]
    # 2행: theirs, 3행: alpha, 4행: beta, 5행: 빈 셀
    assert ws.cell(row=2, column=1).value == "theirs"
    assert ws.cell(row=2, column=2).value == "그들의 것"
    assert ws.cell(row=3, column=1).value == "alpha"
    assert ws.cell(row=3, column=2).value == "알파"
    assert ws.cell(row=4, column=1).value == "beta"
    assert ws.cell(row=4, column=2).value == "베타"
    assert ws.cell(row=5, column=1).value is None
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 -m pytest tests/test_build_xlsx.py -v
```

Expected: 3개 테스트 FAIL (`scripts/build_xlsx.py` 없음).

- [ ] **Step 3: Commit**

```bash
git add tests/test_build_xlsx.py
git commit -m "test: 엑셀 생성 스크립트 실패 테스트 추가"
```

---

## Task 8: 엑셀 생성 스크립트 구현

**Files:**
- Create: `scripts/build_xlsx.py`

- [ ] **Step 1: 스크립트 작성**

Write to `/Users/dohyung/Desktop/13studio/English_book/scripts/build_xlsx.py`:

```python
"""progress.json → vocabulary.xlsx 변환.

이미지 인덱스 순서대로 단어/뜻을 정렬하여 단일 시트 .xlsx 생성.
"""
import argparse
import json
import sys
from pathlib import Path

from openpyxl import Workbook


def build(progress_path: Path, output_path: Path) -> int:
    data = json.loads(progress_path.read_text(encoding="utf-8"))
    images = data.get("images", {})

    wb = Workbook()
    ws = wb.active
    ws.title = "Vocabulary"
    ws.cell(row=1, column=1, value="단어")
    ws.cell(row=1, column=2, value="뜻")

    row = 2
    total = 0
    for idx in sorted(images.keys()):
        for pair in images[idx]:
            ws.cell(row=row, column=1, value=pair["word"])
            ws.cell(row=row, column=2, value=pair["meaning"])
            row += 1
            total += 1

    # 컬럼 폭 자동 조정 (대략)
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 40

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"작성 완료: {output_path} ({total}개 단어)")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="progress.json → xlsx")
    parser.add_argument("--input", required=True, help="vocabulary_progress.json 경로")
    parser.add_argument("--output", required=True, help="vocabulary.xlsx 출력 경로")
    args = parser.parse_args(argv)
    build(Path(args.input), Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 테스트 실행으로 통과 확인**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 -m pytest tests/test_build_xlsx.py -v
```

Expected: 3개 테스트 PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_xlsx.py
git commit -m "feat: progress.json → xlsx 변환 스크립트"
```

---

## Task 9: 최종 엑셀 생성 및 검증

**Files:**
- Create: `vocabulary.xlsx`

- [ ] **Step 1: 최종 .xlsx 생성**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 scripts/build_xlsx.py \
  --input data/vocabulary_progress.json \
  --output vocabulary.xlsx
```

Expected: `작성 완료: vocabulary.xlsx (N개 단어)` 출력.

- [ ] **Step 2: 파일 존재 및 크기 확인**

Run:
```bash
ls -la vocabulary.xlsx
```

Expected: 파일 존재, 크기 > 5000 bytes.

- [ ] **Step 3: 내용 검증 (Python으로 첫 5행 출력)**

Run:
```bash
cd /Users/dohyung/Desktop/13studio/English_book
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('vocabulary.xlsx')
ws = wb['Vocabulary']
print(f'총 행 수: {ws.max_row}')
for r in range(1, min(6, ws.max_row + 1)):
    print(r, ws.cell(row=r, column=1).value, '|', ws.cell(row=r, column=2).value)
"
```

Expected: 
- `총 행 수: N+1` (N개 단어 + 헤더)
- 1행: `단어 | 뜻`
- 2행: `theirs | 그들의 것` (이미지 001에서 추출한 알려진 정답)
- 그 외 정상 페어들.

- [ ] **Step 4: 사용자에게 최종 파일 경로 제시**

다음 메시지로 사용자에게 알리기:
```
완료. 결과 파일:
/Users/dohyung/Desktop/13studio/English_book/vocabulary.xlsx
총 N개 단어, 28장 처리.

Excel/Numbers에서 열어보시고 누락/오류가 있으면 알려주세요.
```

- [ ] **Step 5: Commit (xlsx는 gitignore에 있으므로 progress/log만 최종 커밋)**

```bash
cd /Users/dohyung/Desktop/13studio/English_book
git add data/vocabulary_progress.json data/extraction_log.md
git commit -m "data: 28장 어휘 추출 완료"
```

(`vocabulary.xlsx`는 `.gitignore`에 있으므로 git에 포함되지 않음. 의도된 동작.)

---

## Self-Review 노트

스펙 v2 대비 커버리지:
- ✅ Stage 1 (색상 분리) → Task 2-4
- ✅ Stage 2 (Vision 추출 루프) → Task 5-6
- ✅ Stage 3 (엑셀 생성) → Task 7-9
- ✅ progress.json 재개 가능성 → Task 6 Step 6 (last_processed_index 사용)
- ✅ extraction_log.md → Task 5, 6
- ✅ Image #1 검증 (theirs / 그들의 것) → Task 9 Step 3
- ✅ HSV 파라미터 (H 80-170, S≥0.15, V<0.7) → Task 3
- ✅ 사용자 검토 게이트 → Task 6 Step 4-5
- ✅ 좌측 묶음만 처리 → Task 6 Step 2
- ✅ 굵은/얇은/녹색 분류 → Task 6 Step 3

위험 요소:
- Task 6의 28회 반복은 단조롭지만 인터랙티브가 필수다. 자동화 유혹을 거부할 것.
- cleaned 이미지에서도 굵기 구분이 애매하면 `[?]` 표시로 사용자에게 위임.
- openpyxl 미설치 시 Task 1 Step 3에서 설치하므로 Task 8까지 문제없음.
