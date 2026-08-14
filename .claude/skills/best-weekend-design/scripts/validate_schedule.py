#!/usr/bin/env python3
"""주말 일정 JSON의 하드 제약을 검증한다.

사용법:
    python3 validate_schedule.py schedule.json
    python3 validate_schedule.py schedule.json --rules ../references/recurring-rules.md
    python3 validate_schedule.py schedule.json --window 05:00-21:00

--rules를 주면 주기가 돌아온 고정 규칙이 일정에 들어 있는지도 확인한다.
--window를 주면 모든 활동이 기상~취침 시간대 안에 있는지 확인한다.
형식은 references/schedule-schema.md 참고.
ERROR가 하나라도 있으면 종료 코드 1.
"""

import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta

# 활동 수에 포함하지 않는 카테고리
NOT_COUNTED = {"식사", "이동"}
# 하루 2회 초과가 허용되는 카테고리
UNLIMITED = {"식사", "휴식", "이동"}
HOME_ZONES = {"집", "자택", "home", "house"}

PERSONAS = ["블랙", "레드", "블루", "실버", "골드"]
MIN_ACTIVITIES_PER_DAY = 5
MIN_BUFFER_MIN = 15
MAX_ZONE_MOVES_PER_DAY = 2
MAX_TRAVEL_MIN_PER_DAY = 90
MIN_AVERAGE_SCORE = 9.5
MIN_INDIVIDUAL_SCORE = 9.0

problems = []  # (severity, message)


def err(msg):
    problems.append(("ERROR", msg))


def warn(msg):
    problems.append(("WARN", msg))


def parse_time(value, where):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}:\d{2}", value.strip()):
        err(f"{where}: 시각 형식이 HH:MM이 아님 ({value!r})")
        return None
    hh, mm = value.strip().split(":")
    hh, mm = int(hh), int(mm)
    if hh > 47 or mm > 59:
        err(f"{where}: 시각 범위를 벗어남 ({value!r})")
        return None
    return hh * 60 + mm


def fmt_min(total):
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_window(text):
    """'05:00-21:00' → (300, 1260)"""
    m = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})\s*", str(text))
    if not m:
        print(f"--window 형식이 잘못됨: {text!r} (예: 05:00-21:00)")
        return None
    start = parse_time(m.group(1), "--window 시작")
    end = parse_time(m.group(2), "--window 종료")
    if start is None or end is None:
        return None
    if end <= start:
        end += 24 * 60
    return start, end


def normalize(title):
    return re.sub(r"\s+", " ", str(title)).strip().lower()


def is_home(zone):
    return str(zone).strip().lower() in HOME_ZONES


def check_day(day, index, window=None):
    label = day.get("label") or f"{index + 1}일차"
    acts = day.get("activities") or []
    if not acts:
        err(f"[{label}] 활동이 없음")
        return []

    # --- 시각 파싱 및 순서/겹침 ---
    spans = []
    for i, act in enumerate(acts):
        where = f"[{label}] {i + 1}번째 활동 '{act.get('title', '?')}'"
        start = parse_time(act.get("start"), where + " start")
        end = parse_time(act.get("end"), where + " end")
        if start is None or end is None:
            continue
        if end <= start:
            end += 24 * 60  # 자정을 넘긴 것으로 해석
            if end - start > 12 * 60:
                err(f"{where}: 종료 시각이 시작보다 이름 ({act.get('start')}~{act.get('end')})")
                continue
        spans.append((start, end, act, where))

    # --- 기상~취침 시간대 ---
    if window:
        win_start, win_end = window
        for start, end, act, where in spans:
            if start < win_start:
                err(f"{where}: 기상 시각({fmt_min(win_start)}) 이전에 시작 ({act.get('start')})")
            if end > win_end:
                err(f"{where}: 취침 시각({fmt_min(win_end)}) 이후까지 이어짐 ({act.get('end')})")

    for prev, cur in zip(spans, spans[1:]):
        prev_end, cur_start = prev[1], cur[0]
        if cur_start < prev_end:
            err(f"{cur[3]}: 앞 활동과 시간이 겹침 (앞 활동 종료 {prev[2].get('end')}, 시작 {cur[2].get('start')})")
            continue
        gap = cur_start - prev_end
        travel = int(cur[2].get("travel_min_from_prev") or 0)
        zone_changed = str(prev[2].get("zone", "")).strip() != str(cur[2].get("zone", "")).strip()
        if zone_changed:
            need = travel + MIN_BUFFER_MIN
            if gap < need:
                err(
                    f"{cur[3]}: 지역 이동 여유 부족 (간격 {gap}분 < 이동 {travel}분 + 버퍼 {MIN_BUFFER_MIN}분)"
                )
        elif gap < MIN_BUFFER_MIN:
            warn(f"{cur[3]}: 앞 활동과 간격 {gap}분 (권장 {MIN_BUFFER_MIN}분 이상)")

    # --- 활동 수 ---
    counted = [a for a in acts if str(a.get("category", "")).strip() not in NOT_COUNTED]
    if len(counted) < MIN_ACTIVITIES_PER_DAY:
        err(
            f"[{label}] 활동 {len(counted)}개 (식사·이동 제외 기준 {MIN_ACTIVITIES_PER_DAY}개 이상 필요)"
        )

    # --- 카테고리 반복 ---
    cat_counts = Counter(str(a.get("category", "미지정")).strip() for a in acts)
    for cat, n in cat_counts.items():
        if cat not in UNLIMITED and n > 2:
            err(f"[{label}] '{cat}' 카테고리가 {n}회 반복 (하루 2회까지)")

    # --- 동선: 핑퐁 및 이동 횟수 ---
    zones = []
    for a in acts:
        z = str(a.get("zone", "")).strip()
        if not z:
            warn(f"[{label}] '{a.get('title', '?')}'에 zone이 비어 있어 동선 검사에서 제외")
            continue
        if not zones or zones[-1] != z:
            zones.append(z)

    # 집은 동선 검사에서 제외한다. 집에 들렀다 다시 나가는 건 핑퐁이 아니라
    # 집을 기점으로 사는 사람의 정상적인 하루다. 진짜 핑퐁은 바깥 지역이
    # 다시 등장할 때(강남 → 성수 → 강남)이고, 그건 아래 검사에 그대로 걸린다.
    trimmed = [z for z in zones if not is_home(z)]

    repeated = [z for z, n in Counter(trimmed).items() if n > 1]
    if repeated:
        err(
            f"[{label}] 동선 핑퐁: {' → '.join(zones)} "
            f"(같은 지역으로 되돌아옴: {', '.join(repeated)})"
        )

    moves = len(trimmed)  # 집 밖으로 나가는 횟수
    if moves > MAX_ZONE_MOVES_PER_DAY:
        warn(f"[{label}] 지역 이동 {moves}회 (권장 {MAX_ZONE_MOVES_PER_DAY}회 이하): {' → '.join(zones)}")

    total_travel = sum(int(a.get("travel_min_from_prev") or 0) for a in acts)
    if total_travel > MAX_TRAVEL_MIN_PER_DAY:
        warn(f"[{label}] 총 이동 {total_travel}분 (권장 {MAX_TRAVEL_MIN_PER_DAY}분 이하)")

    # --- 이동 대비 체류 (레드의 기준) ---
    # 집으로 돌아오는 구간은 '방문'이 아니므로 제외한다.
    for start, end, act, where in spans:
        travel = int(act.get("travel_min_from_prev") or 0)
        stay = end - start
        if travel > 0 and not is_home(act.get("zone", "")) and stay < travel * 2:
            warn(f"{where}: 이동 {travel}분 대비 체류 {stay}분 (이동의 2배 이상 머무는 게 기본)")

    return [normalize(a.get("title", "")) for a in acts if str(a.get("category", "")).strip() not in NOT_COUNTED]


def parse_period_days(text):
    """'2주', '매주', '격주', '월 1회', '2주일에 1번' 등을 일수로 바꾼다."""
    t = str(text).strip()
    if "매일" in t:
        return 1
    if "매주" in t:
        return 7
    if "격주" in t:
        return 14
    if "매월" in t or "매달" in t:
        return 30
    m = re.search(r"(\d+)\s*(주일|주|개월|달|일)", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit in ("주", "주일"):
            return n * 7
        if unit in ("개월", "달"):
            return n * 30
        return n
    if "월" in t:
        return 30
    if "주" in t:
        return 7
    return None


def parse_rules(path):
    """recurring-rules.md의 마크다운 표에서 (이름, 주기일수, 마지막실행) 목록을 뽑는다.

    '조건부' 규칙은 스크립트가 판정할 수 없으므로 목록만 알려주고 검사는 하지 않는다.
    """
    rules = []
    conditional = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        err(f"고정 규칙 파일을 읽을 수 없음: {exc}")
        return rules

    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = re.sub(r"[`*_]", "", cells[0]).strip()
        if not name or name == "활동" or set(name) <= set("-: "):
            continue  # 헤더 또는 구분선

        if "조건부" in cells[1] or "필요시" in cells[1]:
            conditional.append(name)
            continue

        period = parse_period_days(cells[1])
        if period is None:
            warn(f"고정 규칙 '{name}': 주기 '{cells[1]}'를 해석할 수 없어 검사에서 제외")
            continue

        last = None
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", cells[2])
        if m:
            try:
                last = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                warn(f"고정 규칙 '{name}': 마지막 실행 날짜 '{cells[2]}'가 올바르지 않음")
        rules.append((name, period, last))

    if not rules and not conditional:
        warn(f"고정 규칙을 하나도 읽지 못함 ({path}) — 표 형식을 확인할 것")
    if conditional:
        print(f"  조건부 규칙(직접 판단 필요): {', '.join(conditional)}")
    return rules


def weekend_end_date(days):
    """일정에 적힌 날짜 중 가장 늦은 날. 없으면 오늘."""
    found = []
    for day in days:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(day.get("date") or ""))
        if m:
            try:
                found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
            except ValueError:
                pass
    return max(found) if found else datetime.now().date()


def check_rules(rules, days, end_date):
    titles = [
        re.sub(r"\s+", "", str(a.get("title", ""))).lower()
        for day in days
        for a in (day.get("activities") or [])
    ]

    # 규칙 이름의 모든 낱말이 제목에 들어 있으면 이행으로 본다.
    # 단순 부분문자열로 보면 '꽃병 물갈이'가 '수경 꽃병 4개 물갈이'에 안 걸린다 —
    # 제목에는 개수나 위치 같은 말이 중간에 끼기 마련이다.
    for name, period, last in rules:
        tokens = [w.lower() for w in name.split() if w]
        present = any(all(tok in t for tok in tokens) for t in titles)
        due = last is None or (end_date - last).days >= period

        if due and not present:
            when = f"마지막 실행 {last} + {period}일" if last else "마지막 실행 미기록"
            err(f"고정 규칙 누락: '{name}' — 주기 도래 ({when}) 인데 일정에 없음")
        elif due and present:
            print(f"  고정 규칙 이행: '{name}' ✔")
        elif present and last is not None:
            next_due = last + timedelta(days=period)
            warn(
                f"고정 규칙 '{name}'은 아직 주기 전 (다음 차례 {next_due}) — "
                "이번 주말에 굳이 넣을 필요는 없음"
            )


def check_scores(scores):
    if not isinstance(scores, dict) or not scores:
        err("scores가 없음 — 5인 채점 결과가 필요함")
        return
    missing = [p for p in PERSONAS if p not in scores]
    if missing:
        err(f"채점자 누락: {', '.join(missing)}")

    averages = {}
    for name, value in scores.items():
        if isinstance(value, dict):
            nums = [v for v in value.values() if isinstance(v, (int, float))]
            if not nums:
                err(f"{name}의 점수 항목이 비어 있음")
                continue
            avg = sum(nums) / len(nums)
        elif isinstance(value, (int, float)):
            avg = float(value)
        else:
            err(f"{name}의 점수 형식이 잘못됨 ({value!r})")
            continue
        averages[name] = avg
        if avg < MIN_INDIVIDUAL_SCORE:
            err(f"{name} 평균 {avg:.2f}점 (개별 {MIN_INDIVIDUAL_SCORE}점 미만은 재작업 대상)")

    if averages:
        overall = sum(averages.values()) / len(averages)
        detail = ", ".join(f"{k} {v:.2f}" for k, v in averages.items())
        if overall < MIN_AVERAGE_SCORE:
            err(f"최종 평균 {overall:.2f}점 (기준 {MIN_AVERAGE_SCORE}점) — {detail}")
        else:
            print(f"  최종 평균 {overall:.2f}점 ({detail})")


def main():
    args = sys.argv[1:]
    rules_path = None
    window = None

    for flag in ("--rules", "--window"):
        if flag not in args:
            continue
        i = args.index(flag)
        if i + 1 >= len(args):
            print(f"{flag} 뒤에 값이 필요합니다")
            return 2
        value = args[i + 1]
        del args[i : i + 2]
        if flag == "--rules":
            rules_path = value
        else:
            window = parse_window(value)
            if window is None:
                return 2

    if len(args) != 1:
        print(__doc__)
        return 2

    try:
        with open(args[0], encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없음: {args[0]}")
        return 2
    except json.JSONDecodeError as exc:
        print(f"JSON 파싱 실패: {exc}")
        return 2

    if not data.get("theme"):
        warn("theme이 비어 있음")

    days = data.get("days") or []
    if not days:
        err("days가 비어 있음")

    all_titles = []
    for i, day in enumerate(days):
        all_titles += check_day(day, i, window)

    for title, n in Counter(t for t in all_titles if t).items():
        if n > 1:
            err(f"활동 중복: '{title}'이(가) 주말 전체에서 {n}회 등장")

    if rules_path:
        check_rules(parse_rules(rules_path), days, weekend_end_date(days))

    check_scores(data.get("scores"))

    errors = [m for s, m in problems if s == "ERROR"]
    warns = [m for s, m in problems if s == "WARN"]

    print()
    for m in errors:
        print(f"  ERROR  {m}")
    for m in warns:
        print(f"  WARN   {m}")

    print()
    if errors:
        print(f"❌ ERROR {len(errors)}건, WARN {len(warns)}건 — 토론으로 돌아가 고칠 것")
        return 1
    if warns:
        print(f"✅ 하드 제약 통과 (WARN {len(warns)}건 — 이유를 설명할 수 있으면 진행)")
    else:
        print("✅ 모든 제약 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
