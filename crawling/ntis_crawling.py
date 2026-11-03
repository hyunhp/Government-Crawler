# UPDATED AT : 2026-03-30
# Site URL : https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do

import os
import time
import logging
import argparse
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# -------------------------------------------------
# 1. 환경 및 로깅 설정
# -------------------------------------------------
def setup_environment(platform_name):
    """폴더 생성 및 로깅 설정"""
    # logs 폴더를 같은 레이어(../logs)에 맞춤
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
def crawl_ntis(driver, wait, target_date):
    """NTIS 공고 목록 수집"""
    results = []
    page = 0
    MAX_PAGE = 10 # 예시로 제한 상향
    
    while page < MAX_PAGE:
        logging.info(f"📄 Page {page + 1} 수집 중...")
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#rndListArea > table > tbody > tr")))
            rows = driver.find_elements(By.CSS_SELECTOR, "#rndListArea > table > tbody > tr")
        except TimeoutException:
            logging.error("데이터 로드 시간 초과")
            break

        for idx in range(len(rows)):
            try:
                # 리스트 페이지 재로딩 대비 재참조
                rows = driver.find_elements(By.CSS_SELECTOR, "#rndListArea > table > tbody > tr")
                row = rows[idx]
                
                seq = row.find_element(By.CSS_SELECTOR, 'td[data-title="순번"]').get_attribute("innerText").strip()
                status = row.find_element(By.CSS_SELECTOR, 'td[data-title="현황"]').text
                title_td = row.find_element(By.CSS_SELECTOR, 'td[data-title="공고명"]')
                ministry = row.find_element(By.CSS_SELECTOR, 'td[data-title="부처명"]').text
                start_date = row.find_element(By.CSS_SELECTOR, 'td[data-title="접수일"]').text
                end_date = row.find_element(By.CSS_SELECTOR, 'td[data-title="마감일"]').text

                # 상세 URL 처리
                detail_url = None
                try:
                    link = title_td.find_element(By.TAG_NAME, "a")
                    href = link.get_attribute("href")

                    if href and "javascript" not in href:
                        detail_url = href
                    else:
                        # 자바스크립트 호출인 경우 클릭하여 이동 후 URL 획득
                        driver.execute_script("arguments[0].click();", link)
                        time.sleep(2)
                        detail_url = driver.current_url
                        driver.back()
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#rndListArea > table > tbody > tr")))
                except NoSuchElementException:
                    detail_url = None

                results.append({
                    "seq": seq,
                    "status": status,
                    "title": title_td.text,
                    "org_name": ministry,
                    "start_date": start_date,
                    "end_date": end_date,
                    "detail_url": detail_url
                })

            except Exception as e:
                logging.error(f"Row {idx} 파싱 에러: {e}")
                continue

        # 🔥 종료 조건: 마지막 아이템의 마감일이 목표일보다 이전(<)인 경우
        if results:
            try:
                last_end_date = datetime.strptime(results[-1]["end_date"], "%Y.%m.%d").date()
                if last_end_date < target_date:
                    logging.info(f"종료 조건 달성: 마지막 마감일({last_end_date})이 목표일({target_date})보다 이전입니다.")
                    break
            except ValueError:
                logging.warning("날짜 형식 변환 실패, 다음 페이지 진행")

        # 페이지 이동
        try:
            page += 1
            next_btn = driver.find_element(By.LINK_TEXT, str(page + 1))
            driver.execute_script("arguments[0].click();", next_btn)
            wait.until(EC.staleness_of(rows[0]))
            time.sleep(1)
        except Exception:
            logging.info("마지막 페이지 도달 혹은 이동 버튼 없음")
            break
            
    return results

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    # 기존 date(2026, 3, 24)를 인자로 대체
    parser.add_argument('--target-date', type=str, required=True, help='YYYY-MM-DD')
    args = parser.parse_args()
    target_dt = datetime.strptime(args.target_date, '%Y-%m-%d').date()

    PLATFORM = "ntis"
    setup_environment(PLATFORM)
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get("https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do")
        data = crawl_ntis(driver, wait, target_dt)
        
        if data:
            df = pd.DataFrame(data)
            df['src_platform'] = PLATFORM
            save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
            df.to_csv(save_path, index=False, encoding="utf-8-sig")
            logging.info(f"✅ 수집 완료: {len(df)}건 저장 -> {save_path}")
        else:
            logging.warning("수집된 데이터가 없습니다.")
            
    except Exception as e:
        logging.critical(f"시스템 에러 발생: {e}")
    finally:
        driver.quit()
        logging.info("드라이버 종료")

if __name__ == "__main__":
    main()