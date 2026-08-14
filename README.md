# Practice

## 주말 일정 생성기 스킬

`.claude/skills/weekend-schedule-generator/` — 테마를 고르면 성격이 다른 5명이
최소 4라운드 토론해서 주말 시간표를 만드는 Claude Code 스킬.

### 쓰는 법

이 저장소에서 Claude Code를 열고 그냥 말하면 된다.

```
이번 주말 계획 좀 짜줘
토요일에 성수에서 친구 만나는데 하루 코스 짜줘
집에서 보내는 주말인데 청소랑 쉬는 거 반반으로
```

### 어떻게 동작하나

| 역할 | 하는 일 |
|---|---|
| 🖤 블랙 | 일정을 짜고 지적을 받아 고친다 |
| ❤️ 레드 | 효율·테마 적합성을 냉정하게 평가하고 과밀한 항목을 잘라낸다 |
| 💙 블루 | 업그레이드 아이디어와 우천·혼잡 대안을 붙인다 |
| 🩶 실버 | 20년 경력 살림 전문가. 집안일 순서와 현실적 소요 시간을 잡는다 |
| 💛 골드 | 안목 있는 인플루언서. 장소·시간대·아이템을 챙긴다 |

최소 4라운드(하한이지 목표가 아니다) 토론 후 5명이 5개 항목(테마 적합성 / 동선 효율 /
다양성 / 실행 가능성 / 완성도)을 채점한다. 평균 9.5점 미만이면 **최저점을 준 사람이
개선안을 직접 제시**하고 블랙이 그 항목만 고쳐 재채점한다.

점수는 **일정의 실제 품질에만** 근거한다. 라운드를 많이 돌았다는 이유로 점수를
올리지 않으며, 최선을 다해도 9.2라면 9.2로 보고하고 무엇이 충돌하는지 설명한다.

### 고정 규칙 — 매주 꼭 해야 하는 것

`references/recurring-rules.md`에 반복 활동을 주기와 함께 적어두면, 일정 생성 때마다
가장 먼저 읽어서 **주기가 돌아온 항목을 초안에 넣는다.**

| 활동 | 주기 | 마지막 실행 | 배치 힌트 |
|---|---|---|---|
| 화분 물주기 | 2주 | 2026-08-02 | 아침, 5~10분. 외출 전에 |
| 다음 주 입을 옷 정하기 | 매주 | 2026-08-09 | 일요일 저녁. 건조 끝난 뒤 |

`마지막 실행 + 주기 ≤ 주말 마지막 날`이면 도래로 보고, 일정에 없으면 검증에서
ERROR로 잡힌다. 일정이 확정되면 마지막 실행 날짜를 갱신한다.
새 규칙은 이 표에 줄을 추가하거나, Claude에게 "앞으로 주말마다 ~할래"라고 말하면 된다.

### 하드 제약

- 하루 5개 이상 활동 (식사·이동 제외)
- 같은 활동 반복 금지, 같은 카테고리 하루 2회까지
- 동선 핑퐁(A→B→A) 금지, 지역 이동 하루 2회 이하
- 활동 간 버퍼 15분, 지역 이동 시 이동시간 + 15분
- 주기가 돌아온 고정 규칙 이행
- 5인 평균 9.5점 이상, 개별 9.0점 미만 없음

이 제약은 눈으로 확인하지 않고 스크립트로 검증한다:

```bash
python3 .claude/skills/weekend-schedule-generator/scripts/validate_schedule.py \
        .claude/skills/weekend-schedule-generator/assets/example-schedule.json \
        --rules .claude/skills/weekend-schedule-generator/references/recurring-rules.md
```

`assets/example-schedule.json`은 고정 규칙 포함 모든 제약을 통과하는 예시다.

### 구성

```
.claude/skills/weekend-schedule-generator/
├── SKILL.md                        # 진행 순서, 상황별 무게중심
├── references/
│   ├── recurring-rules.md          # 내 고정 반복 활동 (여기를 편집)
│   ├── personas.md                 # 5인의 성격과 체크리스트
│   ├── debate-protocol.md          # 라운드 구조, 채점 5항목, 점수 인플레 방지
│   ├── themes.md                   # 생산성 / 휴식 / 소셜 / 집콕 정비
│   └── schedule-schema.md          # 검증용 JSON 형식
├── scripts/validate_schedule.py    # 하드 제약 자동 검증
└── assets/
    ├── output-template.md          # 최종 출력 템플릿
    └── example-schedule.json       # 통과 예시
```
