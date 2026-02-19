import os
import joblib
import numpy as np
from kiwipiepy import Kiwi
import torch
from transformers import T5ForConditionalGeneration, AutoTokenizer
from pathlib import Path

# =========================================================
# 0. 공통 Kiwi 객체 생성 (전역)
# =========================================================
kiwi = Kiwi()

# =========================================================
# 1. 모델 로드용 함수/클래스 정의 (학습 때와 동일해야 함)
# =========================================================

def korean_tokenizer(text):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'VA', 'XR', 'MAG', 'SL']]

def importance_tokenizer(text):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'XR', 'SN']]

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
            self.model_main = joblib.load(os.path.join(self.model_dir, 'main_category_model.pkl'))
            self.model_sub = joblib.load(os.path.join(self.model_dir, 'sub_category_model.pkl'))
            self.model_imp = joblib.load(os.path.join(self.model_dir, 'importance_model.pkl'))
            self.model_sent = joblib.load(os.path.join(self.model_dir, 'sentiment_model.pkl'))
            print("✅ All models loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            self.model_main = None

    def calculate_penalty(self, text):
        """중요도 거품 제거를 위한 강력한 페널티 계산 로직 (업데이트됨)"""
        penalty = 0
        text_str = str(text).strip()
        
        # 1. 길이 기반 페널티
        if len(text_str) < 10: 
            penalty += 2.0
        elif len(text_str) < 15:
            penalty += 1.0
            
        # 2. 감성/에세이/가십성 키워드 (기존 리스트 유지 + '직캠' 등)
        low_quality_keywords = [
            '졸업', '축하', '꽃길', '아들', '딸', '가족', '근황', '포착', 
            '일상', '여행', '맛집', '먹방', '유튜브', '인스타', '화제', 
            '충격', '논란', '경악', '결국', '알고보니', '눈길', '공개',
            '티저', '포스터', '비하인드', '스틸', '예고', '선공개',
            '화보', '포토', '직캠', '패션', '룩', '코디', '뷰티',
            '파이팅', '물오른', '여신', '남신', '자태' # (추가됨)
        ]
        
        # 3. [신규] 연예/드라마/홍보 특화 키워드 (가장 중요!)
        # 이 단어들이 있으면 '심각한 단어(복수, 살인)'가 있어도 픽션임을 인지하고 감점
        entertainment_keywords = [
            '드라마', '예능', '방송', '첫방', '본방', '사수', '줄거리', 
            '관전포인트', '등장인물', '인물관계도', '시청률', 'OST',
            '배우', '가수', '아이돌', '컴백', '데뷔', '소속사', '전속계약',
            '제작발표회', '쇼케이스', '무대인사', '시사회', '레드카펫',
            '일일드라마', '주말드라마', '수목드라마', '월화드라마'
        ]

        # 4. 단순 행사/알림 키워드
        event_keywords = [
            '개최', '성료', '진행', '참석', '모집', '선정', '수상', '표창', 
            '기탁', '전달', '체결', 'MOU', '협약', '이벤트', '프로모션', 
            '할인', '특가', '출시', '오픈', '기념', '소식', '게시판', '인사', '부고'
        ]
        
        # --- 키워드 검사 및 점수 누적 ---
        
        # 가십성 키워드 (건당 1.5점, 최대 3점)
        hit_low = 0
        for k in low_quality_keywords:
            if k in text_str: hit_low += 1.5
        penalty += min(hit_low, 3.0)
            
        # [핵심] 연예/드라마 키워드 (건당 2.0점, 강력 제재)
        hit_ent = 0
        for k in entertainment_keywords:
            if k in text_str: hit_ent += 2.0
        penalty += min(hit_ent, 4.0)

        # 행사 키워드 (건당 1.0점)
        for k in event_keywords:
            if k in text_str: penalty += 1.0

        # 5. 특수문자 과다 사용 (광고/어그로성)
        special_chars = text_str.count('!') + text_str.count('?') + text_str.count('~')
        if special_chars >= 2: penalty += 1.0

        # 최대 7점까지만 감점 (0점 방지용 min 처리는 predict에서 함)
        return min(penalty, 7.0)

    def predict(self, title, description):
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
                if max_prob < 0.4:
                    sub_cat = "기타"
                else:
                    sub_cat = self.model_sub.classes_[np.argmax(proba)]
            else:
                sub_cat = self.model_sub.predict(input_list)[0]

            # Importance (0~10) - 페널티 적용 로직 추가됨
            raw_imp_score = self.model_imp.predict(input_list)[0]
            penalty = self.calculate_penalty(title) # 제목 기반 페널티 계산
            
            final_imp_score = raw_imp_score - penalty
            importance = int(max(0, min(10, final_imp_score))) # 0~10 범위 제한

            # Sentiment (0.0~10.0)
            sent_score = self.model_sent.predict(input_list)[0]
            sentiment = round(max(0.0, min(10.0, sent_score)), 2)

            return {
                "main_category": str(main_cat),
                "sub_category": str(sub_cat),
                "importance": int(importance),
                "sentiment": float(sentiment),
                # "penalty_applied": penalty # 디버깅용: 적용된 페널티 점수 확인
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
# 3. T5 헤드라인 생성기
# =========================================================
class T5HeadlineGenerator:
    def __init__(self, model_dir=None):
        if model_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(current_dir, 'models', 't5-model')

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        # symlink인 경우 실제 경로로 변환 (transformers의 repo_id 검증 우회)
        model_dir = str(Path(model_dir).resolve())
        print(f"Loading T5 model from: {model_dir} (device: {self.device})")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
            self.model = T5ForConditionalGeneration.from_pretrained(model_dir, local_files_only=True).to(self.device)
            self.model.eval()
            print("✅ T5 model loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading T5 model: {e}")
            self.model = None
            self.tokenizer = None

    def generate(self, text, max_new_tokens=64, num_beams=4):
        if self.model is None:
            return ""
        try:
            inputs = self.tokenizer(
                "summarize: " + text,
                return_tensors="pt",
                max_length=512,
                truncation=True
            ).to(self.device)

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    num_beams=num_beams,
                    early_stopping=True
                )

            return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        except Exception as e:
            print(f"⚠️ T5 generation failed: {e}")
            return ""

    def generate_batch(self, texts, max_new_tokens=64, num_beams=4):
        """여러 기사를 한 번에 처리합니다."""
        if self.model is None:
            return [""] * len(texts)

        prefixed = ["summarize: " + t for t in texts]
        try:
            inputs = self.tokenizer(
                prefixed,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True
            ).to(self.device)

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    num_beams=num_beams,
                    early_stopping=True
                )

            return [self.tokenizer.decode(ids, skip_special_tokens=True) for ids in output_ids]
        except Exception as e:
            print(f"⚠️ T5 batch generation failed: {e}")
            return [""] * len(texts)


# =========================================================
# 4. 테스트 실행
# =========================================================
if __name__ == "__main__":
    test_title = "졸업이다"
    test_desc = "드디어 학교를 졸업하게 되어 기쁘다."

    classifier = NewsClassifier()
    result = classifier.predict(test_title, test_desc)
    print("\n--- 분석 결과 ---")
    print(f"제목: {test_title}")
    print(f"결과: {result}")

    t5_title = "삼성전자, 3분기 영업이익 10조 돌파"
    t5_desc = "삼성전자가 올해 3분기 영업이익이 10조원을 넘어섰다고 발표했다. 반도체 부문 회복과 스마트폰 판매 호조가 주요 원인으로 분석된다."
    t5 = T5HeadlineGenerator()
    headline = t5.generate(t5_title + " " + t5_desc)
    print("\n--- T5 헤드라인 생성 결과 ---")
    print(f"입력: {t5_title} / {t5_desc}")
    print(f"생성된 헤드라인: {headline}")