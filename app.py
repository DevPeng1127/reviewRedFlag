import sys
import asyncio

# [중요] Windows 환경에서 Streamlit + Playwright 사용 시 발생하는 asyncio 충돌 해결
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import os
from dotenv import load_dotenv
from crawler import get_place_id, crawl_naver_reviews
from analyzer import analyze_reviews

# .env 파일에서 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Red Flag Reviewer",
    page_icon="🚩",
    layout="centered"
)

# CSS 스타일 주입
st.markdown("""
    <style>
    .stExpander {
        border: 1px solid #ddd;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .metric-card {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚩 Red Flag: 리뷰 분석기")
st.markdown("""
**네이버 플레이스 URL**을 입력하면 AI가 리뷰를 분석하여 
**치명적인 단점(Red Flag)**과 **객관적 팩트**만 요약해 드립니다.
""")

# API Key 확인
if not os.getenv("GEMINI_API_KEY"):
    st.error("⚠️ .env 파일에 GEMINI_API_KEY가 설정되지 않았습니다.")
    st.stop()

url = st.text_input("네이버 플레이스 URL 입력", placeholder="https://naver.me/xxxxx 또는 https://place.naver.com/...")

if st.button("분석 시작", type="primary"):
    if not url:
        st.warning("URL을 입력해주세요!")
    else:
        reviews = []
        
        # 1. URL 분석 및 ID 추출
        with st.spinner("🔍 URL을 분석하고 있습니다..."):
            place_id = get_place_id(url)
        
        if not place_id:
            st.error("❌ 올바른 네이버 플레이스 URL이 아닙니다. 다시 확인해주세요.")
        else:
            # 2. 크롤링 단계 (테스트를 위해 10개로 제한)
            with st.spinner(f"🕷️ 리뷰를 수집하고 있습니다... (ID: {place_id}, 최대 10개)"):
                try:
                    # 차단 방지를 위해 max_count를 10으로 설정
                    reviews = crawl_naver_reviews(place_id, max_count=10)
                except Exception as e:
                    st.error(f"크롤링 중 오류가 발생했습니다: {e}")
                    st.stop()

            if not reviews:
                st.warning("수집된 리뷰가 없습니다. 리뷰가 없는 매장이거나 접근이 제한되었을 수 있습니다.")
            else:
                st.success(f"✅ {len(reviews)}개의 리뷰 수집 완료!")
                
                # 3. 분석 단계
                with st.spinner("🤖 AI가 리뷰를 분석하여 Red Flag를 찾고 있습니다..."):
                    analysis_results = analyze_reviews(reviews)

                # 4. 결과 시각화
                st.divider()
                st.subheader("📊 분석 결과")

                # 에러 체크
                if isinstance(analysis_results, list) and len(analysis_results) > 0 and "error" in analysis_results[0]:
                    st.error(analysis_results[0]["error"])
                elif not analysis_results:
                    st.info("🎉 발견된 치명적인 단점(Red Flag)이 없습니다! 비교적 안전한 매장입니다.")
                else:
                    # 결과 카드 출력
                    for item in analysis_results:
                        risk_level = item.get("risk_level", "Medium")
                        category = item.get("category", "기타")
                        summary = item.get("summary", "")
                        frequency = item.get("frequency", 0)
                        evidence_ids = item.get("evidence_ids", [])

                        # 색상 및 아이콘 설정
                        if risk_level == "High":
                            border_color = "#ff4b4b" # Red
                            icon = "🚨"
                            bg_color = "#ffebeb"
                        else:
                            border_color = "#ffa421" # Orange
                            icon = "⚠️"
                            bg_color = "#fff8e1"

                        # 카드 UI 구성
                        with st.container():
                            st.markdown(f"""
                            <div style="
                                border: 2px solid {border_color};
                                border-radius: 10px;
                                padding: 15px;
                                margin-bottom: 15px;
                                background-color: {bg_color};
                            ">
                                <h4 style="margin: 0; color: #333;">{icon} [{category}] {summary}</h4>
                                <p style="margin: 5px 0 0 0; color: #666;">
                                    <b>위험도:</b> {risk_level} | <b>언급 횟수:</b> {frequency}회
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # 근거 리뷰 펼치기
                            with st.expander(f"🔍 근거 리뷰 보기 ({len(evidence_ids)}건)"):
                                found_evidence = False
                                for review in reviews:
                                    if review['id'] in evidence_ids:
                                        st.markdown(f"**Review #{review['id']}**")
                                        st.text(review['content'])
                                        st.divider()
                                        found_evidence = True
                                
                                if not found_evidence:
                                    st.caption("매칭되는 원본 리뷰를 찾을 수 없습니다.")
