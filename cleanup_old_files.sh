#!/bin/bash
# 보관 기간(기본 30일)이 지난 로그/데이터 파일 삭제
# - run_pipeline.sh 실행 시작 시 자동 호출
# - 보관 기간 변경: RETENTION_DAYS=60 ./cleanup_old_files.sh
#
# 사용법: ./cleanup_old_files.sh [--dry-run]
#   --dry-run : 삭제하지 않고 대상만 출력
#
# ※ 로컬 파일만 존재하므로 삭제 시 복구 불가 (보관이 필요한 결과는 별도 위치로 복사)

BASE_DIR=$(cd "$(dirname "$0")" && pwd)
RETENTION_DAYS=${RETENTION_DAYS:-30}
TARGET_DIRS=(logs raw integrated result)

DRY_RUN=false
[ "$1" == "--dry-run" ] && DRY_RUN=true

echo "[$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S')] 🧹 오래된 파일 정리 (보관 기간: ${RETENTION_DAYS}일, dry-run: $DRY_RUN)"

total=0
for d in "${TARGET_DIRS[@]}"; do
    dir="$BASE_DIR/$d"
    [ -d "$dir" ] || continue

    count=$(find "$dir" -type f -mtime +"$RETENTION_DAYS" | wc -l)
    if [ "$count" -gt 0 ] && [ "$DRY_RUN" == false ]; then
        find "$dir" -type f -mtime +"$RETENTION_DAYS" -delete
    fi

    printf '   - %-11s %5s개\n' "$d" "$count"
    total=$((total + count))
done

if [ "$DRY_RUN" == true ]; then
    echo "   = 삭제 대상 합계 ${total}개 (dry-run: 실제 삭제 안 함)"
else
    echo "   = 삭제 완료 ${total}개"
fi
