import os
import json
import google.generativeai as genai
from typing import List, Dict, Any

def analyze_reviews(reviews: List[Dict]) -> List[Dict[str, Any]]:
    """
    Gemini API를 사용하여 리뷰 데이터를 분석하고 Red Flag를 추출합니다.
    """
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return [{"error": "API Key가 설정되지 않았습니다."}]

    genai.configure(api_key=api_key)
    
    # 사용 가능한 모델 확인 및 선택
    model_name = 'gemini-pro' # 기본값
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"🤖 사용 가능한 모델 목록: {available_models}")
        
        # 우선순위: gemini-1.5-flash -> gemini-pro -> gemini-1.0-pro
        if 'models/gemini-1.5-flash' in available_models:
            model_name = 'gemini-1.5-flash'
        elif 'models/gemini-pro' in available_models:
            model_name = 'gemini-pro'
        elif available_models:
            model_name = available_models[0].replace('models/', '') # 첫 번째 모델 사용
            
        print(f"🎯 선택된 모델: {model_name}")
        model = genai.GenerativeModel(model_name)
        
    except Exception as e:
        print(f"⚠️ 모델 목록 조회 실패, 기본값 사용: {e}")
        model = genai.GenerativeModel('gemini-pro')

    # 리뷰 텍스트만 추출하여 프롬프트에 넣기 위해 변환
    reviews_text = json.dumps(reviews, ensure_ascii=False, indent=2)

    system_prompt = """
    당신은 'Naver Place Red Flag Analyzer'입니다. 
    사용자가 제공한 네이버 플레이스 리뷰 목록을 분석하여, 잠재 고객에게 치명적일 수 있는 단점(Red Flag)을 찾아내세요.

    **분석 규칙:**
    1. **필터링:** 
       - 단순 비방(욕설, 이유 없는 불만)은 무시하세요.
       - '진상 고객'으로 추정되는 리뷰(매장 규정 미숙지, 과도한 요구 등)는 무시하세요.
       - 맛, 분위기 등 주관적인 호불호는 '치명적 단점'이 아닙니다. (단, '음식에서 이물질이 나왔다' 등 위생 문제는 포함)
    
    2. **보고 기준:**
       - 전체 리뷰가 10개 미만인 경우: 1건의 불만이라도 타당하다면 보고하세요.
       - 전체 리뷰가 10개 이상인 경우: 
         - 동일한 불만 사항이 2건 이상 반복될 때만 보고하세요.
         - **예외:** 위생(벌레, 이물질, 식중독 등) 및 안전 이슈는 단 1건이라도 즉시 보고하세요.

    3. **출력 형식 (JSON List):**
       아래 형식의 JSON 리스트로만 응답하세요. 마크다운 코드 블록(```json)을 사용하지 말고 순수 JSON 텍스트만 출력하세요.
       
       [
         {
           "category": "위생",  // 예: 위생, 서비스, 맛(품질), 가격, 시설 등
           "risk_level": "High", // High (위생/안전/사기 등), Medium (불친절/오안내 등)
           "summary": "음식에서 머리카락이 반복적으로 발견됨",
           "frequency": 3, // 해당 이슈가 언급된 횟수
           "evidence_ids": [1, 5, 12] // 해당 이슈가 언급된 리뷰의 ID 리스트
         }
       ]
       
    4. **데이터가 없을 경우:**
       치명적인 단점이 발견되지 않았다면 빈 리스트 `[]`를 반환하세요.
    """

    user_prompt = f"""
    다음은 수집된 네이버 플레이스 리뷰 데이터입니다.
    위의 규칙에 따라 분석 결과를 JSON 형식으로 출력해주세요.

    [리뷰 데이터]
    {reviews_text}
    """

    try:
        response = model.generate_content(system_prompt + "\n" + user_prompt)
        
        # 응답 텍스트 정리 (혹시 모를 마크다운 제거)
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        return json.loads(result_text)
        
    except Exception as e:
        return [{"error": f"분석 중 오류 발생: {str(e)}"}]

if __name__ == "__main__":
    pass
