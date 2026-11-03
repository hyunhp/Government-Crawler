# UPDATED AT : 2026-03-30
# IRIS 사이트 : https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do

import os
import time
import re
import logging
import argparse
from datetime import datetime

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

def setup_driver():
    """셀레니움 드라이버 초기화"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    return webdriver.Chrome(options=options)

# -------------------------------------------------
# 2. 크롤링 핵심 로직
# -------------------------------------------------
def crawl_iris(driver, wait):
    """IRIS 공고 목록 수집"""
    results = []
    page = 1
    MAX_PAGE = 10  # 최대 페이지 수 제한 
    
    # 접수중 탭 클릭
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > nav > ul")))
        active_tab = driver.find_element(By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > nav > ul > li.active > a")
        driver.execute_script("arguments[0].click();", active_tab)
        time.sleep(2)
        logging.info("접수중 탭 선택 완료")
    except Exception as e:
        logging.warning(f"탭 선택 실패(기본값 진행): {e}")

    while True:
        if page > MAX_PAGE:
            logging.warning("최대 페이지 수 초과, 크롤링 종료")
            break

        logging.info(f"📄 Page {page} 수집 중...")
        
        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > div.tstyle.list.biz_announce > ul > li"))
            )
            items = driver.find_elements(By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > div.tstyle.list.biz_announce > ul > li")
        except Exception as e:
            logging.error(f"목록 로드 실패: {e}")
            break

        for idx in range(len(items)):
            try:
                # DOM 재참조
                items = driver.find_elements(By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > div.tstyle.list.biz_announce > ul > li")
                item = items[idx]

                # 데이터 추출
                title_tag = item.find_element(By.CSS_SELECTOR, "a")
                title = title_tag.text.strip()
                group = item.find_element(By.CSS_SELECTOR, "div.group1 > div")

                ancm_no = group.find_element(By.CSS_SELECTOR, "span:nth-child(1)").text.replace("공고번호 :", "").strip()
                ancm_date = group.find_element(By.CSS_SELECTOR, "span.ancmDe").text.replace("공고일자 :", "").strip()
                ancm_status = group.find_element(By.CSS_SELECTOR, "span.rcveSttSeNmLst").text.replace("공고상태 :", "").strip()
                ancm_type = group.find_element(By.CSS_SELECTOR, "span.pbofrTpSeNmLst").text.replace("공모유형 :", "").strip()

                # URL 파싱 로직
                href = title_tag.get_attribute("href") or ""
                onclick = title_tag.get_attribute("onclick") or ""
                target = href if "fnView" in href else onclick
                match = re.findall(r"'(.*?)'", target)
                detail_url = f"https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId={match[0]}" if match else None

                results.append({
                    "제목": title,
                    "공고번호": ancm_no,
                    "공고일자": ancm_date,
                    "공고상태": ancm_status,
                    "공모유형": ancm_type,
                    "URL": detail_url
                })
            except Exception as e:
                logging.error(f"항목 파싱 에러 (Page {page}, Index {idx}): {e}")
                continue

        # 다음 페이지 이동
        try:
            pager = driver.find_element(By.CSS_SELECTOR, "#bsnsAncmBtinSituListForm > div.board_pager > div > div")
            current = pager.find_element(By.CSS_SELECTOR, "a.page_now")
            next_btn = current.find_element(By.XPATH, "following-sibling::a[1]")
            
            driver.execute_script("arguments[0].click();", next_btn)
            wait.until(EC.staleness_of(items[0]))
            time.sleep(1)
            page += 1
        except Exception:
            logging.info("마지막 페이지 도달")
            break
            
    return results

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-date', type=str, required=True, help='YYYY-MM-DD')
    args = parser.parse_args()
    
    PLATFORM = "iris"
    setup_environment(PLATFORM)
    
    url = "https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do"
    driver = setup_driver()
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)
        data = crawl_iris(driver, wait)
        
        if data:
            df = pd.DataFrame(data)
            df['src_platform'] = PLATFORM
            save_file = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
            df.to_csv(save_file, index=False, encoding="utf-8-sig")
            logging.info(f"✅ 수집 완료: {len(df)}건 저장됨 -> {save_file}")
        else:
            logging.warning("수집된 데이터가 없습니다.")
            
    except Exception as e:
        logging.critical(f"프로그램 중단 에러: {e}")
    finally:
        driver.quit()
        logging.info("드라이버 종료 및 프로세스 마감")

if __name__ == "__main__":
    main()