# 영어단어책 스캔본 → 엑셀 추출 설계 (v2)

작성일: 2026-05-22
작성자: 13studio
버전: v2 (색상 분리 전처리 단계 추가)

## 변경 이력

- **v1 → v2**: 픽셀 색상 분석 결과, 일부 녹색 단어가 시각적으로 검정과 거의 구분되지 않는 어두운 녹색(R≈73, G≈103, B≈65)임이 확인됨. Vision 단독으로는 오추출 위험이 크므로, Python으로 녹색 픽셀을 사전 제거하는 전처리 단계를 추가.

## 목적

영어단어책 스캔본 28장에서 **좌측 첫 번째 묶음의 얇은(regular weight) 검정 영어단어와 한글 뜻**만 추출하여 단일 Excel 파일로 정리한다.

## 입력

- 경로: `/Users/dohyung/Downloads/English/`
- 형식: PNG 28장 (KakaoTalk_Photo_2026-05-22-23-18-*.png)

## 출력

- 경로: `/Users/dohyung/Desktop/13studio/English_book/vocabulary.xlsx`
- 형식: Excel (.xlsx)
- 시트: `Vocabulary`
- 컬럼: A=`단어`, B=`뜻`
- 1행 헤더, 2행부터 데이터
- 정렬: 이미지 순서 (001 → 028)

## 추출 규칙

각 이미지의 **좌측 첫 번째 묶음**에서만 추출한다.

| 분류 | 색상 | 굵기 | 처리 |
|-----|------|------|------|
| 메인 표제어 | 검정 (R≈G≈B≈34) | 굵음 (bold) | ❌ 제외 |
| **파생어/관련어** | **검정** | **얇음 (regular)** | ✅ **추출** |
| 숙어/구문/변화형 | 어두운 녹색 (G > R,B) | 얇음 | ❌ 제외 |

예시 (Image #1 좌측 컬럼 기준):
- 굵은 검정 (제외): `that`, `this`, `thus`, `they`, `their`, `them`, `to`, `to V`, `do`, `doing`, `done`, `come`, `coming`, `become`, `overcome` 등
- **얇은 검정 (추출)**: `theirs 그들의 것`
- 녹색 (제외): `so that`, `to do with`, `do without`, `outcome`, `income`, `come into`, `come up` 등

> 사용자 우려대로, 어두운 녹색은 사람 눈에 검정처럼 보일 수 있다. 색상 분리 전처리로 이 위험을 제거한다.

중앙/우측 묶음은 모두 무시한다.

## 아키텍처 (2단계 파이프라인)

### Stage 1: 색상 분리 (Python 전처리)

```
입력: 28장 원본 PNG
처리:
  1. PIL로 이미지 로드 → RGB 배열
  2. HSV 변환으로 픽셀별 hue/saturation/value 계산
  3. 녹색 마스크 정의:
     - Hue: 80° ~ 170° (녹색 ~ 청록 범위)
     - Saturation: >= 0.15 (회색 제외)
     - Value: < 0.7 (밝은 배경 제외)
  4. 녹색 마스크에 해당하는 픽셀을 흰색(255,255,255)으로 치환
  5. 결과를 /tmp/cleaned/NNN.png로 저장
출력: 28장 cleaned PNG (검정만 남음)
```

### Stage 2: 시각 판독 (Claude Vision)

```
입력: cleaned 28장
처리 (이미지마다):
  1. Read tool로 cleaned 이미지 로드
  2. 좌측 첫 번째 묶음만 시각 스캔
  3. 검정 단어 중 굵기가 얇은(regular) 것만 → 우측 한글 뜻과 페어링
  4. 텍스트 리스트로 사용자에게 제시:
     "이미지 N 추출 결과:
      - theirs : 그들의 것
      승인하시겠습니까?"
  5. 사용자 응답:
     - 승인 → progress.json 업데이트, 로그 추가
     - 수정 → 페어 교정 후 저장
출력: 누적된 (단어, 뜻) 페어 리스트
```

### Stage 3: 엑셀 작성

```
입력: vocabulary_progress.json
처리: openpyxl로 .xlsx 생성, 헤더 + 데이터 작성
출력: /Users/dohyung/Desktop/13studio/English_book/vocabulary.xlsx
```

## 컴포넌트

1. **color_separator.py**: 단일 Python 스크립트. 입력 디렉토리의 PNG 28장을 모두 처리하여 cleaned 디렉토리에 저장
2. **Vision 추출기**: Claude가 cleaned 이미지를 Read tool로 로드하여 얇은 검정 페어 식별
3. **검토 게이트**: 이미지마다 추출 결과 텍스트 리스트로 사용자 검토
4. **누적 저장소**: `vocabulary_progress.json` — 이미지별 확정 페어 백업, 중단 시 재개 가능
5. **로그 작성기**: `extraction_log.md` — 사람이 읽을 수 있는 추출 기록
6. **xlsx 작성기**: 별도 Python 스크립트 또는 인라인. openpyxl 사용

## 색상 분리 파라미터 (검증된 값)

001.png 샘플로 검증한 HSV 마스크 파라미터:

| 파라미터 | 값 | 근거 |
|---------|-----|------|
| Hue 하한 | 80° | 어두운 녹색 시작점 |
| Hue 상한 | 170° | 청록 끝 (파랑 시작 전) |
| Saturation 하한 | 0.15 | 회색 텍스트 제외 |
| Value 상한 | 0.7 | 배경/밝은 영역 제외 |

검증 결과: 좌측 컬럼 어두운 픽셀 중 검정 87.0%, 녹색 3.7% 분리됨. `so that`, `to do with`, `do without`, `outcome`, `income`, `come into`, `come up` 모두 녹색으로 정확히 식별.

## 오류 처리

- **굵기 애매**: 페어 옆에 `[?]` 표시 후 사용자 판단 요청
- **빈 좌측 컬럼**: "이미지 N: 얇은 검정 단어 없음" 보고 후 다음
- **색상 분리 실패 (PIL 오류)**: 사용자에게 보고, 원본 이미지로 fallback
- **openpyxl 미설치**: `pip install openpyxl` 안내 후 설치
- **작업 중단**: progress.json으로 마지막 처리 이미지부터 재개

## 의존성

- Python 3 (시스템 기본)
- Pillow (PIL) — 시스템에 이미 설치됨 (확인됨)
- numpy — 시스템에 이미 설치됨 (2.0.2, 확인됨)
- openpyxl — 필요시 설치

## 산출물

- `/tmp/cleaned/NNN.png` — 색상 분리된 cleaned 이미지 28장
- `/tmp/color_separator.py` — 전처리 스크립트
- `vocabulary_progress.json` — 누적 페어 백업
- `extraction_log.md` — 추출 로그
- `vocabulary.xlsx` — 최종 엑셀

## 비목표 (Out of scope)

- 중앙/우측 컬럼 단어 추출
- 굵은 검정 표제어 추출
- 녹색 숙어/구문/변화형 추출
- 완전 자동 OCR (Tesseract 등) 파이프라인
- 폰트 굵기 자동 탐지 (Vision에 위임)

## 성공 기준

1. 28장 모두 색상 분리 완료, cleaned 디렉토리에 저장
2. 28장 모두 Vision 판독 완료, 각 이미지에서 추출된 페어가 사용자 검토 통과
3. `vocabulary.xlsx` 파일이 Excel에서 정상적으로 열림
4. 헤더(`단어`, `뜻`) + 누적 데이터가 이미지 순서대로 정렬
5. Image #1 검증: 추출 페어가 `theirs / 그들의 것` 하나로 일치 (사용자 명시 정답)
