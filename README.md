# 뉴스 데이터 자동 수집 및 분석 시스템

## 프로젝트 요약

> Python, GitHub Actions와 Amazon Free Tier일 때 사용하기 적합한 DynamoDB, 네이버 검색 API를 이용하여 수집한 뉴스정보를 Gemini 2.5 Flash-Lite API가 분석한 정보를 포함하고, 군집화를 한 뒤 AWS DynamoDB에 저장하는 프로젝트.

-----

## 개발 타임라인 (Change Log)

### 2025년 9월

<details>
<summary><strong>2025-09-09 09:07</strong></summary>

* 빌드 = 10개 저장
</details>

<details>
<summary><strong>2025-09-09 09:14</strong></summary>

* 빌드 = 100개 저장
</details>

<details>
<summary><strong>2025-09-09 10:04</strong></summary>

* 오류 발생 = 기본키 값 누락 -> 가끔 JSON 파일에서 original link, description이 비어있는 경우가 있음
</details>

<details>
<summary><strong>2025-09-09 11:30</strong></summary>

* 100개 저장, link를 파티션 키(기본 키)로 변경
</details>

<details>
<summary><strong>2025-09-10 10:39</strong></summary>

* 어제 날짜의 뉴스정보를 읽어오는 파이썬 파일을 만들었음. 다만 아직 읽어오고 파이썬에서 print하도록 만들었을 뿐이므로, 어떻게 활용할지 생각해야 함
</details>

<details>
<summary><strong>2025-09-10 14:50</strong></summary>

* 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업. Layer 설정 부족, boto 충돌, Deserializer() 오류 해결 필요
</details>

<details>
<summary><strong>2025-09-10 15:53</strong></summary>

* 테스트 작업. Layer 설치시 Linux 기반으로 변경, TypeDeserializer() 으로 변경, DynamoDB에 반영되지 않아서 확인
</details>

<details>
<summary><strong>2025-09-10 16:37</strong></summary>

* 테스트 작업. 환경변수 TABLE_NAME value값에 오입력된 공백 제거, 로그를 통한 API 회신 확인, Free Tier 호출 제한 발생
</details>

<details>
<summary><strong>2025-09-10 16:51</strong></summary>

* (1) 테스트 작업. time.sleep(1)을 적용하여 분당 요청수 제한을 넘지 않도록 설정
* (2) 테스트 작업. import time 작성 -> 429 발생. 한 개의 뉴스당 1개의 request를 요청하기 때문에, 지속적으로 확인해보기 위해 Commit을 한 결과, 일일 한도인 1000개에 도달하였다.
</details>

<details>
<summary><strong>2025-09-11 10:45</strong></summary>

* Gemini AI의 모델을 2.5 Flash로 변경하고, 90일 무료 플랜 (Tier 1)으로 변경하였다.
* 어제 얻은 정보를 토대로 토큰수와 Request 수를 줄이기 위해 한번의 요청당 10개의 기사를 보내고 10개의 기사를 받아오는 형태로 변경.
* 20분당 10번의 요청, 하루에 720번의 요청을 진행하기 때문에 무료 플랜으로 돌아가도 정상 작동할 것이다.
* 1개의 요청당 15초 정도 소요되어, GitHub Actions가 workflow를 실행시킬 때 약 3분 정도 소요된다.
* 오전 10:45 이후로 저장되는 데이터에는 소분류, 대분류, 중요도, 감정, 토픽이 분류된다. 이를 통하여 하루에 한번, 일주일에 한번, 한달에 한번 분석/시각화를 하기 쉬워져서, 이를 Actions로 자동화하는 작업을 해도 유효할 것으로 보인다.
</details>

<details>
<summary><strong>2025-09-11 13:00</strong></summary>

* category1, category2 같은 중복값, topics와 같은 잘못된 테이블값을 제거했다.
</details>

<details>
<summary><strong>2025-09-12 15:33 ~ 17:52</strong></summary>

* 수집하고 있는 정보를 웹페이지에서 서비스를 제공하기 위해서는, 현재 DynamoDB(파티션키 = News)로 조회 기능을 사용하기에는 Query사용이 불가능하여 적합하지 않다. 새로운 DB(News_Data_v1)을 생성하여 PK, SK를 새롭게 지정하여 최신 정렬이 가능하도록 만들고, GSI를 이용하여 중요도순, 토픽순 정렬을 가능하도록 만들 예정이다.
* 기존 News가 PK였던 DynamoDB 테이블의 경우 Query를 할 수 없어 데이터가 많아 질수록 조회가 어려워져서, PK(Date), SK(Date-HH-MM-ss-시간대#링크)인 News_Data_v1 테이블을 생성하였다.
* main_category 분석에 대해 prompt로 '대분류를 해달라'라고 했을뿐 기준이 없어서 여러 대분류가 존재했으나, 정치,경제,사회,IT/과학,문화/생활,연예,스포츠,국제 중 하나로 정하도록 변경하였다.
</details>

<details>
<summary><strong>2025-09-15 14:54 ~ 17:09</strong></summary>

* 주말간 Actions의 스케쥴 작업에서 AI가 Importance를 string으로 주는 경우가 있어 GSI와 맞지 않아 데이터를 저장하지 못하는 경우가 존재하여, Int로 바꾸는 과정 추가. (+쓰지 않는 workflow 삭제)
* 로컬테스트 환경과 테스트 workflow / 스케쥴 workflow를 분리하였다.
</details>

<details>
<summary><strong>2025-09-16 14:02 ~ 16:28</strong></summary>

* sentiment(감정)을 부정/중립/긍정에서 0.0(부정)~10.0(긍정)으로 세분화 하였고, link를 통해 매치되는 언론사가 있는지 확인하고 없으면 기타언론사로 분류하도록 변경했다.
* 군집화 과정을 추가하여 중복 기사가 조회되지 않도록 만들고, DynamoDB에 float형인 sentiment가 들어갈 수 없어서 Decimal형식으로 변환하여 저장하도록 변경하였다.
* cluster-id의 유일성을 보장하기 위해 link를 이어붙였으나 지나친 데이터 중복 / 불필요한 저장이라 생각하여 uuid를 생성하여 저장하도록 변경하였다.
* 테스트 환경에서의 최신 DB에서 꺼내오는 batch수를 제한하였다.
* torch가 포함됨에 따라 캐싱을 하더라도 의존성파일 설치에 시간이 더 걸리게 되어, 기존 10분 제한을 15분으로 변경하였다.
* GSI에서 대표군집인지 확인하는 (0,1) 속성을 포함시키고 이진으로 했더니 계속해서 오류가 발생하여 GSI를 제거하고 이전형태로 되돌렸다.
</details>

<details>
<summary><strong>2025-09-17 15:35</strong></summary>

* 군집로직을 개선하고 DB에서 읽어오는 갯수를 100개에서 300개로 증가시켰으며, 모듈화를 진행하고 readme에 Commit했던 이력에 대한 부가설명을 작성하였다.
</details>

<details>
<summary><strong>2025-09-24 10:27</strong></summary>

* 분석을 위한 S3 저장 로직 테스트. Lambda를 통하여 실시간 Stream을 저장하고, 그 데이터를 토대로 Lambda로 parquet 일일데이터로 변환하도록 만들었음
</details>

<details>
<summary><strong>2025-10-04 13:40</strong></summary>

* 오전 2시부터 발생한 오류를 해결하기 위해 파이썬 실행환경을 3.9에서 3.12로 변경
</details>

<details>
<summary><strong>2025-11-07 10:05</strong></summary>

* 무료 크레딧 (200$) 소진으로 인하여 Gemini 모델을 Gemini 2.5 Flash-Lite로 변경하였다.
</details>

<details>
<summary><strong>2025-11-27 10:05</strong></summary>

* 분석탭 개발을 위해 Gemini에게 새롭게 'keyword'를 분류하도록 만들었다.
* Gemini가 반환값을 지키지않아 prompt를 수정했다.

* keywords 저장 형식이 동일하지 않아 Glue Table을 삭제, Crawler를 돌린 후 형식을 array<string>으로 통합하는 과정을 거쳤다. (수집시 마다 hour에 저장되는 jsonl에도 array<string>으로 저장되도록, 일별 parquet으로 통합하는 이미지기반 Lambda역시 array<string>을 사용하도록 변경했다.)

* '분석'을 위해 Glue Table을 저장한 것까지는 좋았으나, 기존 수집 정보의 'topic'은 기사에 대한 '요약정보'이기 때문에, 키워드 요약으로는 적절하지 않았고, 이에 따라 prompt문을 변경함. 기존 수집한 데이터 22만 건의 데이터에 대한 키워드 추출에 대해 고민해봐야 할 듯
</details>

<details>
<summary><strong>2025-11-28</strong></summary>
* 어떤 정보를 토대로 어떤 시각화를 할지에 대해 구상했다. 최근(24시간 내) 데이터에 대해 시계열로 분석하면 좋을것 같다.
 
* 뉴스 대분류 트렌드,실시간 키워드, 어떤 기사군집이 가장 큰지등을 시각화 하기로 했다.
  
* 분석 DB를 생성했다. PK (어떤 분석정보인가?. ex) 키워드에 대한 분석정보 STATS#KEYWORDS ) SK (어떤 범위에 대한 분석인가? H#2025-11-28#14) data(분석정보에 따라 다름), TTL
 
* 분석 DB에 저장하는 Lambda를 생성했다. 이 Lambda는 Athena에 쿼리를 하고, 쿼리 정보를 분석 DB에 저장한다. (Athena 쿼리는 수명주기 정책에 의해 시간이 지나면 삭제된다.)
  
* 분석 DB를 조회하는 Lambda를 생성했다. 이 Lambda는 분석탭에 들어갔을때 수행되며, 분석 DB로부터 데이터를 읽어와 반환한다.

* 새롭게 dashboard.js를 생성하여, 시각화 했다.
 
</details>

<details>
<summary><strong>2025-12-01 ~ 12-04</strong></summary>

* **12-01 10:02**: 군집화가 적절하지 않아서, 범용 군집화 모델 대신 한국어 군집 모델을 새로 적용했다.
* **12-01 10:45**: 연예계 뉴스, 지자체 상 수상등 큰 이슈가 아님에도 중요도가 4~6을 배정받아, 중요도 관련 prompt를 추가했다.
* **12-01 11:28**: 수집량과 기존 기사 읽어오는 양을 증가시켰다.
* **12-01 12:36**: 네이버검색 API는 한번에 100개씩만 가져올수 있어서, 100개단위로 나눠 쿼리하도록 수정했다.
* **12-01 15:17**: 중요도에 대한 Prompt를 추가하고, 하한을 0으로 확장했다. (기존 0)
* **12-02 09:42**: 군집의 최소 기사 수를 1로 조정하고, 임계값을 조정하여 뉴스 분류를 더 정확하게 만들었다.
* **12-02 11:29**: 기존에 읽는 기사를 400건에서 1000건으로 조정하고, 군집ID 로직을 변경하였다.(기존 군집에 속할경우, 군집ID를 상속받게됨)
* **12-02 15:31**: 군집화 로직에 의하여 군집대표가 두개가 되는 현상이 발생하여 조정하였다.
* **12-03 09:31**: Gemini가 제목을 반환할때 기사의 ""를 사용하여,(""챗GPT 뉴스 검색 결과는 예측 불가능하고 종종 부정확"") JSON을 파싱할때 에러가발생했다. 응답형식을 json을 강제하고, 창의성을 낮췄다.
* **12-03 13:08**: 기존에 읽는 기사를 1000건에서 2000건으로 조정
* **12-03 13:59**: 양식을 제공하였음에도 파싱에러가 발생했다. json 양식을 직접 제공하여 파싱 에러가 발생하지 않도록 했다.
* **12-04 13:59**: 기존 GitHub Actions 스케쥴러를 통한 작업은 불규칙적(20분 단위로 설정헀으나, 한시간에 한번도 수행되지 않는 경우가 존재함)하여, EventBridge 예약된 규칙작업으로 GitHub Workflow를 실행시키도록 했다.
* **12-04 16:55**: 여전히 연예 뉴스의 중요도가 높게 평가되어 prompt를 추가했다.
</details>

<details>
<summary><strong>2025-12-07</strong></summary>

* **12-07**: Gemini가 프리티어의 quota수를 20으로 크게 줄여서, 무료로 사용하던 API를 전혀 사용할수 없게되었다. Google Gemini API대신, 다른 AI를 활용하여 데이터를 분석하도록 변경해야한다.
* https://discuss.ai.google.dev/t/is-gemini-2-5-pro-disabled-for-free-tier/111261/2
* https://www.reddit.com/r/Bard/comments/1pg02ni/they_removed_the_free_tier_for_25_pro_api/
* https://gall.dcinside.com/mgallery/board/view/?id=eastfantasy&no=34475
* https://discuss.ai.google.dev/t/do-they-really-think-we-wouldnt-notice-a-92-free-tier-quota-nerf/111262

* 일시적으로 EventBridge 규칙을 비활성화 헀다.

</details>

<details>
<summary><strong>2025-12-08</strong></summary>
EventBridge 규칙을 활성화하고, 경과를 지켜본 뒤 여전히 quota가 크게 제한되어있다면 요청 모델 Gemini에서 다른 무료모델로 바꾼다.
 
확인결과, 여전히 quota가 20으로 제한이 걸려있어, Groq llama-3.3-70b-versatile모델을 이용하도록 변경하였다.

Groq은 하루 제한량은 넉넉하나, 토큰 입력양에 제한이 걸려있어, 모든 기사를 넣으면 금방 제한량에 걸린다.

따라서, 기존 수집된 기사 (26만건)을 통해 sklearn 분류모델을 생성하고 이를 적용하도록 변경할것이다.
 
또한, AI 모델이 고장났다고 수집이 안되는것은 좋지 않아보인다. 간단한 대/소분류, keyword 추출, topic에 따른 중요도 산정같은 새로운 예비로직이 필요할것 같다.

기존 26만건을 이용하여 ML을 하기로 했고, BERT, sklearn, TensorFlow 중 가장 가벼운 sklearn을 이용하여 모델 적합, pkl파일을 생성하였다.
</details>

<details>
<summary><strong>2025-12-09</strong></summary>

* **12-09**: ML모델을 이용하여 대/소분류(분류), 중요도(회귀), 감정(회귀)을 예측하도록 만들고, ML모델을 이용하여 만들수없는 topic을 군집대표만 Groq에게 요청하게끔 변경하였다.
* 테스트 과정에서 topic, outlet, keywords을 넣는부분이 엉켜 시간이 조금 걸렸다.
* 현재 (2025-12-09 15:40) 일정작업에서 topic이 없는경우가 발견되고 있다. 해당경우는 title을 사용하도록 했다.(새로운 대표군집의 경우, Groq에 topic 요청 하도록 설정되어있어서, is_representative가 0인값만 발생하고 있다.)
* 군집화 오류가 발견되어, 임계값을 조정했다.
* 분석 DB에 저장하는 부분을 Duck DB를 이용하여 합치고 SQL 쿼리를 날리는 형식으로 변경했다. Athena는 이제 디버깅용도로만 사용된다.


*  EventBridge 규칙을 활성화 헀다.

</details>
<details>
<summary><strong>2025-12-10</strong></summary>

* **12-10**: main_category와 sub_category를 정제한 파일인 cleaned_news_data.parquet로 ML모델을 적합 시켰으나, main_category를 정제할때 문제가 발생했던걸 뒤늦게 확인했다.
* 수집데이터는 수집 로직이 정형화 되기전 데이터도 존재하기에, main_Category가 30개인 문제가 있었다. 따라서 이를 통합하는 과정이 필요했는데, 이 과정에 문제가 발생하여 문화생활이 61건이 되어버렸다. (문화/생활 수집데이터는 25259건)
* 따라서 main_category를 제대로 통폐합한뒤, 다시 ML을 돌리고 개선된 pkl파일을 업로드해야한다. -> 완료. 이제부터 문화/생할을 잘 분류한다.
* 쓸데없는 키워드가 많아, stop_words를 추가했다. AI가 추출한 키워드에 비해 유효하지 않은 키워드도 추출되며, 복합명사를 잘 인식하지 못한다. -> 나중에 수정할 부분
* 수집은 잘 되었으나 캐시 저장하는 과정에서 오류가 발생하는 문제, 의존성 설치중 중단되는 문제를 해결했다. -> requirements.txt에서 sentence-transformers로 인해 GPU버전으로 설치되던 torch(4GB 남짓)를 cpu버전으로 먼저 설치하도록 변경하여 캐시 크기를 줄였다.(0.5GB)
Git Hub Actions에 올라갈진 모르겠으나, 26만건을 딥러닝시켜 요약하는 모델을 생성중이다. 만약 이 딥러닝 모델이 적절히 topic을 만들어낸다면, Groq 에게 요청하는것을 없애고, 분석정보에 대한 AI 분석 요청을 할 수 도 있을것 같다.

</details>


### 해결된 문제
* Athena는 10MB마다 과금된다. 기사 한건당 1KB, 최근 24시간 수집데이터가 5000건임을 감안하면, 약 2일마다 매우 작은 비용이 발생하게 된다. 또한 Athena는 쿼리를 위해 S3 List/Get 요청을 매우 많이 해서, 이에 대한 비용도 발생한다.
* 따라서, 분석 DB에 저장하는 부분을 Duck DB를 이용하여 합치고 SQL 쿼리를 날리는 형식으로 변경한다.
* 위 과정을 거칠경우, Glue 테이블을 갱신할 필요가 없어지므로, 파티션을 갱신하는 부분을 제거한다.
  -> 디버깅용 Athena를 유지한다면, Glue 테이블을 유지해도 가격자체는 들지 않으므로 유지한다.


* 12-07에 Gemini Free tier 한도가 갑자기 제한되는 문제로인해 중요도/대/소분류판별등이 되지 않아 뉴스수집기 자체가 작동하지 않았다. -> Groq llama-3.3-70b-versatile 모델을 사용하도록 변경하였다. -> 여전히 제한에 막혀, llama-3.1-8b-instant로 변경하였으나 여전히 제한에 막힌다.
* Gemini, 혹은 바뀔 AI모델이 작동하지 않더라도 네이버 검색 API가 다운되지 않았다면 수집되도록 조치를 취해야한다.
* topic을 제외한 것들 (importance(회귀/분류(10중 택1)), main_category(분류),sub_category(통합후분류),sentiment(회귀 0.0~10.0) 및 keywords(kiwipiepy 형태소분리))은 어떻게든 커버가 가능하겠으나,
* topic은 '요약'이기 때문에 분류/회귀등으로 해결할 수 없다. topic만을 groq에 넣던지, topic을 최대한 사용하지 않도록 할지 (현재 군집화에 topic이 사용되고 있는데, 이를 수정하던지)결정해야한다.
  -> topic은 대표군집의 경우에만 Groq에게 요청하며, 만약 Groq할당량이 초과되었거나 기존 수집과정에서 topic이 누락되었을경우, topic을 title로 채우는 과정을 추가했다.
  -> 실수/정수인 sentiment, importance는 회귀모델을, main_category,sub_category는 분류모델을 사용했다. 키워드 분리는 kiwipiepy를 사용하고 있다. (이전보다는 완벽한 키워드 추출은 아니다.)
  
### 이후 가이드라인

* S3에 일일 parquet을 유지한다면, DynamoDB에 TTL 1년정도를 걸어 25GB를 초과하지않도록 조정해야한다.
  
* **'군집의 상태변화'를 반영하고 있지 않다.**
   -> '지하철 노조 파업시작' -> '지하철 노조 파업직전 극적 타결, 파업 철회' 이 둘은 같은 군집으로 묶인다.
  
     -> 이 경우, 대표군집은 '노조 파업시작'이기 때문에, 조회 서비스에서 '지하철 노조 파업 철회' 기사가 조회되지 않는 문제가 존재한다. (is_representative=1인 값만 기사 노출)
  
     -> 분석탭의 버블차트 역시 '지하철 노조 파업시작'으로 고정되어, 이슈 파악은 쉬우나, 지금도 파업을 하고 있는지, 철회되었는지 알 수 없다.
  
* 주간 분석을 제공해야 한다.

* 현재 Cloudfront 캐싱을 사용하고 있지 않아, 데이터를 일일히 Lambda가 DynamoDB에 요청하여 반환하는 형태를 가지고 있다. Cloudfront가 캐싱을 사용하도록 해야한다.

*  CORS를 통해 cloudfront 웹페이지에서만 요청할 수 있게 수정하였으나(로컬 환경에서는 요청할 수 없음), Postman등의 Agent에서는 여전히 API Gateway경로 및 적절한 매개변수만 주어지면 응답을 받을 수 있는 문제가 발견되었다.

*  위 같은 경우가 허용될경우, 웹페이지에서 어떤 요청이 오고가는지 확인하고 이를 악용하여 데이터를 빼내거나, API Gateway에 악의적인 요청을 보낼 가능성이 존재하므로, 이를 수정해야한다.

---

## 기술 스택 및 아키텍처

  * **GitHub Actions - 자동화**

      * 해당 Repository의 workflows yml파일에 따라, 20분마다 py파일을 이용하여 100개의 뉴스기사를 수집한다.
      * Repository에서 미리 지정한 액세스 코드를 통하여, Amazon DynamoDB에 접근하여 데이터를 저장한다.
      * 해당 Repository가 'Public'인 이상, 비용은 발생하지 않는다.

  * **Amazon DynamoDB**

      * 데이터베이스 프리티어 기준으로 25GB와 빠른 읽기/쓰기를 제공한다.

  * **IAM - DB 접근 권한**

      * GitHub Actions가 DynamoDB 접근하기 위해 먼저 설정해야 하는 부분이다.
      * 사용자 그룹(GitHub Worker로 지정함)을 생성하여 DynamoDB 접근권한만을 부여하고, CLI 액세스코드를 생성하여 GitHub Actions가 사용할 수 있도록 했다.

  * **네이버 API**

      * API keyword를 뉴스, 갯수를 100개, date순(최신순)으로 하여 뉴스정보 100개를 수집한다.
      * API는 100개씩 검색가능하여, 150개를 검색하기 위해 두번의 쿼리를 날리도록 조정하였다.
      * API를 이용하기 때문에 response로 받는 JSON 파일 안의 정보 외에는 획득 할 수 없지만, 기본적으로 대부분의 뉴스사이트, 네이버뉴스도 기본적으로 크롤링을 허용하지 않으므로, 이를 활용한다.

  * **Gemini API - AI API**

      * 토픽, 대분류/소분류는 가능하겠지만 중요도, 감정은 꽤 심화적인 머신러닝이 필요할 것으로 보여 AI API를 이용하여 이 과정을 대체하였다.
      * News에 대해 AI API는 대분류, 소분류, 토픽, 중요도(1-10), 감정판별을 진행하여 반환해준다.
      * 키워드를 추가적으로 추출하여 반환하도록 설정하였다.

-----

## 생각할 점 및 시스템 구성

### 보안

  * GitHub Actions에겐 Amazon IAM에서 CLI 액세스 코드를 통하여 DynamoDB의 모든 권한을 부여하였는데, 조금 더 강한 보안을 위해서라면 다른 방법으로 권한을 부여하거나, DynamoDB에서 쓰기만 가능하도록 만드는 것도 좋아 보인다.
  * \-\> 지금은 Actions가 Scan이 가능해야하니, 이 부분은 그대로 두어도 될 것 같다.
  * \-\> 현재는 군집화 과정에서 테이블의 최신값을 불러오므로 현재의 권한(DynamoDB Full Access)을 유지한다.

### 확장

  * 나중에 크롤링을 통해서도 정보를 수집하고, 검색어 트렌드 등과 결합할 수 있을수도 있는데, 이에 대해 생각해보면 좋을 것 같다.
  * (DynamoDB는 RDB와 달리 NoSQL DB형식이라, 크롤링을 통해 원래정보 + 기타정보가 들어오면 그냥 새로운 속성을 같이 사용하여 같은 DynamoDB를 사용해도 문제는 없는 것 같다.) (보류)

### 빌드 테스트

  * API를 이용한 자동수집은 마무리 되었으나, 이후 수정한다면 수정할때마다 자동으로 테스트하는 기능을 넣으면 좋을 것 같다.
  * \-\> 다만, 이 Repository 안에서 수정이 일어날 경우(심지어 README.md를 수정할때도) 무조건적으로 main.yml이 실행되어 100개의 데이터를 받아오고 분석하고 저장하고 있는 형태이다. 워크플로우를 분리하여 변경시 테스트, 스케쥴 작업으로 나눠 두는것이 좋아 보인다. (완료)

### Airflow

  * Airflow를 실습한 뒤 Actions를 사용하였는데, 매우 단순한 작업이라면 Actions를 이용한 작업으로 충분하나, 복잡해지거나 순환과정 같은 부분이 생길경우 AirFlow가, DAG가 서로 얽혀 관리가 필요하다면 Kubernetes가 사용된다.

### AWS EventBridge

  * 만약 Git Hub Actions같은 역할을 AWS안에서 모두 해결하고 싶다면 AWS Eventbridge를 이용할 수 있다.
  * \-\> 조사해보니 이 친구는 AWS안의 시스템에게 정보를 보내거나 하는것은 가능하나 다른것을 호출하고 실행하는 역할은 할 수 없다고 함. 대체 가능한 방법은 지금 같은 상황이라면 EC2 + Airflow로 진행해도 프리티어로 비용이 발생하지 않을 수 도 있음. 비용을 생각한다면 Git Hub Actions가 가장 좋은 방법.
  * (사용 후) Runner가 존재하지 않고, 어떤 함수를 실행시키도록 일정 스케쥴링이 가능한 서비스이다.
  * Glue ETL/ Firehose을 이용한 자동 테이블 갱신이 되고 있지 않으므로, 하루에 한번(KST기준 02:00) INSERT 데이터 테이블에서 7일이 지난 데이터 처리, 하루에 한번 EventBridge 일정 작업이 INSERT 테이블에서 hour=0\~23을 parquet형식으로 통합하는 Lambda를 각각 호출한다.
  * 두 Lambda Function 모두 계층 용량한계보다 커서, ECR에 업로드한 도커 이미지를 사용한다.
  * 기존 Workflow 스케쥴 작업 대신 EventBridge 예약된 규칙작업으로 정확히 20분마다 호출하고 있다. 토큰을 사용하므로, Private Repository의 경우 보안에 유의하여야 한다.

### Glue

  * Athena를 효율적으로 활용하기 위해 Kinesis Firehose -\> Glue ETL -\> Athena를 이용하고자 하였으나, Glue ETL을 사용하는경우 프리티어가 존재하지 않아 시간당 비용이 부과되어 생각보다 비용부담이 컸기에, Docker 이미지를 ECR을 활용하여 업로드하고, 이를 활용한 Lambda가 처리하도록 만들었다.
  * Glue ETL은 사용하지 않고, Glue Crawler(일회성 테이블 생성용), Glue Table만을 사용한다.

### Kinesis Firehose

  * Kinesis Firehose의 경우 동적활성화를 하지 않으면 UTC기준으로 파티셔닝 되어 기사의 pub\_date의 KST와 형식이 일치하지 않아 처리하기 어려워지고, 동적 파티셔닝을 할 경우 추가비용이 발생하여 INSERT STREAM 파티셔닝도 Lambda가 KST기준으로 처리하도록 만들었다.

### OpenSearch

  * 서버리스 형태로 제공할 수는 있으나, 비용 최소화가 우선적인 상황에서 채용하긴 어려웠다.

### S3 버킷

  * INSERT 데이터와 일간 데이터를 저장하여 Athena를 통해 분석을 할 수 있도록 저장소 역할을 한다. 여러 개의 버킷이 존재한다.
  * 단, 20분마다 들어오는 INSERT 데이터는 시간별로 파티셔닝되고, 지나치게 많은 정보를 저장하는 것을 방지하기 위해 수명주기 정책을 7일로 설정하고, 만료될 경우 영구삭제가 되도록 만들었다.

### ECR (Elastic Container Registry)

  * CMD를 통해 AWS와 연결하고, 도커로 이미지를 빌드 / AWS ECR 레포지토리에 push하여 이미지를 업로드하는데 사용하였다.

-----

## 이전에 생각했던 것 (회고 - 2025-09-10)

  * **문제1**

      * for 문을 사용하여 한 record당 1 request를 보내어, 하나의 결과물 (기본키, 주요 토픽, 대분류, 소분류, 중요도)을 받는 구조의 문제.
      * 다만 여러 개를 한번에 줄 경우 답변에 대한 결과 분석이 어려워 질 수 있다. 다만, 일일 한도 1000개로는 턱없이 부족하므로, 해당 방법은 바꿔야 한다.

  * **생각해본 점1**

      * 굳이 INSERT 스트림을 감지하여 100개가 들어올 때마다 분류를 할 필요가 있을까?
      * 그런 건 아니지만, 어제의 데이터 (펜듈럼 now에서 day-1해서 09-09)를 뽑았을 때 1500개 정도의 로그만 남겨져 있던 걸 보면 다 추출이 안 되었을지도 모르니 이런 방법을 사용했던 것이지만, 무료 API 한도가 존재하여 이 방법은 좋은 방법이 아니다.

  * **생각해본 점2**

      * '로그'가 6000개 중 일부만 받아온 게 아닐까?
      * 일단 lambda 함수의 코드를 모두 주석처리하고, 혹시 AI API를 사용할 때 csv파일로 보내고, csv파일로 받을 수 있는지도 확인해보면 좋을 것 같다.

  * **배운 점**

      * lambda는 Window bash에서 설치한 py 컨테이너와 충돌을 일으키는 부분이 있어, 레이어를 만들 때 어느정도 확인을 해야하는 부분이 있다.
      * 스트림을 활성화해서 INSERT 신호가 들어오면 트리거 되는 형식으로 작성되었는데, 이러한 기능은 꽤 도움이 될 것 같다.
      * 당연하지만, lambda의 IAM 권한에서 DynamoDB에 대한 접근권한을 허용해야만 가능하다.

  * **개선점**
      * 클라우드 서비스를 이용해보고 싶어서 lambda를 사용했지만, 현재 환경에서 lambda를 사용할 거라면 AWS AI나 AWS 머신러닝 쪽으로 보내는 것이 현재 방법보다 좋지만 비용이 발생한다.
      * 따라서 GitHub Actions에서 Naver API를 이용하여 JSON 파일을 받아오고, 이를 AI API에게 보내 분류를 시키는 것이 더 좋은 개선 방법인 것 같다.
      * 로컬 LLM은 컴퓨터가 켜져 있어야 하니 자동화에는 어울리지 않고, 머신러닝을 직접 짜는 것은 DT쪽에 더 가깝고, 분류도 정확하지 않을 수 있다.
   
