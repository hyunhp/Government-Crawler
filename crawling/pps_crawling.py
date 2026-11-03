# UPDATED AT : 2026-03-30
# API Guide : https://www.data.go.kr/data/15129394/openapi.do#/

import os
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# -------------------------------------------------
# 1. 환경 및 로깅 설정
# -------------------------------------------------
def setup_environment(platform_name):
    """폴더 생성 및 로깅 설정"""
    dirs = [f'../raw/{platform_name}', f'../logs/{platform_name}']
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

    log_filename = f"../logs/{platform_name}/{platform_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"{platform_name.upper()} 크롤러 시작")

# -------------------------------------------------
# 2. 크롤링 핵심 로직
# -------------------------------------------------
def crawl_pps(target_dt, end_dt, service_key):
    """조달청 5개 카테고리 입찰공고 수집"""
    api_prefix = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService'
    
    # 카테고리별 엔드포인트 정의
    api_dict = {
        'product': '/getBidPblancListInfoThng',
        'service': '/getBidPblancListInfoServc',
        'foreign': '/getBidPblancListInfoFrgcpt',
        'construction': '/getBidPblancListInfoCnstwk',
        'etc': '/getBidPblancListInfoEtc'
    }
    
    # API 날짜 포맷 설정 (YYYYMMDDHHMM)
    target_date_api = target_dt.strftime('%Y%m%d') + '0000'
    end_date_api = end_dt.strftime('%Y%m%d') + '2359' # 종료일 끝까지 수집
    
    num_of_rows = 999
    all_data = []

    for category, endpoint in api_dict.items():
        logging.info(f"🚀 카테고리 수집 시작: {category.upper()}")
        idx, total_count, iteration_count = 1, None, None
        
        while True:
            api_url = (
                f"{api_prefix}{endpoint}?serviceKey={service_key}&type=json"
                f"&inqryBgnDt={target_date_api}&inqryEndDt={end_date_api}"
                f"&inqryDiv=1&numOfRows={num_of_rows}&pageNo={idx}"
            )
            
            try:
                response = requests.get(api_url, timeout=20)
                if response.status_code != 200:
                    logging.error(f"[{category}] API Error {response.status_code}")
                    break
                
                res_json = response.json().get('response', {})
                body = res_json.get('body', {})
                items = body.get('items', [])
                
                # 첫 페이지에서 총 개수 및 반복 횟수 계산
                if total_count is None:
                    total_count = body.get('totalCount', 0)
                    iteration_count = (total_count // num_of_rows) + 1
                    logging.info(f"[{category}] 총 건수: {total_count}, 예상 페이지: {iteration_count}")

                if not items:
                    logging.info(f"[{category}] 더 이상 수집할 데이터가 없습니다.")
                    break

                # 표준 컬럼 추출
                column_list = [
                    'bidNtceNo', 'ntceKindNm', 'bidNtceDt', 'bidNtceNm', 
                    'ntceInsttNm', 'dminsttNm', 'bidBeginDt', 'bidClseDt', 'bidNtceUrl'
                ]

                for item in items:
                    crawled_dict = {col: item.get(col) for col in column_list}
                    # 공사(construction)는 bidNtceUrl이 빈 값으로 오고 bidNtceDtlUrl에 상세 링크가 담겨 옴
                    crawled_dict['bidNtceUrl'] = item.get('bidNtceUrl') or item.get('bidNtceDtlUrl')
                    crawled_dict['category'] = category
                    all_data.append(crawled_dict)

                logging.info(f"[{category}] {idx}/{iteration_count} 페이지 완료")
                
                if idx >= iteration_count:
                    break
                
                idx += 1
                time.sleep(1) # 서버 부하 방지

            except Exception as e:
                logging.error(f"[{category}] 수집 중 예외 발생: {e}")
                break
                
    return pd.DataFrame(all_data)

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-date', type=str, required=True, help='시작일 (YYYY-MM-DD)')
    parser.add_argument('--target-keyword', type=str, default='양자', help='키워드 (기본: 양자)')
    args = parser.parse_args()

    # 날짜 처리 (입력일로부터 7일치)
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d')
    end_dt = target_dt + timedelta(days=7)

    PLATFORM = "pps"
    setup_environment(PLATFORM)
    
    # .env에서 API 키 로드
    load_dotenv('../env/.env')
    service_key = os.getenv('pps_api')
    
    if not service_key:
        logging.critical("API Key가 .env에 설정되지 않았습니다.")
        return

    logging.info(f"수집 범위: {target_dt.date()} ~ {end_dt.date()}")
    df = crawl_pps(target_dt, end_dt, service_key)

    if not df.empty:
        df['src_platform'] = PLATFORM
        save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 수집 완료: 총 {len(df)}건 저장 -> {save_path}")
    else:
        logging.warning("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()