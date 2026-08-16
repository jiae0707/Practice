#!/usr/bin/env python3
"""보유 종목을 같은 기준으로 줄 세운다. 어디에 돈을 넣을지 정하는 표.

    python3 compare.py

PBR 밴드 중립 시나리오 기준 1년·3년 기대수익률에 배당을 더해 정렬한다.
**같은 방식으로 계산해야 비교가 성립한다.** 종목마다 다른 잣대를 쓰면
비교표가 아니라 인상의 나열이 된다.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# 종목별 PBR 밴드(실측 과거 범위)와 정상화 ROE
BANDS = {
    "현대차":   {"lo": 0.51, "hi": 0.96, "roe": 8.45,  "payout": 28.1},
    "한국전력": {"lo": 0.32, "hi": 0.63, "roe": 9.06,  "payout": 11.8},
    "네이버":   {"lo": 1.15, "hi": 1.45, "roe": 6.78,  "payout": 20.0},
    "삼성전자": {"lo": 0.92, "hi": 2.51, "roe": 10.85, "payout": 16.2,
                "note": "2026E ROE 55.83%는 피크. 2025년 실적치 10.85%로 정상화"},
}


def main():
    with open(os.path.join(DATA, "financials.json"), encoding="utf-8") as fh:
        fin = json.load(fh)

    rows = []
    for name, b in BANDS.items():
        blk = fin.get(name)
        if not blk:
            continue
        last = blk["annual"]["2026.12E"]
        px, bps, dps = blk["price"], last["bps"], last["dps"]
        cur = px / bps
        mid = (b["lo"] + b["hi"]) / 2
        g = b["roe"] / 100 * (1 - b["payout"] / 100)
        dy = dps / px
        r1 = (bps * (1 + g) ** 1 * mid / px - 1) + dy
        r3 = (bps * (1 + g) ** 3 * mid / px - 1) + dy * 3
        pos = (cur - b["lo"]) / (b["hi"] - b["lo"])   # 밴드 내 위치 0~1
        rows.append((r1, r3, name, px, cur, b["lo"], b["hi"], pos,
                     b["roe"], dy, g, b.get("note")))

    rows.sort(reverse=True)
    print(f"\n{'='*78}")
    print("  보유 종목 비교 — PBR 밴드 중립 시나리오 + 배당 (총수익률)")
    print(f"{'='*78}")
    print(f"  {'종목':<9}{'현재가':>10}{'PBR':>7}{'밴드':>14}{'위치':>7}"
          f"{'ROE':>7}{'배당':>7}{'1년':>9}{'3년':>9}")
    print("  " + "-" * 74)
    for r1, r3, nm, px, cur, lo, hi, pos, roe, dy, g, note in rows:
        band = f"{lo:.2f}~{hi:.2f}"
        loc = ("하단" if pos < 0.3 else "상단" if pos > 0.7 else "중간")
        print(f"  {nm:<9}{px:>10,}{cur:>7.2f}{band:>14}{loc:>7}"
              f"{roe:>6.2f}%{dy*100:>6.2f}%{r1*100:>+8.1f}%{r3*100:>+8.1f}%")

    print("\n  ▸ 읽는 법")
    print("    · 밴드 '하단'이면 되돌림 여지가 크고, '상단'이면 이미 반영됐다는 뜻")
    print("    · ROE가 자본비용(대략 7~9%)보다 낮으면 성장해도 가치가 안 는다")
    print("    · 1년·3년은 **PBR이 밴드 중간으로 돌아온다**는 가정 하나에만 의존한다")
    for r in rows:
        if r[-1]:
            print(f"\n  ⚠️  {r[2]}: {r[-1]}")
    print(f"\n{'='*78}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
