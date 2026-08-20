#!/usr/bin/env python3
"""오늘 걸려 있는 촉매를 기계적으로 뽑는다. 의존성 없음.

**이 스크립트가 없어서 두 번 틀렸다.**
  · 2026-08-16 사용자가 "엔비디아 투자·삼성 주주환원 반영했냐"고 물었을 때 둘 다 못 했다
  · 2026-08-20 삼성전자 주주환원 이벤트를 events.json에 등록해두고도
    브리핑에 안 올렸다. 그날 SK하이닉스 40조 주주환원 발표로 삼성이 +9.49% 갔다

두 번 다 원인이 같다 — **"읽어야 한다"는 규칙에만 의존했다.**
읽는 걸 잊는 게 정상이므로 기계가 뽑아준다. 아침 브리핑에서 이걸 먼저 돌린다.

    python3 scripts/events_due.py            # 오늘 기준
    python3 scripts/events_due.py 2026-09-01 # 특정 날짜 기준
"""
import json, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "..", "data", "events.json")


def parse_window(s):
    """'2026-08~3분기', '2026.08', 'Q4 2026~1H 2027' 같은 표기에서 연·월을 뽑는다."""
    ys = [int(y) for y in re.findall(r"20\d\d", str(s))]
    ms = [int(m) for m in re.findall(r"(?:^|[-.\s])(\d{1,2})월", str(s))]
    ms += [int(m) for m in re.findall(r"20\d\d[-.](\d{1,2})", str(s))]
    q = re.findall(r"(\d)\s*분기|Q(\d)", str(s))
    for a, b in q:
        ms.append(int(a or b) * 3)
    return ys, ms


def main():
    today = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    with open(EV, encoding="utf-8") as fh:
        data = json.load(fh)

    due, soon, undated = [], [], []
    for e in data.get("events", []):
        when = str(e.get("시점", ""))
        ys, ms = parse_window(when)
        if not ys:
            undated.append(e)
            continue
        # 창이 오늘을 포함하거나, 3개월 안에 시작하면 잡는다
        lo = min(ys) * 12 + (min(ms) if ms else 1)
        hi = max(ys) * 12 + (max(ms) if ms else 12)
        now = today.year * 12 + today.month
        (due if lo <= now <= hi else soon if 0 < lo - now <= 3 else []).append(e) \
            if (lo <= now <= hi or 0 < lo - now <= 3) else None

    print("=" * 72)
    print(f"  오늘 걸려 있는 촉매 — {today}")
    print("=" * 72)
    if not due:
        print("  창이 열린 이벤트 없음")
    for e in due:
        flag = "확정" if e.get("확정") else "**미정**"
        print(f"\n  ▸ [{e.get('종목','—')}] {e.get('시점')}  {flag}")
        print(f"    {e.get('내용','')}")
        if e.get("왜중요"):
            print(f"    → 내 어느 계산에 들어가나: {e['왜중요'][:110]}")
        if e.get("쓰지않는것"):
            print(f"    ⚠️ 쓰지 않는 것: {e['쓰지않는것'][:90]}")

    if soon:
        print(f"\n  ── 3개월 안에 시작 ──")
        for e in soon:
            print(f"    · [{e.get('종목','—')}] {e.get('시점')} — {e.get('내용','')[:70]}")
    if undated:
        print(f"\n  ── 시점 미상 {len(undated)}건 (직접 확인) ──")
        for e in undated:
            print(f"    · [{e.get('종목','—')}] {e.get('내용','')[:70]}")

    print("\n" + "=" * 72)
    print("  창이 열린 이벤트는 **브리핑에 반드시 한 줄 올린다.**")
    print("  '아직 발표 안 됨'도 정보다 — 그게 오늘 급등락의 후보다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
