#!/usr/bin/env python3
"""예측을 채점한다. 두 판을 동시에 비교할 수 있다. 의존성 없음.

    python3 scripts/score.py 20260824 --key _대결_20260824

종가 파일(prices-YYYYMMDD.json)만 있으면 나머지는 predictions.json에서 읽는다.
**방향 적중과 절대오차를 나눠서 본다** — 이 모형에서 믿을 건 방향이지 크기가 아니다
(관측 14건에서 방향 13/14, 그런데 함의된 k는 0.5~5.8로 흩어졌다).
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")


def load(n):
    with open(os.path.join(D, n), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="채점할 날짜 YYYYMMDD (그날 종가 파일을 읽는다)")
    ap.add_argument("--key", default="_대결_20260824", help="predictions.json의 대결 블록 키")
    a = ap.parse_args()

    px = load(f"prices-{a.date}.json")
    duel = load("predictions.json")[a.key]
    base = duel["기준가_8/21_종가"]
    sets = {k: v for k, v in duel.items() if k.startswith(("A_", "B_"))}

    names = sorted({n for s in sets.values() for n in s if not n.startswith("_")})
    print("=" * 84)
    print(f"  두 판 채점 — {a.date} 종가")
    print("=" * 84)
    hdr = f"  {'종목':<12}{'기준':>10}{'실제':>10}{'실제%':>8}"
    for k in sets:
        hdr += f"{k.split('_')[0]:>9}{'오차':>8}{'방향':>5}"
    print(hdr)

    tally = {k: {"n": 0, "hit": 0, "err": 0.0} for k in sets}
    for n in names:
        b = base.get(n)
        act = px.get(n) or (px.get("_watch") or {}).get(n)
        if not b or not act:
            print(f"  {n:<12}{'—':>10}{'종가 없음':>12}")
            continue
        ap_ = (act / b - 1) * 100
        line = f"  {n:<12}{b:>10,}{act:>10,}{ap_:>+7.2f}%"
        for k, s in sets.items():
            if n not in s:
                line += f"{'—':>9}{'—':>8}{'—':>5}"
                continue
            pp = s[n]
            err = abs(pp - ap_)
            hit = (pp > 0) == (ap_ > 0)
            t = tally[k]; t["n"] += 1; t["hit"] += hit; t["err"] += err
            line += f"{pp:>+8.2f}%{err:>7.2f}p{'○' if hit else '✗':>5}"
        print(line)

    print("\n" + "=" * 84)
    for k, t in tally.items():
        if not t["n"]:
            continue
        print(f"  {k:<20} 방향 {t['hit']}/{t['n']}   평균 절대오차 {t['err']/t['n']:.2f}%p")
    win = [k for k in tally if tally[k]["n"]]
    if len(win) == 2:
        x, y = win
        hx = tally[x]["hit"] / tally[x]["n"]; hy = tally[y]["hit"] / tally[y]["n"]
        ex = tally[x]["err"] / tally[x]["n"]; ey = tally[y]["err"] / tally[y]["n"]
        print(f"\n  방향: {'A' if hx > hy else 'B' if hy > hx else '무승부'}"
              f"   오차: {'A' if ex < ey else 'B' if ey < ex else '무승부'}")
        print("  ⚠️ **하루 결과다.** 이걸로 한쪽을 폐기하지 않는다. 기록에 넣고 계속 센다.")
    print("  ⚠️ 종목 수가 적고 같은 날이라 **독립 관측이 아니다.** 시장이 한 방향이면 다 같이 맞는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
