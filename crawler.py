import requests
import re
import time
import sys
import asyncio
import random
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

# [중요] Windows 환경에서 Streamlit + Playwright 사용 시 발생하는 asyncio 충돌 해결
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def get_place_id(url: str) -> Optional[str]:
    """
    입력된 URL(단축 URL 포함)을 분석하여 네이버 플레이스 고유 ID를 추출합니다.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    headers = {"User-Agent": random.choice(user_agents)}
    
    try:
        print(f"🔍 URL 분석 중: {url}")
        response = requests.get(url, headers=headers, allow_redirects=True)
        final_url = response.url
        print(f"📍 최종 URL: {final_url}")

        match = re.search(r'/(place|restaurant|hospital|hair|accommodations|campsite)/(\d+)', final_url)
        if match: return match.group(2)
        
        match = re.search(r'[?&]id=(\d+)', final_url)
        if match: return match.group(1)

        if "place" in final_url:
            id_match = re.search(r'"id":"(\d+)"', response.text)
            if id_match: return id_match.group(1)

    except Exception as e:
        print(f"❌ ID 추출 실패: {e}")
    
    return None

def crawl_naver_reviews(place_id: str, max_count: int = 50) -> List[Dict]:
    """
    플레이스 ID를 기반으로 모바일 리뷰 페이지에 직접 접속하여 리뷰를 수집합니다.
    Target URL: https://m.place.naver.com/place/{place_id}/review/visitor
    """
    reviews = []
    target_url = f"https://m.place.naver.com/place/{place_id}/review/visitor"
    
    print(f"🚀 크롤링 시작 (Target): {target_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        mobile_uas = [
            "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1"
        ]
        
        context = browser.new_context(
            user_agent=random.choice(mobile_uas),
            viewport={"width": 412, "height": 915},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(3, 5))

            if "이용이 제한되었습니다" in page.content():
                print("🚫 여전히 차단된 상태입니다.")
                return []

            # 0. '방문자 리뷰' 탭 명시적 클릭
            try:
                visitor_tab = page.locator("a, span").filter(has_text="방문자 리뷰").first
                if visitor_tab.is_visible():
                    visitor_tab.click()
                    print("✅ '방문자 리뷰' 탭 클릭")
                    time.sleep(random.uniform(1, 2))
            except:
                pass

            # 1. '최신순' 정렬 클릭
            try:
                sort_btn = page.get_by_text("최신순")
                if sort_btn.count() > 0:
                    sort_btn.first.click()
                    print("✅ '최신순' 정렬 클릭")
                    time.sleep(random.uniform(1, 2))
            except:
                pass

            # 2. '더보기' 버튼 반복 클릭
            print("📜 리뷰 목록 확장 중...")
            scroll_limit = 2 if max_count <= 10 else 5
            
            for _ in range(scroll_limit): 
                try:
                    prev_height = page.evaluate("document.body.scrollHeight")
                    
                    more_btn = page.locator("a").filter(has_text="더보기").first
                    if more_btn.is_visible():
                        more_btn.click()
                        time.sleep(random.uniform(2, 3))
                    else:
                        page.mouse.wheel(0, random.randint(500, 1000))
                        time.sleep(random.uniform(1, 2))
                        
                    curr_height = page.evaluate("document.body.scrollHeight")
                    if curr_height == prev_height:
                        break
                except Exception:
                    break
            
            # 3. '내용 더보기' 펼치기
            try:
                expand_btns = page.locator("span, a").filter(has_text="내용 더보기").all()
                if expand_btns:
                    print(f"🔍 긴 리뷰 {len(expand_btns)}개 펼치기...")
                    for btn in expand_btns:
                        if btn.is_visible():
                            try:
                                btn.click()
                                time.sleep(random.uniform(0.5, 1.0))
                            except:
                                pass
            except:
                pass

            # 4. 데이터 추출 (필터링 대폭 강화)
            print("📝 텍스트 추출 및 정제 중...")
            
            elements = page.locator("span, div, a").all()
            
            collected_count = 0
            seen_texts = set()
            
            # [제외 키워드 리스트]
            # 1. UI 및 시스템 문구
            ui_keywords = [
                "영수증", "주문", "길찾기", "공유", "신고", "업체", "소식", "이용이 제한되었습니다",
                "알림받기", "이미지 갯수", "방문자 리뷰", "블로그 리뷰", "정렬 안내", "추천순", "최신순",
                "피드형식", "리스트형식", "별건 없는데", "님의 블로그", "맛볼수있는", "데이트", "맛집",
                "리뷰 클렌징", "다녀오셨나요", "경험을", "팔로우", "개의 리뷰가 더 있습니다", "펼쳐보기"
            ]
            
            # 2. 키워드 리뷰 (통계) 문구 - 네이버 고정 문구들
            keyword_reviews = [
                "이런 점이 좋았어요", "음식이 맛있어요", "친절해요", "재료가 신선해요", "매장이 청결해요",
                "특별한 메뉴가 있어요", "가성비가 좋아요", "양이 많아요", "인테리어가 멋져요", "뷰가 좋아요",
                "혼밥하기 좋아요", "단체모임 하기 좋아요", "주차하기 편해요", "화장실이 깨끗해요", "특별한 날 가기 좋아요"
            ]
            
            # 3. 방문 인증 정보
            visit_info = ["방문일", "예약", "대기 시간", "목적", "동행", "안내", "메뉴"]

            skip_keywords = ui_keywords + keyword_reviews + visit_info
            
            for el in elements:
                if collected_count >= max_count:
                    break
                
                try:
                    if not el.is_visible(): continue
                    
                    text = el.inner_text().strip()
                    text = text.strip('"').strip("'")
                    
                    # 1. 길이 필터링 (너무 짧은 텍스트 제외)
                    if len(text) < 15: continue
                    
                    # 2. 중복 제거
                    if text in seen_texts: continue
                    seen_texts.add(text)
                    
                    # 3. 키워드 필터링
                    if any(k in text for k in skip_keywords): continue
                    
                    # 4. 블로그 제목 패턴 제외 ([...])
                    if text.startswith("[") and text.endswith("]"): continue
                    
                    # 5. 날짜 형식 제외
                    if re.match(r'^\d{2}\.\d{2}\.\d{2}', text): continue
                    if re.match(r'^\d{4}년', text): continue
                    
                    # 6. [핵심] 통계 수치 패턴 제외 (정규식)
                    # 예: 5,132회, 4,980명 참여, +4, 12사진
                    if re.search(r'\d{1,3}(,\d{3})*[회명원개]', text): continue # 5,132회, 10명
                    if re.search(r'리뷰 \d+', text): continue # 리뷰 12
                    if re.search(r'사진 \d+', text): continue # 사진 13
                    if re.search(r'\+\d+', text): continue # +4

                    # 7. 포함 관계 확인 (더 긴 텍스트 선호)
                    is_duplicate = False
                    for r in reviews:
                        if text in r['content']: 
                            is_duplicate = True
                            break
                        if r['content'] in text: 
                            r['content'] = text
                            is_duplicate = True
                            break
                    
                    if is_duplicate: continue

                    print(f"✅ 수집됨 [{collected_count+1}]: {text[:30]}...")

                    reviews.append({
                        "id": collected_count + 1,
                        "content": text
                    })
                    collected_count += 1
                    
                except Exception:
                    continue

        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {e}")
        
        finally:
            browser.close()
            print(f"✅ 수집 완료: {len(reviews)}건")

    return reviews

if __name__ == "__main__":
    pass
