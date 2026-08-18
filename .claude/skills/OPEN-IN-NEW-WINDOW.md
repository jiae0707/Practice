# 스킬별 새 창 열기

세 스킬을 각각 다른 창에서 다룬다. **claude.ai/code에서 새 세션을 만들고
저장소를 `jiae0707/Practice`로 지정한 뒤 아래 프롬프트를 붙여넣는다.**

---

## 브랜치는 창마다 하나씩 쓴다

같은 브랜치를 셋이 쓰면 한 창이 커밋할 때마다 나머지 둘의 푸시가 막힌다.
매번 `git pull`을 기억해야 하는데, 그걸 잊는 게 정상이다.
**창마다 브랜치를 따로 두면 서로를 막지 않는다.**

대신 합치는 기준점이 하나 필요하다 —
**기준 브랜치는 `claude/weekend-schedule-generator-8cnp60`** (저장소 기본 브랜치).
모든 창은 여기서 갈라지고, 작업이 끝나면 여기로 합친다.

| 창 | 스킬 | 브랜치 |
|---|---|---|
| **기준** | — | `claude/weekend-schedule-generator-8cnp60` |
| 1️⃣ | `best-weekend-design` | `claude/weekend-scheduling-gkj7zq` |
| 2️⃣ | `weekday-evening` | `claude/weekday-schedule-skill-migration-3s1kgi` |
| 3️⃣ | `kr-stock-council` | *(창을 열면 정해진다 — 정해진 이름을 여기 적는다)* |

**브랜치 이름은 새 창을 열 때 자동으로 붙는다. 고를 수 없다.**
그래서 붙은 이름을 이 표에 적어두는 게 나중에 그 창을 다시 찾는 유일한 방법이다.

### 창을 열 때 · 닫을 때

| 언제 | 무엇을 |
|---|---|
| **작업 시작** | `git fetch origin && git merge origin/claude/weekend-schedule-generator-8cnp60` — 다른 창이 올린 걸 먼저 받는다 |
| **작업 끝** | 자기 브랜치에 커밋 → `git push -u origin <자기 브랜치>` |
| **합칠 때** | 자기 브랜치를 기준 브랜치로 머지한다 (PR을 만들어도 되고 직접 머지해도 된다) |

---

## 공용 파일 — 여기만 조심하면 된다

| 파일 | 누가 쓰나 |
|---|---|
| `CLAUDE.md` | 세 창이 모두 읽는다 |
| `.claude/context/about-me.md` | 세 창이 모두 읽고, **새로 알게 된 걸 세 창이 모두 적는다** |
| `best-weekend-design/references/recurring-rules.md` | 주말 창이 주로 쓰지만 평일 창도 본다 |
| `kr-stock-council/data/*.json` | 주식 창 전용 — 다른 창은 건드리지 않는다 |

**공용 파일을 고쳤으면 그 커밋만 먼저 기준 브랜치로 올린다.**
프로필에 새로 알게 된 한 줄을 안 올려두면, 다른 창이 옛날 프로필로 일정을 짠다.
스킬 폴더 안의 변경은 급하지 않으니 작업이 끝난 뒤에 합쳐도 된다.

각 창이 자기 스킬 폴더 안에서만 움직이면 충돌은 거의 나지 않는다.
충돌이 나는 건 대개 공용 파일 네 개 중 하나다.

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

작업 시작 전에 기준 브랜치를 받아온다:
git fetch origin && git merge origin/claude/weekend-schedule-generator-8cnp60
커밋·푸시는 이 창의 브랜치 claude/weekend-scheduling-gkj7zq 에 한다.
```

---

## 2️⃣ 평일 저녁 루틴 — `weekday-evening`

```
weekday-evening 스킬을 점검해줘. 아직 실전에서 안 써본 스킬이라
빠진 것과 모순을 먼저 찾고 싶다.

1. .claude/context/about-me.md 를 읽고 시작한다
2. SKILL.md와 references를 전부 읽는다
3. 다음을 점검한다:
   - 귀가 18:00, 집 정리 마치면 18:30, 저녁 안 먹음, 취침 21:00이라
     18:30~21:00 2시간 30분이 통째로 비는데 그 시간 구조가 현실적인가
   - 게임·넷플릭스를 없애지 않고 순서만 바꾼다는 원칙이 실제로 지켜지는 설계인가
   - 운동과 영어의 강도가 매일 같은가, 요일별로 달라야 하는가
   - kr-stock-council에 있는 장치 중 여기에도 필요한 게 있는가
     (반증 조건, 신뢰등급, 결론 이력 같은 것)
4. 고칠 것을 목록으로 내고, 동의를 받은 뒤 고친다

작업 시작 전에 기준 브랜치를 받아온다:
git fetch origin && git merge origin/claude/weekend-schedule-generator-8cnp60
커밋·푸시는 이 창의 브랜치 claude/weekday-schedule-skill-migration-3s1kgi 에 한다.
```

---

## 3️⃣ 주식 협의체 — `kr-stock-council`

> ✅ **2026-08-19부터 이 창이 주식 전담이다.** 아침 브리핑도 여기서 한다.
> 기존 창은 더 이상 주식을 다루지 않는다.

새 창을 열 때 붙여넣을 프롬프트는 아래와 같다. 핵심은 **HANDOFF.md를 먼저
읽게 하는 것**이다 — 새 창은 3주치 기억이 없고, 그 문서가 유일한 인수인계다.

```
kr-stock-council 스킬을 이 창에서 전담한다. 매일 아침 브리핑도 여기서 한다.

시작 전에 반드시 이 순서로 읽는다:
1. CLAUDE.md → .claude/context/about-me.md
2. .claude/skills/kr-stock-council/references/HANDOFF.md   ← 인수인계. 가장 중요
3. SKILL.md
4. references/daily-brief.md

HANDOFF.md에 있는 것 — 다른 데서 다시 만들 수 없는 것들이다:
  · 사용자의 투자 제약 (손절을 싫어함, "망한다"의 정의, 장중에 못 움직임)
  · 내가 틀린 5가지 방식과 그 근본 원인
  · 자료 등급제 (1급 4/4 맞음 vs 검색 요약 0/7 맞음)
  · 지금 걸려 있는 지정가 주문 12칸
  · 종목별 반증 조건
  · 장치들이 어떤 실패에서 나왔는지

읽고 나서 먼저 할 일:
  python3 .claude/skills/kr-stock-council/scripts/dart.py --check
  python3 .claude/skills/kr-stock-council/scripts/decisions.py --audit

DART가 열려 있으면 --setup 후에 미확인 5건을 순서대로 처리한다
(현대차 BD 지분, 넥스틸 소송 금액, 화인베스틸 자본총계, 동국산업·비츠로셀 재무).
막혀 있으면 무엇이 막혔는지(키인지 도메인인지) 사용자에게 정확히 알린다.

작업 시작 전에 기준 브랜치를 받아온다:
git fetch origin && git merge origin/claude/weekend-schedule-generator-8cnp60
커밋·푸시는 이 창의 브랜치에 한다.
그 브랜치 이름을 .claude/skills/OPEN-IN-NEW-WINDOW.md 의 표에 적어둔다.
```

---

## 창을 나눌 때 주의

| | |
|---|---|
| **브랜치** | 창마다 하나. 시작할 때 기준 브랜치를 머지하고, 끝나면 기준 브랜치로 합친다 |
| **이름 적기** | 새 창의 브랜치 이름은 자동으로 붙는다. **위 표에 적어두지 않으면 그 창을 다시 못 찾는다** |
| **충돌 지점** | 공용 파일 네 개(위 표). 스킬 폴더 안에서만 작업하면 안전하다 |
| **프로필 갱신** | `about-me.md`를 고쳤으면 **바로** 기준 브랜치로 올린다. 안 올리면 다른 창이 옛날 프로필로 일정을 짠다 |
| **CLAUDE.md** | 세 창 모두 자동으로 읽는다. `about-me.md`를 먼저 읽으라는 규칙도 그대로 적용된다 |
| **브리핑** | 매일 05:10 브리핑은 **기존 창**에서 한다. 새 창 3개는 스킬 개발용이다 |
