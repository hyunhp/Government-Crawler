# UPDATED AT : 2026-03-30
# Site URL : https://www.smtech.go.kr/front/ifg/no/notice02_list.do

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
def crawl_smtech(driver, wait):
    """SMTECH 공고 목록 수집 및 페이지네이션 처리"""
    results = []
    page = 1
    
    while True:
        logging.info(f"📄 Page {page} 수집 중...")
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#subcontent table tbody tr")))
            rows = driver.find_elements(By.CSS_SELECTOR, "#subcontent table tbody tr")
        except Exception as e:
            logging.error(f"데이터 로드 실패: {e}")
            break

        stop_flag = False
        first_row_text_before = rows[0].text if rows else ""

        for idx in range(len(rows)):
            try:
                # DOM 재참조
                rows = driver.find_elements(By.CSS_SELECTOR, "#subcontent table tbody tr")
                row = rows[idx]

                # 상태 확인 및 종료 조건
                status = row.find_element(By.CSS_SELECTOR, "td.ac.ll img").get_attribute("alt")
                if "접수완료" in status.replace(" ", ""):
                    logging.info("⛔ '접수완료' 항목 발견으로 수집 종료")
                    stop_flag = True
                    break

                project = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text.strip()
                period = row.find_element(By.CSS_SELECTOR, "td:nth-child(5)").get_attribute("innerText").strip()
                post_date = row.find_element(By.CSS_SELECTOR, "td:nth-child(6)").get_attribute("innerText").strip()
                
                a_tag = row.find_element(By.CSS_SELECTOR, "td:nth-child(4) a")
                title = a_tag.text.strip()
                href = a_tag.get_attribute("href")

                # URL 보정 로직
                if href.startswith("/"):
                    real_url = "https://www.smtech.go.kr" + href
                elif href == "javascript:goMove()":
                    real_url = "IRIS 공고문 이동 필요"
                else:
                    real_url = href

                results.append({
                    "status": status,
                    "project_name": project,
                    "title": title,
                    "period": period,
                    "post_date": post_date,
                    "detail_url": real_url
                })
            except Exception as e:
                logging.error(f"Row {idx} 파싱 에러: {e}")
                continue

        if stop_flag:
            break

        # 페이지 이동 로직
        try:
            next_page = page + 1
            number_buttons = driver.find_elements(By.CSS_SELECTOR, "#paging a")
            next_btn = None

            # 1. 다음 숫자 버튼 찾기
            for b in number_buttons:
                if b.text.strip() == str(next_page):
                    next_btn = b
                    break

            # 2. 숫자 버튼 없으면 '다음' 화살표 버튼 찾기
            if next_btn is None:
                next_btn = driver.find_element(
                    By.XPATH, "//div[@id='paging']//a[contains(@class,'next') or contains(text(),'다음')]"
                )

            driver.execute_script("arguments[0].click();", next_btn)
            
            # 페이지 전환 대기 (첫 줄 텍스트 변경 확인)
            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#subcontent table tbody tr")[0].text != first_row_text_before)
            page += 1
            time.sleep(1)
        except Exception:
            logging.info("마지막 페이지 도달")
            break
            
    return results

# -------------------------------------------------
# 3. 메인 실행부
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-date', type=str, required=True, help='기준일자 (YYYY-MM-DD)')
    args = parser.parse_args()

    PLATFORM = "smtech"
    setup_environment(PLATFORM)
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 10)
    
    try:
        url = "https://www.smtech.go.kr/front/ifg/no/notice02_list.do"
        driver.get(url)
        data = crawl_smtech(driver, wait)
        
        if data:
            df = pd.DataFrame(data)
            df['src_platform'] = PLATFORM
            save_path = f"../raw/{PLATFORM}/{PLATFORM}_{args.target_date}.csv"
            df.to_csv(save_path, index=False, encoding="utf-8-sig")
            logging.info(f"✅ 수집 완료: {len(df)}건 저장 -> {save_path}")
        else:
            logging.warning("수집된 데이터가 없습니다.")
            
    except Exception as e:
        logging.critical(f"시스템 에러: {e}")
    finally:
        driver.quit()
        logging.info("브라우저 종료")

if __name__ == "__main__":
    main()