import os
import joblib
import pandas as pd
import numpy as np
from kiwipiepy import Kiwi

# =========================================================
# 0. 공통 Kiwi 객체 생성 (전역)
# =========================================================
# 함수들이 이 객체를 참조합니다.
kiwi = Kiwi()

# =========================================================
# 1. 모델 로드용 함수/클래스 정의 (학습 때와 동일해야 함)
# =========================================================

# (A) 소분류, 감정 분석 모델이 찾을 함수
def korean_tokenizer(text):
    # 명사, 형용사, 어근, 외국어 등 (학습 코드 기준)
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'VA', 'XR', 'MAG', 'SL']]

# (B) 중요도 모델이 찾을 함수
def importance_tokenizer(text):
    # 명사, 어근, 숫자
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'XR', 'SN']]

# (C) 대분류 모델이 찾을 클래스 (만약 클래스로 학습했다면)
class KiwiTokenizer:
    def __init__(self):
        self.kiwi = Kiwi()
    
    def __call__(self, text):
        return [t.form for t in self.kiwi.tokenize(text) if t.tag in ['NNG', 'NNP']]

    def __getstate__(self):
        state = self.__dict__.copy()
        if 'kiwi' in state: del state['kiwi']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.kiwi = Kiwi()

# =========================================================
# 2. 뉴스 분석기 클래스
# =========================================================
class NewsClassifier:
    def __init__(self, model_dir=None):
        # 경로 자동 탐지 로직
        if model_dir is None:
            current_file_path = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file_path)
            self.model_dir = os.path.join(current_dir, 'models')
        else:
            self.model_dir = model_dir

        print(f"Loading models from: {self.model_dir}")
        self.load_models()

    def load_models(self):
        try:
            # 각 모델 로드
            self.model_main = joblib.load(os.path.join(self.model_dir, 'main_category_model.pkl'))
            self.model_sub = joblib.load(os.path.join(self.model_dir, 'sub_category_model.pkl'))
            self.model_imp = joblib.load(os.path.join(self.model_dir, 'importance_model.pkl'))
            self.model_sent = joblib.load(os.path.join(self.model_dir, 'sentiment_model.pkl'))
            print("✅ All models loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            print("힌트: 학습할 때 사용한 tokenizer 함수가 이 파일에도 정의되어 있어야 합니다.")
            # 에러 발생 시 더미 모델이라도 만들어 둠 (속성 에러 방지)
            self.model_main = None

    def predict(self, title, description):
        # 모델 로드 실패 시 방어 로직
        if self.model_main is None:
            return {"error": "Models not loaded"}

        # 1. 전처리
        title = str(title) if title else ""
        desc = str(description) if description else ""
        input_text = title + " " + desc
        input_list = [input_text]

        # 2. 예측 수행
        try:
            # Main Category
            main_cat = self.model_main.predict(input_list)[0]
            
            # Sub Category
            if hasattr(self.model_sub, "predict_proba"):
                proba = self.model_sub.predict_proba(input_list)[0]
                max_prob = np.max(proba)
                # 확률이 너무 낮으면(40% 미만) '기타'로 처리
                if max_prob < 0.4:
                    sub_cat = "기타"
                else:
                    sub_cat = self.model_sub.classes_[np.argmax(proba)]
            else:
                sub_cat = self.model_sub.predict(input_list)[0]

            # Importance (0~10)
            imp_score = self.model_imp.predict(input_list)[0]
            importance = int(max(0, min(10, imp_score)))

            # Sentiment (0.0~10.0)
            sent_score = self.model_sent.predict(input_list)[0]
            sentiment = round(max(0.0, min(10.0, sent_score)), 2)

            return {
                "main_category": str(main_cat),
                "sub_category": str(sub_cat),
                "importance": int(importance),
                "sentiment": float(sentiment)
            }

        except Exception as e:
            print(f"⚠️ Prediction failed: {e}")
            return {
                "main_category": "기타",
                "sub_category": "기타",
                "importance": 5,
                "sentiment": 5.0
            }

# =========================================================
# 3. 테스트 실행
# =========================================================
if __name__ == "__main__":
    test_title = "삼성전자, 3분기 영업이익 '어닝 서프라이즈' 달성"
    test_desc = "반도체 부문의 실적 개선에 힘입어 시장 예상치를 상회하는 실적을 기록했다."
    
    classifier = NewsClassifier()
    result = classifier.predict(test_title, test_desc)
    
    print("\n--- 분석 결과 ---")
    print(f"제목: {test_title}")
    print(f"결과: {result}")