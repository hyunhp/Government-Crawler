import os
import re
import glob
import hashlib
import argparse
import time
import pandas as pd
from datetime import datetime, date

today = date.today().strftime('%Y-%m-%d')

# 1. 표준 스키마 정의
STANDARD_COLUMNS = [
    'src_platform', 'ancm_id', 'ancm_title', 'org_name', 
    'post_date', 'start_date', 'end_date', 'detail_url', 
]

# 2. 매핑 설정
MAPPING_CONFIG = {
    'bizinfo': {'ancm_title': 'pblancNm', 'org_name': 'refrncNm', 'post_date': 'creatPnttm', 'detail_url': 'pblancUrl'},
    'iris': { 'ancm_id': '공고번호', 'ancm_title': '제목', 'post_date': '공고일자', 'detail_url': 'URL'},
    'msit': { 'ancm_title': 'subject', 'org_name': 'deptName', 'post_date': 'pressDt', 'detail_url': 'viewUrl'},
    'nrf': { 'ancm_title': 'title', 'post_date': 'post_date', 'detail_url': 'detail_url'},
    'ntis': { 'ancm_id': 'seq', 'ancm_title': 'title', 'org_name': 'org_name', 'start_date': 'start_date', 'end_date': 'end_date', 'detail_url': 'detail_url'},
    'pps': { 'ancm_id': 'bidNtceNo', 'ancm_title': 'bidNtceNm', 'org_name': 'ntceInsttNm', 'post_date': 'bidNtceDt', 'start_date': 'bidBeginDt', 'end_date': 'bidClseDt', 'detail_url': 'bidNtceUrl'},
    'ordering': { 'ancm_id': 'orderPlanUntyNo', 'ancm_title': 'bizNm', 'org_name': 'orderInsttNm', 'post_date': 'nticeDt', 'detail_url': 'orderPlanDtlUrl'},
    'smes': { 'ancm_title': 'pblancNm', 'org_name': 'sportInsttNm', 'post_date': 'creatDt', 'start_date': 'pblancBgnDt', 'end_date': 'pblancEndDt', 'detail_url': 'pblancDtlUrl'},
    'smtech': { 'ancm_title': 'title', 'org_name': 'project_name', 'post_date': 'post_date', 'detail_url': 'detail_url'}
}

def generate_hash_id(platform, title, date):
    if pd.isna(title) or pd.isna(date): 
        return "temp_id_" + str(int(time.time() * 1000))
    combined = f"{platform}_{title}_{date}".replace(" ", "")
    return hashlib.sha256(combined.encode()).hexdigest()[:16]

def normalize_date(date_val):
    if pd.isna(date_val) or date_val == "": return None
    clean_date = str(date_val).replace(" ", "").replace(".", "-").strip("-")
    try:
        return datetime.strptime(clean_date[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except:
        return clean_date[:10]

# -------------------------------------------------
# 3. 키워드 추출 및 result 폴더 저장 함수
# -------------------------------------------------
def save_keyword_result(df, keyword, target_date, result_dir='../result'):
    """통합 데이터에서 키워드 추출 후 result 폴더에 저장"""
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    # 키워드 검색 (대소문자 무시)
    filtered_df = df[df['ancm_title'].str.contains(keyword, na=False, case=False, regex=False)]
    
    if not filtered_df.empty:
        output_file = keyword_output_path(keyword, target_date, result_dir)
        filtered_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"🎯 키워드 '{keyword}' 추출 완료: {output_file} ({len(filtered_df)}건)")
    else:
        print(f"ℹ️ 키워드 '{keyword}'에 해당하는 공고가 없습니다.")

def keyword_output_path(keyword, target_date, result_dir):
    if keyword == '양자':
        prefix = 'quantum'
    else:
        safe_keyword = re.sub(r'[^\w-]+', '_', keyword, flags=re.UNICODE).strip('_')
        if safe_keyword != keyword:
            keyword_hash = hashlib.sha256(keyword.encode('utf-8')).hexdigest()[:8]
            safe_keyword = f"{safe_keyword or 'search'}_{keyword_hash}"
        prefix = f"keyword_{safe_keyword or 'search'}"
    return os.path.join(result_dir, f"{prefix}_{target_date}_{today}.csv")

# -------------------------------------------------
# 4. 메인 변환 프로세스
# -------------------------------------------------
def transform_all_raw_data(target_date, target_keyword, raw_dir='../raw', output_dir='../integrated', result_dir='../result'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_dfs = []

    for platform, mapping in MAPPING_CONFIG.items():
        file_pattern = os.path.join(raw_dir, platform, f"{platform}_{target_date}.csv")
        files = glob.glob(file_pattern)
        
        if not files:
            print(f"⚠️ {platform.upper()}: {target_date} 데이터 없음.")
            continue

        for file in files:
            print(f"🔄 Processing: {file}")
            try:
                df = pd.read_csv(file, encoding='utf-8-sig')
            except:
                df = pd.read_csv(file)
            
            if df.empty: continue

            # 동일 공고번호의 변경/취소공고가 여러 건이면 가장 최근 공고만 유지
            if platform == 'pps':
                before = len(df)
                df = df.sort_values('bidNtceDt').drop_duplicates(subset=['bidNtceNo'], keep='last')
                print(f"   ↳ PPS 동일 공고번호 이전 차수 제거(최신 공고만 유지): {before - len(df)}건")

            rows_list = []
            for _, row in df.iterrows():
                item = {col: None for col in STANDARD_COLUMNS}
                for std_col, raw_col in mapping.items():
                    if raw_col in row:
                        item[std_col] = row[raw_col]
                
                item['src_platform'] = platform

                # IRIS는 하나의 공고번호로 여러 사업이 공고되므로 URL의 ancmId를 붙여 구분
                if platform == 'iris' and 'URL' in row:
                    ancm_match = re.search(r'ancmId=(\w+)', str(row['URL']))
                    if ancm_match:
                        item['ancm_id'] = f"{item['ancm_id']}_{ancm_match.group(1)}"

                if platform == 'smtech' and 'period' in row:
                    p_split = str(row['period']).split(' ~ ')
                    if len(p_split) >= 2:
                        item['start_date'] = normalize_date(p_split[0])
                        item['end_date'] = normalize_date(p_split[1])

                # 발주계획은 입찰공고와 구분되도록 제목 앞에 표기
                if platform == 'ordering' and not pd.isna(item['ancm_title']):
                    item['ancm_title'] = f"[발주계획] {item['ancm_title']}"

                item['post_date'] = normalize_date(item['post_date'])
                item['start_date'] = normalize_date(item['start_date']) if item['start_date'] else None
                item['end_date'] = normalize_date(item['end_date']) if item['end_date'] else None

                if not item['ancm_id'] or pd.isna(item['ancm_id']):
                    item['ancm_id'] = generate_hash_id(platform, item['ancm_title'], item['post_date'])
                
                rows_list.append(item)

            if rows_list:
                all_dfs.append(pd.DataFrame(rows_list))

    if all_dfs:
            final_df = pd.concat(all_dfs, ignore_index=True)

            # ancm_id 중복 제거 내역을 로그에 명시 (먼저 나온 행 유지)
            dup_mask = final_df.duplicated(subset=['ancm_id'], keep='first')
            dup_df = final_df[dup_mask]
            print(f"🧹 ancm_id 중복 삭제: {len(dup_df)}건")
            for _, row in dup_df.iterrows():
                print(f"   - [{row['src_platform']}] {row['ancm_id']} | {row['ancm_title']}")

            final_df = final_df[~dup_mask]
            final_df = final_df[STANDARD_COLUMNS]

            print("📊 플랫폼별 통합 건수")
            for platform, cnt in final_df['src_platform'].value_counts().items():
                print(f"   - {platform:<10} {cnt:>6}건")
            print(f"   = 합계       {len(final_df):>6}건")

            # 1. 로컬 통합 파일 저장
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            integrated_file = f"{output_dir}/integrated_{target_date}_{today}.csv"
            final_df.to_csv(integrated_file, index=False, encoding='utf-8-sig')
            print(f"💾 통합 파일 저장: {integrated_file}")

            # 2. 로컬 키워드(양자) 추출 파일 저장
            if not os.path.exists(result_dir): os.makedirs(result_dir)
            keyword_file = keyword_output_path(target_keyword, target_date, result_dir)
            keyword_df = final_df[final_df['ancm_title'].str.contains(target_keyword, na=False, case=False, regex=False)]
            keyword_df.to_csv(keyword_file, index=False, encoding='utf-8-sig')

            print(f"🎯 키워드 '{target_keyword}' 추출: {len(keyword_df)}건 -> {keyword_file}")
            for platform, cnt in keyword_df['src_platform'].value_counts().items():
                print(f"   - {platform:<10} {cnt:>6}건")

    else:
        print(f"❌ {target_date} 데이터 처리 실패.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--target-keyword', type=str, default='양자', help='키워드 (기본: 양자)')
    args = parser.parse_args()
    transform_all_raw_data(args.target_date, args.target_keyword)