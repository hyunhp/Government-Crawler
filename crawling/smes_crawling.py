# UPDATED AT : 2026-03-30
# API Guide : https://www.smes.go.kr/main/dbCnrs#

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
def crawl_smes(target_dt, end_dt, service_key):
    """중소벤처24 공공데이터 API 수집"""
    # API 날짜 포맷 설정 (YYYYMMDD)
    str_dt = target_dt.strftime('%Y%m%d')
    end_dt_str = end_dt.strftime('%Y%m%d')
    
    api_prefix = 'https://www.smes.go.kr/fnct/apiReqst/extPblancInfo?'
    api_url = f"{api_prefix}token={service_key}&strDt={str_dt}&endDt={end_dt_str}"
    
    df_list = []
    
    try:
        logging.info(f"API 요청 전송: {api_url.split('token=')[0]}...") # 토큰 제외 로깅
        response = requests.get(api_url, timeout=20)
        
        if response.status_code != 200:
            logging.error(f"API Error: {response.status_code}")
            return pd.DataFrame()

        json_response = response.json()
        crawling_list = json_response.get('data', [])

        if not crawling_list:
            logging.info("해당 기간에 수집된 데이터가 없습니다.")
            return pd.DataFrame()

        # 수집 필드 정의
        column_list = [
            'pblancNm', 'sportTrget', 'sportInsttNm', 'reqstRcept', 'refrnc', 
            'pblancBgnDt', 'pblancEndDt', 'creatDt', 'pblancDtlUrl'
        ]

        for crawled in crawling_list:
            crawled_dict = dict()
            for key in column_list:
                try:
                    val = crawled.get(key)
                    # 🔥 Bizinfo 상세 URL 중복 제거 및 보정 로직
                    if key == 'pblancDtlUrl' and val:
                        val = 'https://www.bizinfo.go.kr' + val.replace('https://www.bizinfo.go.kr', '')
                    
                    crawled_dict[key] = val
                except Exception:
                    crawled_dict[key] = None
            df_list.append(crawled_dict)

        logging.info(f"API 응답 수집 완료: {len(df_list)}건")

    except Exception as e:
        logging.error(f"수집 중 에러 발생: {e}")

    return pd.DataFrame(df_list)

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    # 날짜를 인자로 변경
    parser.add_argument('--target-date', type=str, required=True, help='시작일 (YYYY-MM-DD)')
    args = parser.parse_args()

    # 날짜 처리 (입력일로부터 7일치)
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d')
    end_dt = target_dt + timedelta(days=7)

    PLATFORM = "smes"
    setup_environment(PLATFORM)
    
    # .env에서 API 키 로드
    load_dotenv('../env/.env')
    service_key = os.getenv('smes_api')
    
    if not service_key:
        logging.critical("API Key(smes_api)가 .env에 설정되지 않았습니다.")
        return

    logging.info(f"수집 범위: {target_dt.date()} ~ {end_dt.date()}")
    df = crawl_smes(target_dt, end_dt, service_key)

    if not df.empty:
        # 데이터 표준화: 출처 컬럼 추가
        df['src_platform'] = PLATFORM
        save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 저장 완료: {save_path} ({len(df)}건)")
    else:
        logging.warning("수집된 데이터가 최종적으로 비어있습니다.")

if __name__ == "__main__":
    main()