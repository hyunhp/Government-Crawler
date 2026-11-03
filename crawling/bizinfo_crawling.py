# UPDATED AT : 2026-03-30
# API Guide : https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi

import os
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

def setup_logging(target_date):
    """로깅 설정: 콘솔과 파일에 동시 기록"""
    if not os.path.exists('../logs/bizinfo'):
        os.makedirs('../logs/bizinfo')
    
    log_filename = f"../logs/bizinfo/bizinfo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler() # 콘솔 출력도 유지
        ]
    )

def crawl_bizinfo(target_date, service_key):
    """비즈인포 API 수집 핵심 로직"""
    api_prefix = 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?'
    df_list = []
    idx = 1
    
    while True:
        api_url = f"{api_prefix}&dataType=json&pageUnit=10&pageIndex={idx}&crtfcKey={service_key}"
        response = requests.get(api_url)
        
        if response.status_code != 200:
            logging.error(f"API Error: {response.status_code}")
            break

        crawling_list = response.json().get('jsonArray', [])
        if not crawling_list:
            logging.info("수집할 데이터가 더 이상 없습니다.")
            break

        # 컬럼 정의
        column_list = ['creatPnttm', 'pblancNm', 'pblancUrl', 'bsnsSumryCn', 'refrncNm', 'fileNm', 'flpthNm']

        for crawled in crawling_list:
            crawled_dict = {key: crawled.get(key) for key in column_list}
            df_list.append(crawled_dict)

        # 날짜 비교 및 종료 조건
        last_item_date_str = crawling_list[-1].get('creatPnttm')
        if last_item_date_str:
            last_date = datetime.strptime(last_item_date_str, "%Y-%m-%d %H:%M:%S").date()
            if last_date < target_date:
                logging.info(f"종료 조건 달성: 마지막 데이터 날짜({last_date})가 목표 날짜({target_date}) 이전입니다.")
                break

        logging.info(f"Page {idx} 완료 (현재까지 {len(df_list)}건 수집)")
        idx += 1
        time.sleep(1)

    return pd.DataFrame(df_list)

def main():
    # 1. Argument 처리
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--target-date', type=str, required=True,
        help='크롤링 목표 날짜 (YYYY-MM-DD 형식), 해당 날짜 이후의 데이터만 수집됩니다.')
    args = parser.parse_args()
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d').date()

    # 2. 환경 설정
    setup_logging(args.target_date)
    load_dotenv('../env/.env')
    service_key = os.getenv('bizinfo_api')
    
    if not os.path.exists('../raw/bizinfo'):
        os.makedirs('../raw/bizinfo')

    # 3. 크롤링 시작
    logging.info(f"Bizinfo 크롤링 시작 (목표 날짜: {target_dt})")
    df = crawl_bizinfo(target_dt, service_key)

    # 4. 저장
    if not df.empty:
        df['src_platform'] = 'bizinfo'
        save_path = f'../raw/bizinfo/bizinfo_{target_dt}.csv'
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logging.info(f"저장 완료: {save_path} ({len(df)}건)")
    else:
        logging.warning("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()