#!/bin/bash
# 사용법: ./run_pipeline.sh [시작일자 YYYY-MM-DD] [검색 키워드]
# - 시작일자 미입력 시 지난주 월요일부터 일주일치 크롤링 수행
# - 검색 키워드 미입력 시 '양자'

# 스크립트 위치 기준으로 실행 (cron 실행 위치와 무관하게 동작)
# 셸/파이썬 로그 시간을 모두 KST로 통일
export TZ=Asia/Seoul
cd "$(dirname "$0")" || exit 1

# 1. 사용할 파이썬 경로 설정 (print 출력이 로그 순서대로 남도록 버퍼링 해제)
# 우선순위: PYTHON_BIN 환경변수 > 저장소의 .venv > python3.11 > python3
if [ -z "$PYTHON_BIN" ]; then
    if [ -x .venv/bin/python ]; then
        PYTHON_BIN="$PWD/.venv/bin/python"
    elif command -v python3.11 >/dev/null 2>&1; then
        PYTHON_BIN="python3.11"
    else
        PYTHON_BIN="python3"
    fi
fi
export PYTHONUNBUFFERED=1

# 2. 대상 날짜 설정 (Linux/macOS 공통으로 동작하도록 파이썬으로 계산)
TARGET_DATE=$1
TARGET_KEYWORD=${2:-양자}
TODAY=$(date +%Y-%m-%d)
if [ -z "$TARGET_DATE" ]; then
    # 지난주 월요일 (오늘이 월요일이면 7일 전)
    TARGET_DATE=$("$PYTHON_BIN" -c "import datetime as d; t=d.date.today(); print(t - d.timedelta(days=t.weekday() or 7))")
fi

# 3. 로깅 설정: stdout/stderr 모두 콘솔과 로그 파일에 기록
# 파일명 예시: logs/shell/pipeline_2026-09-21_2026-09-28.log (크롤링 시작일자_실행일자)
mkdir -p logs/shell
TOTAL_LOG="logs/shell/pipeline_${TARGET_DATE}_${TODAY}.log"
exec > >(tee -a "$TOTAL_LOG") 2>&1
TEE_PID=$!

# 크롤러 실행 순서
CRAWLERS=(bizinfo iris msit nrf ntis pps ordering smes smtech)

# -------------------------------------------------
# 로그 출력 헬퍼
# -------------------------------------------------
now() { date '+%Y-%m-%d %H:%M:%S'; }

section() {
    echo
    echo "================================================================"
    echo "  $1"
    echo "================================================================"
}

SUMMARY=()
FAIL_COUNT=0

# run_step <단계명> <명령...> : 단계 시작/종료 구분선과 결과(성공 여부, 소요 시간)를 기록
run_step() {
    local name=$1; shift
    local start=$SECONDS
    STEP_START_EPOCH=$(date +%s)

    echo
    echo "▶ [$name] 시작 ($(now))"
    echo "----------------------------------------------------------------"
    "$@"
    STEP_RC=$?
    STEP_ELAPSED=$((SECONDS - start))
    echo "----------------------------------------------------------------"
    if [ $STEP_RC -eq 0 ]; then
        echo "■ [$name] 종료: ✅ 성공 (${STEP_ELAPSED}초)"
    else
        echo "■ [$name] 종료: ❌ 실패 exit=$STEP_RC (${STEP_ELAPSED}초)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 단계 결과 문구를 STEP_RESULT에 설정
step_result() {
    if [ $STEP_RC -eq 0 ]; then STEP_RESULT="✅ 완료"; else STEP_RESULT="❌ 실패(exit $STEP_RC)"; fi
}

# 크롤러 결과 문구를 STEP_RESULT에 설정: 이번 실행에서 생성된 raw 파일의 건수 확인
crawl_result() {
    local platform=$1
    local raw_file="raw/$platform/${platform}_${TARGET_DATE}.csv"

    if [ $STEP_RC -ne 0 ]; then
        STEP_RESULT="❌ 실패(exit $STEP_RC)"
    elif [ ! -f "$raw_file" ] || [ "$("$PYTHON_BIN" -c "import os, sys; print(int(os.path.getmtime(sys.argv[1])))" "$raw_file")" -lt "$STEP_START_EPOCH" ]; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        STEP_RESULT="⚠️  수집 데이터 없음"
    else
        local rows
        rows=$("$PYTHON_BIN" -c "import sys, pandas as pd; print(len(pd.read_csv(sys.argv[1])))" "$raw_file" 2>/dev/null)
        STEP_RESULT="✅ ${rows:-?}건"
    fi
}

add_summary() {
    SUMMARY+=("$(printf '%-12s %5s초   %s' "$1" "$STEP_ELAPSED" "$STEP_RESULT")")
}

# -------------------------------------------------
# 파이프라인 시작
# -------------------------------------------------
PIPELINE_START=$SECONDS
section "★ 파이프라인 시작 $(now)"
echo "  - 파이썬      : $PYTHON_BIN"
echo "  - 크롤링 기간 : $TARGET_DATE ~ (7일간)"
echo "  - 검색 키워드 : $TARGET_KEYWORD"
echo "  - 로그 파일   : $TOTAL_LOG"

# 5. 오래된 로그/데이터 정리
section "STEP 1. 오래된 파일 정리"
run_step "cleanup" ./cleanup_old_files.sh
step_result
add_summary "cleanup"

# 6. 크롤링 단계 (Crawling)
section "STEP 2. 크롤링 (${#CRAWLERS[@]}개 사이트)"
for platform in "${CRAWLERS[@]}"; do
    run_step "$platform" bash -c "cd crawling && \"$PYTHON_BIN\" ${platform}_crawling.py --target-date '$TARGET_DATE'"
    crawl_result "$platform"
    add_summary "$platform"
done

# 7. 데이터 통합 및 변환 단계 (Utils)
section "STEP 3. 데이터 통합 및 키워드 추출"
run_step "transform" bash -c "cd utils && \"\$0\" standard_transforms.py --target-date \"\$1\" --target-keyword \"\$2\"" "$PYTHON_BIN" "$TARGET_DATE" "$TARGET_KEYWORD"
step_result
add_summary "transform"

# 8. 결과 요약
section "★ 파이프라인 요약 $(now)"
echo "단계            소요   결과"
echo "----------------------------------------------------------------"
for line in "${SUMMARY[@]}"; do
    echo "$line"
done
echo "----------------------------------------------------------------"
echo "총 소요 시간: $(( (SECONDS - PIPELINE_START) / 60 ))분 $(( (SECONDS - PIPELINE_START) % 60 ))초 / 실패·경고: ${FAIL_COUNT}건"
echo "통합 결과: integrated/ / 키워드 결과: result/ / 로그: $TOTAL_LOG"

# 요약까지 로그 파일에 모두 기록되도록 tee 종료 대기
exec >&- 2>&-
wait "$TEE_PID"
