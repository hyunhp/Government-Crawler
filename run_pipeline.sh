#!/bin/bash
# 사용법: ./run_pipeline.sh [시작일자 YYYY-MM-DD]
# - 시작일자 미입력 시 지난주 월요일부터 일주일치 크롤링 수행
# - 인스턴스 부팅 시 crontab(@reboot)으로 자동 실행됨

# 스크립트 위치 기준으로 실행 (cron 실행 위치와 무관하게 동작)
# 셸/파이썬 로그 시간을 모두 KST로 통일
export TZ=Asia/Seoul
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# 1. 대상 날짜 설정
TARGET_DATE=$1
TODAY=$(TZ=Asia/Seoul date +%Y-%m-%d)
if [ -z "$TARGET_DATE" ]; then
    TARGET_DATE=$(TZ=Asia/Seoul date -d "last monday" +%Y-%m-%d)
fi

# 2. 로깅 설정: stdout/stderr 모두 콘솔과 로그 파일에 기록
# 파일명 예시: logs/shell/pipeline_2026-09-21_2026-09-28.log (크롤링 시작일자_실행일자)
mkdir -p logs/shell
TOTAL_LOG="logs/shell/pipeline_${TARGET_DATE}_${TODAY}.log"
exec > >(tee -a "$TOTAL_LOG") 2>&1
TEE_PID=$!

# 최종 로그 S3 업로드 경로: s3://government-crawled-bucket/logs/YYYY/MM/ (실행일자 기준)
S3_LOG_URI="s3://government-crawled-bucket/logs/${TODAY:0:4}/${TODAY:5:2}/$(basename "$TOTAL_LOG")"

# 3. 사용할 파이썬 경로 설정 (print 출력이 로그 순서대로 남도록 버퍼링 해제)
PYTHON_BIN="python3.11"
export PYTHONUNBUFFERED=1

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
    elif [ ! -f "$raw_file" ] || [ "$(stat -c %Y "$raw_file")" -lt "$STEP_START_EPOCH" ]; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        STEP_RESULT="⚠️  수집 데이터 없음"
    else
        local rows
        rows=$($PYTHON_BIN -c "import sys, pandas as pd; print(len(pd.read_csv(sys.argv[1])))" "$raw_file" 2>/dev/null)
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
echo "  - 로그 파일   : $TOTAL_LOG"

# 4. 오래된 로그/데이터 정리 (인스턴스 시작 시점)
section "STEP 1. 오래된 파일 정리"
run_step "cleanup" ./cleanup_old_files.sh
step_result
add_summary "cleanup"

# 5. 크롤링 단계 (Crawling)
section "STEP 2. 크롤링 (${#CRAWLERS[@]}개 사이트)"
for platform in "${CRAWLERS[@]}"; do
    run_step "$platform" bash -c "cd crawling && $PYTHON_BIN ${platform}_crawling.py --target-date '$TARGET_DATE'"
    crawl_result "$platform"
    add_summary "$platform"
done

# 6. 데이터 통합 및 변환 단계 (Utils)
section "STEP 3. 데이터 통합 및 S3 업로드"
run_step "transform" bash -c "cd utils && $PYTHON_BIN standard_transforms.py --target-date '$TARGET_DATE'"
step_result
add_summary "transform"

# 7. 결과 요약
section "★ 파이프라인 요약 $(now)"
echo "단계            소요   결과"
echo "----------------------------------------------------------------"
for line in "${SUMMARY[@]}"; do
    echo "$line"
done
echo "----------------------------------------------------------------"
echo "총 소요 시간: $(( (SECONDS - PIPELINE_START) / 60 ))분 $(( (SECONDS - PIPELINE_START) % 60 ))초 / 실패·경고: ${FAIL_COUNT}건"
echo "최종 로그 업로드: $S3_LOG_URI"
echo "모든 작업을 마쳤습니다. AWS 외부 스케줄러에 의해 곧 종료될 예정입니다."

# 8. 최종 로그 S3 업로드: 요약까지 파일에 모두 기록되도록 tee 종료를 기다린 뒤 업로드
exec >&- 2>&-
wait "$TEE_PID"
if aws s3 cp "$TOTAL_LOG" "$S3_LOG_URI" --only-show-errors >> "$TOTAL_LOG" 2>&1; then
    echo "[$(now)] 🚀 S3 로그 업로드 성공" >> "$TOTAL_LOG"
else
    echo "[$(now)] ❌ S3 로그 업로드 실패" >> "$TOTAL_LOG"
fi
