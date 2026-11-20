# 로또 6/45 번호 추첨기 (GitHub + Netlify 배포용 스타터)

## 폴더 구성
- `index.html` : 메인 웹페이지 (40~60대 맞춤 고대비 UI, 5게임 순차 추첨, 이미지 저장/공유)
- `data/lotto.json` : 역대 당첨번호 데이터베이스 (매주 자동 갱신)
- `scripts/update_lotto.py` : 동행복권 최신 회차 수집 스크립트
- `.github/workflows/update-lotto.yml` : 매주 토요일 밤 9시 15분 자동 실행 워크플로우

## 사용 방법
1. GitHub에 새 저장소(Repository)를 만들고 이 폴더의 파일들을 모두 업로드합니다.
2. Netlify에서 `Add new site` -> `Import an existing project` -> `GitHub`를 선택해 위 저장소를 연결합니다.
3. GitHub 저장소 상단 `Actions` 탭에서 자동 업데이트 워크플로우를 활성화합니다.
4. 이후 매주 토요일 밤 GitHub가 `data/lotto.json`을 갱신하면 Netlify가 자동으로 사이트를 최신 상태로 재배포합니다.
