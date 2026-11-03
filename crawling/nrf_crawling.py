# UPDATED AT : 2026-03-30
# Site URL : https://www.nrf.re.kr/page/57

import os
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

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
def crawl_nrf(target_dt, end_dt):
    """한국연구재단 공지사항 수집"""
    BASE_URL = "https://www.nrf.re.kr"
    LIST_URL = "https://www.nrf.re.kr/page/57"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    df_list = []
    page = 1
    
    while True:
        params = {
            "ac": "list", "menuTypeCd": "MENU_TYPE_02", "menuNo": "57",
            "boardNo": "10", "pageNum": page, "searchType": "",
            "boardCatCd": "", "searchText": ""
        }

        logging.info(f"📄 Page {page} 수집 중...")
        try:
            res = requests.get(LIST_URL, params=params, headers=headers, timeout=10)
            if res.status_code != 200:
                logging.error(f"Status code error: {res.status_code}")
                break
        except Exception as e:
            logging.error(f"Request failed: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("div.omks--table-list tbody tr")

        if not rows:
            logging.info("데이터 행이 없습니다. 수집 종료.")
            break

        stop_flag = False
        for row in rows:
            # 제목 및 상세 URL 추출
            a_tag = row.select_one("a.table-list-link")
            if not a_tag: continue

            title = a_tag.text.strip()
            post_no = a_tag.get("data-post_no")
            detail_url = (
                f"{BASE_URL}/page/57?ac=view&searchType=&searchText=&"
                f"pageNum=1&menuNo=57&boardNo=10&menuTypeCd=MENU_TYPE_02&postNo={post_no}"
            )

            # 날짜 추출
            date_tag = row.select_one(".table-list-date")
            if not date_tag: continue
            
            date_text = date_tag.text.strip()
            try:
                created_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except:
                continue

            # 🔥 종료 조건: 목표일 "이전(<)" 데이터 도달 시
            if created_date < target_dt:
                logging.info(f"종료 조건 달성: 데이터 날짜({created_date})가 목표일({target_dt})보다 이전입니다.")
                stop_flag = True
                break

            # 수집 범위 조건 (target_dt ~ end_dt)
            if target_dt <= created_date <= end_dt:
                df_list.append({
                    "title": title,
                    "post_date": date_text,
                    "detail_url": detail_url
                })

        if stop_flag:
            break

        page += 1
        time.sleep(0.5)

    return pd.DataFrame(df_list)

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-date', type=str, required=True, help='시작 목표일 (YYYY-MM-DD)')
    args = parser.parse_args()

    # 날짜 계산
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d').date()
    end_dt = target_dt + timedelta(days=7)

    PLATFORM = "nrf"
    setup_environment(PLATFORM)

    logging.info(f"수집 범위: {target_dt} ~ {end_dt}")
    
    df = crawl_nrf(target_dt, end_dt)

    if not df.empty:
        df['src_platform'] = PLATFORM
        save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 저장 완료: {save_path} ({len(df)}건)")
    else:
        logging.warning(f"해당 범위({target_dt} ~ {end_dt})에 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()