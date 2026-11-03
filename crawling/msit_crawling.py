# UPDATED AT : 2026-03-30
# API Guide : https://www.data.go.kr/data/15074634/openapi.do#/tab_layer_detail_function

import os
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime
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
def crawl_msit(target_date, service_key):
    """과학기술정보통신부 API 수집"""
    api_prefix = 'http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList?serviceKey='
    api_suffix = '&numOfRows=10&pageNo='
    api_format = '&returnType=json'
    
    df_list = []
    idx = 1
    
    while True:
        api_url = f"{api_prefix}{service_key}{api_suffix}{idx}{api_format}"
        try:
            response = requests.get(api_url, timeout=15)
            if response.status_code != 200:
                logging.error(f"API Error: {response.status_code}")
                break
            
            json_response = response.json().get('response', [])
            #에 따라 [1]번 인덱스의 body 데이터 추출
            if len(json_response) < 2:
                logging.info("수집할 데이터가 더 이상 없습니다.")
                break
                
            crawling_list = json_response[1]['body']['items']
            # 수집 대상 컬럼 정의
            column_list = ['subject', 'viewUrl', 'deptName', 'managerName', 'managerTel', 'pressDt']

            if not crawling_list:
                logging.info("Page 데이터가 비어 있습니다.")
                break

            for crawled in crawling_list:
                crawled_dict = dict()
                for key in column_list:
                    try:
                        # 구조에 맞게 item 키 내부 데이터 접근
                        crawled_dict[key] = crawled['item'][key]
                    except KeyError:
                        crawled_dict[key] = None
                df_list.append(crawled_dict)

            # 종료 조건 확인
            if crawled_dict['pressDt']:
                press_date = datetime.strptime(crawled_dict['pressDt'], '%Y-%m-%d').date()
                if press_date < target_date:
                    logging.info(f"종료 조건 달성: 마지막 게시일({press_date})이 목표일({target_date}) 이전입니다.")
                    break

            logging.info(f"Page {idx} 완료 (누적 {len(df_list)}건)")
            idx += 1
            time.sleep(0.5) # API 부하 방지

        except Exception as e:
            logging.error(f"수집 중 예상치 못한 에러 발생: {e}")
            break

    return pd.DataFrame(df_list)

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    #의 하드코딩된 날짜를 인자값으로 대체
    parser.add_argument('--target-date', type=str, required=True, help='YYYY-MM-DD')
    args = parser.parse_args()
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d').date()

    PLATFORM = "msit"
    setup_environment(PLATFORM)
    
    # 환경변수에서 API 키 로드
    load_dotenv('../env/.env')
    service_key = os.getenv('msit_api')
    
    if not service_key:
        logging.critical("API Key가 .env 파일에 설정되지 않았습니다.")
        return

    df = crawl_msit(target_dt, service_key)

    if not df.empty:
        # 데이터 표준화: 출처 컬럼 추가
        df['src_platform'] = PLATFORM
        save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 저장 완료: {save_path} ({len(df)}건)")
    else:
        logging.warning("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()