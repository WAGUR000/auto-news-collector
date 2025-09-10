2025-09-09 오전 9:07 빌드 = 10개 저장

2025-09-09 오전 09:14 빌드 = 100개 저장

2025-09-09 오전 10:04 오류 발생 = 기본키 값 누락 -> 가끔 JSON 파일에서 original link, description이 비어있는 경우가 있음

2025-09-09 오전 11:30 = 100개저장, link를 파티션 키(기본 키)로 변경

2025-09-10 오전 10:39 = 어제날짜의 뉴스정보를 읽어오는 파이썬 파일을 만들었음. 다만 아직 읽어오고 파이썬에서 print하도록 만들었을 뿐이므로, 어떻게 활용할지 생각해야 함

2025-09-10 오후 2:50 = 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업. Layer 설정 부족, boto 충돌 , Deserializer() 오류 해결 필요

2025-09-10 오후 3:53 = 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업 Layer 설치시 Linux 기반으로 변경, TypeDeserializer() 으로 변경,  DynamoDB에 반영되지 않아서 확인

2025-09-10 오후 4:37 = 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업 환경변수 TABLE_NAME value값에 오입력된 공백 제거, 로그를 통한 API 회신 확인, Free Tier 호출 제한 발생

2025-09-10 오후 4:51 = 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업 time.sleep(1)을 적용하여 분당 요청수 제한을 넘지 않도록 설정

2025-09-10 오후 4:51 = 해당 Actions를 트리거로 하는 lambda 함수를 작성해서 테스트 작업 import time 작성

요약 : Python, GitHub Actions와 Amazion Free tier일때 사용하기 적합한 DynamoDB, 네이버 검색 API를 이용한 간단한 뉴스 수집도구

**GitHub Actions** - 자동화
해당 Repository의 workflows yml파일에 따라, 20분마다 py파일을 이용하여 100개의 뉴스기사를 수집한다.

Repository에서 미리 지정한 액세스 코드를 통하여, Amazon DynamoDB에 접근하여 데이터를 저장한다.

해당 Repository가 'Public'인 이상, 비용은 발생하지 않는다. 


**Amazon DynamoDB** - 데이터베이스 
프리티어 기준으로 25GB와 빠른 읽기/쓰기를 제공한다.


**IAM** - DB접근 권한
GitHub Actions가 DynamoDB 접근하기 위해 먼저 설정해야 하는 부분이다.


사용자 그룹(GitHub Worker로 지정함)을 생성하여 DynamoDB 접근권한만을 부여하고, CLI 액세스코드를 생성하여 GitHub Actions가 사용할 수 있도록 했다.


**네이버 API** - API
keyword를 뉴스, 갯수를 100개, date순(최신순)으로 하여 뉴스정보 100개를 수집한다.

API를 이용하기 때문에 response로 받는 JSON 파일 안의 정보외에는 획득 할 수 없지만, 크롤링을 방법을 생각해보지 않은 지금은 가장 쉬운 방법이다.




생각할 점
- 보안 : GitHub Actions에겐 Amazon IAM에서 CLI 액세스 코드를 통하여 DynamoDB의 모든 권한을 부여하였는데, 조금 더 강한 보안을 위해서라면 다른 방법으로 권한을 부여하거나, DynamoDB에서 쓰기만 가능하도록 만드는 것도 좋아보인다.
- 확장 : 나중에 크롤링을 통해서도 정보를 수집하고, 검색어 트렌드 등과 결합할 수 있을수도 있는데, 이에 대해 생각해보면 좋을 것 같다. (DynamoDB는 RDB와 달리 NoSQL DB형식이라, 크롤링을 통해 원래정보 + 기타정보가 들어오면 그냥 새로운 속성을 같이 사용하여 같은 DynamoDB를 사용해도 문제는 없는 것 같다.)
- 빌드 테스트 : API를 이용한 자동수집은 마무리 되었으나, 이후 수정한다면 수정할때마다 자동으로 테스트하는 기능을 넣으면 좋을 것 같다. (Actions 실행에 앞서, Amazon DynamoDB에 대한 접근권한이 있는지 액세스 해보는 것, API에서 JSON파일을 제대로 받아오는지 등)
- Airflow : Airflow를 실습한 뒤 Actions를 사용하였는데, 매우 단순한 작업이라면 Actions를 이용한 작업으로 충분하나, 복잡해지거나 순환과정 같은 부분이 생길경우 AirFlow가, DAG가 서로 얽혀 관리가 필요하다면 Kubernetes가 사용된다. 

