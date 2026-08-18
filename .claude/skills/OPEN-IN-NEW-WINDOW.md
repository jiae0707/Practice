# 스킬별 새 창 열기

세 스킬을 각각 다른 창에서 다루려면 **claude.ai/code에서 새 세션을 만들고
저장소를 `jiae0707/Practice`로 지정한 뒤 아래 프롬프트를 붙여넣는다.**

브랜치는 셋 다 `claude/weekend-schedule-generator-8cnp60`을 쓴다.
같은 저장소를 보므로 서로의 변경이 보인다 — 다른 창에서 커밋했으면
작업 전에 `git pull origin claude/weekend-schedule-generator-8cnp60`을 한다.

---

## 1️⃣ 주말 설계 — `best-weekend-design`

```
best-weekend-design 스킬로 이번 주말(2026년 8월 22일 토요일 ~ 23일 일요일)
일정을 설계해줘.

시작 전에 반드시:
1. .claude/context/about-me.md 를 읽는다 (CLAUDE.md의 첫 번째 규칙)
2. .claude/skills/best-weekend-design/references/recurring-rules.md 에서
   주기 활동의 마지막 실행 날짜를 확인한다
3. 5인 페르소나 토론을 최소 4라운드 돌린다
4. scripts/validate_schedule.py 로 하드 제약을 기계적으로 검증한다

특히 조심할 것 — 기상 05:00 / 취침 21:00이라 20시 이후 일정은 성립하지 않는다.
자전거는 있고 자동차는 없어서 지하철은 비용 때문에 후순위다.
요리를 못 하므로 메뉴를 제안하면 레시피까지 준다.
미술과 숲을 좋아하고 미니멀·우드톤 취향이다.

장소·전시·영업시간은 검색으로 확인한 것만 사실로 쓴다.
확인 못 했으면 "확인 필요"라고 밝힌다.

결과는 큰 블록 + 체크리스트 두 층으로 내고, 선택지가 갈리는 자리는
후보 2~3개를 성격과 함께 낸다.

브랜치 claude/weekend-schedule-generator-8cnp60 에서 작업하고 커밋·푸시한다.
```

---

## 2️⃣ 평일 저녁 루틴 — `weekday-evening`

```
weekday-evening 스킬을 점검해줘. 아직 실전에서 안 써본 스킬이라
빠진 것과 모순을 먼저 찾고 싶다.

1. .claude/context/about-me.md 를 읽고 시작한다
2. SKILL.md와 references를 전부 읽는다
3. 다음을 점검한다:
   - 퇴근 17:00, 저녁 안 먹음, 취침 21:00이라 17:30~21:00이 통째로 비는데
     그 시간 구조가 현실적인가
   - 게임·넷플릭스를 없애지 않고 순서만 바꾼다는 원칙이 실제로 지켜지는 설계인가
   - 운동과 영어의 강도가 매일 같은가, 요일별로 달라야 하는가
   - kr-stock-council에 있는 장치 중 여기에도 필요한 게 있는가
     (반증 조건, 신뢰등급, 결론 이력 같은 것)
4. 고칠 것을 목록으로 내고, 동의를 받은 뒤 고친다

브랜치 claude/weekend-schedule-generator-8cnp60 에서 작업하고 커밋·푸시한다.
```

---

## 3️⃣ 주식 협의체 — `kr-stock-council`

> ⚠️ 아침 브리핑은 **기존 창**에서 계속한다. 이 창은 **스킬 자체를 손보는 용도**다.

```
kr-stock-council 스킬을 점검해줘. 매일 브리핑은 다른 창에서 돌리고 있고,
이 창에서는 스킬 자체의 구조를 본다.

1. SKILL.md와 references 7개, scripts 10개를 전부 읽는다
2. 다음을 점검한다:
   - data/decisions.json 의 표류율을 확인하고 (scripts/decisions.py --audit)
     표류가 잦은 종목에 어떤 장치가 더 필요한지
   - references 사이에 서로 모순되는 규칙이 없는지
     (특히 daily-brief.md, decision-protocol.md, future-value.md)
   - scripts 중 안 쓰이는 것, 중복되는 것이 있는지
   - 아직 미해결로 남은 것: 화인베스틸 자본총계·부채비율(fnguide 차단),
     VIX 일별 데이터 수집 경로
3. 고칠 것을 목록으로 내고, 동의를 받은 뒤 고친다

브랜치 claude/weekend-schedule-generator-8cnp60 에서 작업하고 커밋·푸시한다.
```

---

## 창을 나눌 때 주의

| | |
|---|---|
| **같은 브랜치** | 셋 다 같은 브랜치를 쓴다. 작업 전에 `git pull` |
| **충돌 지점** | `data/` 아래 파일을 두 창이 동시에 고치면 충돌한다. 스킬 폴더 안에서만 작업하면 안전하다 |
| **CLAUDE.md** | 세 창 모두 자동으로 읽는다. `about-me.md`를 먼저 읽으라는 규칙도 그대로 적용된다 |
| **브리핑** | 매일 05:10 브리핑은 **기존 창**에서 한다. 새 창 3개는 스킬 개발용이다 |
