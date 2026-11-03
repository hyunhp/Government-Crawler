# 정부 R&D 과제·공고 크롤러

정부 지원사업, 연구개발 과제, 입찰공고를 사이트별로 수집하고 표준 CSV로 통합하는 저장소입니다. 기존 크롤러와 실행 순서를 유지하며, 인증키와 수집 데이터는 Git에 포함하지 않습니다.

## 수집 대상

| 플랫폼 | 수집 방식 | API 키 환경변수 | API 안내 |
| --- | --- | --- | --- |
| Bizinfo | OpenAPI | `bizinfo_api` | [Bizinfo OpenAPI 안내](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi) |
| IRIS | 웹 페이지 수집 (Selenium) | 없음 | [IRIS 공고 목록](https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do) |
| MSIT | 공공데이터포털 OpenAPI | `msit_api` | [과기정통부 사업공고 API](https://www.data.go.kr/data/15074634/openapi.do) |
| NRF | 웹 페이지 수집 (requests) | 없음 | [한국연구재단 공지](https://www.nrf.re.kr/page/57) |
| NTIS | 웹 페이지 수집 (Selenium) | 없음 | [NTIS 사업공고](https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do) |
| 나라장터 입찰 (PPS) | 공공데이터포털 OpenAPI | `pps_api` | [입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do) |
| 나라장터 발주계획 | 공공데이터포털 OpenAPI | `g2b_ordering_api` | [발주계획현황서비스](https://www.data.go.kr/data/15129462/openapi.do) |
| 중소벤처24 (SMES) | OpenAPI | `smes_api` | [중소벤처24 OpenAPI 안내](https://www.smes.go.kr/main/dbCnrs) |
| SMTECH | 웹 페이지 수집 (Selenium) | 없음 | [SMTECH 사업공고](https://www.smtech.go.kr/front/ifg/no/notice02_list.do) |

## 준비

- Python 3.11
- Selenium으로 수집하는 IRIS, NTIS, SMTECH용 Chrome/Chromium 브라우저
- S3 업로드를 사용하는 경우 AWS CLI와 적절한 IAM 권한 또는 AWS 자격 증명

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp env/.env.example env/.env
```

API 키가 필요한 플랫폼은 위 표의 API 안내 페이지에서 계정 로그인 후 해당 API의 활용 신청을 진행합니다. 승인 상태와 호출 한도를 확인하고 발급된 인증키를 `env/.env.example`에 적힌 동일한 변수명으로 `env/.env`에 입력하세요. 공공데이터포털 API는 각 서비스 페이지에서 활용 신청을 해야 하며, Bizinfo와 중소벤처24는 해당 서비스의 API 안내/신청 절차를 따릅니다. 사이트 구조에 따라 별도 API 키가 필요 없는 크롤러도 있습니다.

`.env` 파일은 `.gitignore`에 포함되어 있으므로 실제 키 값을 소스 코드나 README에 넣지 마세요. 키를 발급받은 뒤 API 문서에 표시된 인증키 형식과 사용 승인 상태를 확인하세요. AWS 자격 증명은 `.env`에 넣지 말고 인스턴스 IAM 역할 또는 AWS 표준 자격 증명 프로필을 사용하세요.

## 전체 수집 및 통합

저장소 루트에서 파이프라인을 실행합니다.

```bash
./run_pipeline.sh
# 또는 시작일을 지정
./run_pipeline.sh 2026-11-02
```

날짜를 생략하면 스크립트가 지난주 월요일을 시작일로 선택합니다. 각 플랫폼 크롤러를 `bizinfo`, `iris`, `msit`, `nrf`, `ntis`, `pps`, `ordering`, `smes`, `smtech` 순서로 실행한 뒤 표준 변환을 수행합니다. 각 사이트는 기존 코드의 날짜 종료 조건과 페이지 처리 방식을 따르므로, 실제 수집 종료 시점은 사이트별로 다를 수 있습니다.

단계를 따로 실행할 수도 있습니다.

```bash
cd crawling
python3.11 bizinfo_crawling.py --target-date 2026-11-02
cd ..

cd utils
python3.11 standard_transforms.py --target-date 2026-11-02
```

수집 원본은 `raw/<platform>/<platform>_<시작일>.csv`에, 표준 통합본은 `integrated/`에 저장됩니다. 로그는 `logs/`에 기록됩니다. 표준 스키마는 `src_platform`, `ancm_id`, `ancm_title`, `org_name`, `post_date`, `start_date`, `end_date`, `detail_url`입니다.

## 키워드 검색 및 별도 저장

표준 변환 시 제목(`ancm_title`)에 포함된 검색어를 대소문자 구분 없이 찾아 `result/`에 별도 CSV로 저장합니다. 기본 검색어는 `양자`입니다.

```bash
cd utils
python3.11 standard_transforms.py \
  --target-date 2026-11-02 \
  --target-keyword "양자컴퓨터"
```

기본 검색어의 결과 파일명은 기존 호환성을 위해 `quantum_<시작일>_<실행일>.csv`를 사용합니다. 다른 검색어는 `keyword_<검색어>_<시작일>_<실행일>.csv` 형식으로 저장되며, 파일명에 쓸 수 없는 문자는 안전하게 변환하고 충돌 방지용 식별자를 덧붙입니다. 이미 원본 CSV가 있다면 크롤러를 다시 실행하지 않고 위 변환 명령만 실행해 다른 키워드 결과를 만들 수 있습니다.

키워드 검색은 통합 데이터의 공고 제목을 대상으로 하며, 원본 수집 API 요청 조건을 변경하지 않습니다.

## 저장 및 운영 참고

- 변환 스크립트는 통합본을 S3 `integrated/` 경로에 업로드하고, 검색 결과가 있을 때 S3 `result/` 경로에도 업로드합니다. 현재 버킷 이름은 `government-crawled-bucket`으로 코드에 설정되어 있습니다.
- 파이프라인 로그는 실행 후 S3 `logs/연도/월/` 경로에 업로드합니다. S3 업로드를 사용하지 않는 환경은 AWS 자격 증명과 네트워크 설정을 먼저 확인하세요.
- `./cleanup_old_files.sh --dry-run`으로 30일 보관 정책의 삭제 대상을 먼저 확인할 수 있습니다. 일반 실행은 `raw/`, `logs/`, `integrated/`, `result/`의 오래된 파일을 삭제합니다. 원본 및 사이트별 로그는 재생성할 수 있는 백업이 아니므로 보관 정책에 유의하세요.
- `.gitignore`는 `.env`, 원본/결과 CSV, 로그, 캐시를 제외합니다. API 키나 수집 데이터를 커밋하지 마세요.

## EC2 자동 실행 (선택)

부팅 시 전체 파이프라인을 실행하려면 `crontab -e`에 저장소 절대경로를 등록합니다.

```cron
@reboot cd /home/ec2-user/government-rnd-crawler && ./run_pipeline.sh >/dev/null 2>&1
```

종료 시 오래된 파일을 정리하는 systemd 예시는 `deploy/crawl-cleanup.service.example`에 있습니다. 저장소 위치와 사용자에 맞게 경로를 수정한 뒤 설치하고, `logs/shell/` 디렉터리가 있는지 확인하세요.
