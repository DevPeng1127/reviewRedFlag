# 메인 실행 파일 (Streamlit 웹앱)
import streamlit as st
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

st.title("🚩 Red Flag: 리뷰 분석기")
st.write("네이버 플레이스 URL을 입력하면 치명적인 단점만 찾아드립니다.")

url = st.text_input("네이버 플레이스 URL 입력")

if st.button("분석 시작"):
    if not url:
        st.warning("URL을 입력해주세요!")
    else:
        st.success(f"입력하신 URL: {url} (분석 기능 구현 중...)")

        # 여기에 나중에 우리가 만든 analyze_reviews() 함수를 연결하면 끝!
        api_key_status = "✅ 로드 성공" if os.getenv("GEMINI_API_KEY") else "❌ 키 없음"
        st.write(f"API Key 상태: {api_key_status}")