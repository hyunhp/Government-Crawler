# 정부 R&D 과제·공고 크롤러

정부 지원사업·R&D 과제·입찰공고를 사이트별로 수집하고, 하나의 표준 CSV로 통합하는 도구.
모든 데이터는 로컬 PC에만 저장됨. 클라우드 계정 불필요.

## 수집 대상

| 플랫폼 | 수집 방식 | API 키 변수명 | 키 발급 페이지 |
| --- | --- | --- | --- |
| Bizinfo | OpenAPI | `bizinfo_api` | [Bizinfo OpenAPI](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi) |
| IRIS | 웹 수집 (Chrome) | 불필요 | - |
| MSIT | 공공데이터포털 API | `msit_api` | [과기정통부 사업공고](https://www.data.go.kr/data/15074634/openapi.do) |
| NRF | 웹 수집 | 불필요 | - |
| NTIS | 웹 수집 (Chrome) | 불필요 | - |
| 나라장터 입찰 (PPS) | 공공데이터포털 API | `pps_api` | [입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do) |
| 나라장터 발주계획 | 공공데이터포털 API | `g2b_ordering_api` | [발주계획현황서비스](https://www.data.go.kr/data/15129462/openapi.do) |
| 중소벤처24 (SMES) | OpenAPI | `smes_api` | [중소벤처24 OpenAPI](https://www.smes.go.kr/main/dbCnrs) |
| SMTECH | 웹 수집 (Chrome) | 불필요 | - |

## 1. 사전 준비

- **운영체제**: macOS 또는 Linux. Windows는 [WSL](https://learn.microsoft.com/ko-kr/windows/wsl/install)에서 실행
- **Python 3.11**
- **Google Chrome**: IRIS·NTIS·SMTECH 수집에 필요. 드라이버는 자동 설치됨

## 2. 설치

```bash
git clone https://github.com/hyunhp/Government-Crawler.git
cd Government-Crawler

python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

cp env/.env.example env/.env
```

`.venv` 폴더가 있으면 실행 스크립트가 자동으로 사용함. 가상환경 활성화(`source`) 불필요.

## 3. API 키 입력

1. 위 표의 발급 페이지에서 로그인 후 **활용 신청**
2. 승인 후 발급된 인증키 확인
3. `env/.env` 파일에 변수명에 맞춰 입력

```dotenv
bizinfo_api=발급받은_키
msit_api=발급받은_키
pps_api=발급받은_키
g2b_ordering_api=발급받은_키
smes_api=발급받은_키
```

- 키가 없는 플랫폼은 해당 크롤러만 실패하고 나머지는 정상 진행
- `env/.env`는 Git에 올라가지 않음. 키를 코드나 README에 직접 적지 말 것

## 4. 실행

```bash
./run_pipeline.sh                          # 지난주 월요일부터 수집, 키워드 '양자'
./run_pipeline.sh 2026-11-02               # 시작일 지정
./run_pipeline.sh 2026-11-02 "양자컴퓨터"   # 시작일 + 키워드 지정
```

실행 순서: 오래된 파일 정리 → 9개 사이트 수집 → 통합 및 키워드 추출 → 결과 요약 출력.
사이트별 수집 종료 시점은 각 사이트의 날짜·페이지 구조에 따라 다를 수 있음.

## 5. 결과 확인

| 폴더 | 내용 | 파일명 예시 |
| --- | --- | --- |
| `integrated/` | 전체 사이트 통합본 | `integrated_2026-11-02_2026-11-03.csv` |
| `result/` | 키워드 포함 공고만 추출 | `quantum_2026-11-02_2026-11-03.csv` |
| `raw/<사이트>/` | 사이트별 원본 | `raw/pps/pps_2026-11-02.csv` |
| `logs/` | 실행 로그 | `logs/shell/pipeline_2026-11-02_2026-11-03.log` |

- 파일명 규칙: `<종류>_<수집 시작일>_<실행일>.csv`
- 키워드 `양자`는 `quantum_...`, 그 외 키워드는 `keyword_<키워드>_...` 형식
- CSV는 UTF-8(BOM) 저장으로 Excel에서 바로 열림
- 표준 컬럼: `src_platform`, `ancm_id`, `ancm_title`, `org_name`, `post_date`, `start_date`, `end_date`, `detail_url`

## 6. 다른 키워드로 다시 추출

이미 수집한 원본이 있으면 재수집 없이 키워드 추출만 가능.

```bash
cd utils
../.venv/bin/python standard_transforms.py --target-date 2026-11-02 --target-keyword "반도체"
```

- 공고 제목(`ancm_title`) 기준, 대소문자 무시
- 기존 수집 결과에 영향 없음

## 7. 사이트 하나만 수집

```bash
cd crawling
../.venv/bin/python pps_crawling.py --target-date 2026-11-02
```

파일명은 `<사이트>_crawling.py` 형식 (`bizinfo`, `iris`, `msit`, `nrf`, `ntis`, `pps`, `ordering`, `smes`, `smtech`).

## 8. 오래된 파일 정리

실행 시마다 30일 지난 파일을 `raw/`, `logs/`, `integrated/`, `result/`에서 자동 삭제함.

```bash
./cleanup_old_files.sh --dry-run          # 삭제 대상만 확인
RETENTION_DAYS=90 ./run_pipeline.sh       # 보관 기간 변경
```

- 삭제된 파일은 복구 불가. 보관할 결과는 다른 폴더로 미리 복사할 것

## 9. 정기 실행 (선택)

macOS·Linux의 `cron` 사용. 예: 매주 월요일 오전 9시 실행.

```bash
crontab -e
```

```cron
0 9 * * 1 /절대경로/Government-Crawler/run_pipeline.sh >/dev/null 2>&1
```

- PC가 켜져 있을 때만 실행됨
- 실행 결과는 `logs/shell/`에서 확인

## 10. 문제 해결

| 증상 | 확인 사항 |
| --- | --- |
| 로그에 `API Key가 ... 설정되지 않았습니다` | `env/.env` 위치와 변수명 확인 |
| API 응답 오류 / 0건 | 활용 신청 승인 여부, 일일 호출 한도 확인 |
| IRIS·NTIS·SMTECH 실패 | Chrome 설치 여부 확인 |
| `Permission denied` | `chmod +x run_pipeline.sh cleanup_old_files.sh` 실행 |
| 결과 요약에 `⚠️ 수집 데이터 없음` | 해당 기간 공고 없음 또는 사이트 구조 변경. `logs/<사이트>/` 확인 |

## 폴더 구조

```
Government-Crawler/
├── run_pipeline.sh          # 전체 실행
├── cleanup_old_files.sh     # 오래된 파일 정리
├── requirements.txt
├── env/.env.example         # API 키 양식 (복사해서 .env로 사용)
├── crawling/                # 사이트별 크롤러
├── utils/standard_transforms.py   # 통합·키워드 추출
├── raw/  integrated/  result/  logs/   # 실행 시 자동 생성 (Git 제외)
```
