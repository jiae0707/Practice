#!/usr/bin/env python3
"""수급 데이터로 회귀를 돌린다. 의존성 없음.

"외국인이 팔았다"는 관찰이고, "외국인 순매수는 익일 수익률을 설명하지 못한다(t=0.4)"가
분석이다. 이 스크립트는 후자를 만든다.

    python3 flows.py --file data/daily-naver.json --name 네이버

돌리는 것:
  · 변동성·VaR — 이 종목 하나가 만드는 일간 손실 분포
  · 외국인 보유율 추세 회귀 — 지분이 실제로 빠지고 있는가, 노이즈인가
  · 수급 → 당일 수익률 — 누가 가격을 움직였는가 (동시성)
  · 수급 → 익일 수익률 — 수급이 내일을 예측하는가 (예측력)
  · 수익률 자기상관 — 모멘텀인가 평균회귀인가
  · 거래량 급증일의 수익률 — 대량 거래가 방향을 담는가

**동시성과 예측력은 다르다.** 외국인이 산 날 주가가 오르는 건 당연하다(그들이 샀으니까).
쓸모 있는 건 "오늘 산 것이 내일을 예측하는가"이고, 대개 예측하지 못한다.
그걸 확인하는 게 이 스크립트의 핵심이다.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from correlation import ols, mean, stdev, corr, TRADING_DAYS  # noqa: E402


def stars(t):
    if t is None:
        return ""
    a = abs(t)
    return ("  *** 유의" if a > 2.6 else "  ** 유의" if a > 2.0
            else "  · 유의하지 않음")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--name", default="종목")
    ap.add_argument("--qty", type=int, help="보유 수량. 넣으면 VaR를 원화로")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as fh:
        blob = json.load(fh)
    rows = blob["rows"] if "rows" in blob else blob
    dates = sorted(k for k in rows if not k.startswith("_"))
    n = len(dates)
    if n < 30:
        print(f"거래일 {n}개 — 회귀에 부족하다")
        return 1

    close = [rows[d]["close"] for d in dates]
    vol = [rows[d].get("volume") for d in dates]
    fo = [rows[d].get("foreign") for d in dates]
    ins = [rows[d].get("inst") for d in dates]
    ind = [rows[d].get("indiv") for d in dates]
    hp = [rows[d].get("hold_pct") for d in dates]

    ret = [math.log(close[i] / close[i - 1]) for i in range(1, n)]

    print(f"=== {args.name} — {dates[0]} ~ {dates[-1]}  ({n}거래일) ===")
    print(f"  종가 {close[0]:,} → {close[-1]:,}  "
          f"({(close[-1]/close[0]-1)*100:+.1f}%)")

    # ── 변동성 ──
    sd = stdev(ret)
    ann = sd * math.sqrt(TRADING_DAYS)
    lo, hi = min(ret), max(ret)
    print(f"\n▸ 변동성")
    print(f"    일간 표준편차 {sd*100:.2f}%   연환산 {ann*100:.1f}%")
    print(f"    최악의 하루 {lo*100:+.2f}%   최고의 하루 {hi*100:+.2f}%")
    print(f"    1일 VaR(95%) {1.645*sd*100:.2f}%   VaR(99%) {2.326*sd*100:.2f}%")
    if args.qty:
        val = close[-1] * args.qty
        print(f"    보유 {args.qty:,}주 = {val:,}원")
        print(f"    → 95% VaR {1.645*sd*val:,.0f}원   99% VaR {2.326*sd*val:,.0f}원")
        print(f"    → 실제 최악의 하루가 오늘 오면 {lo*val:,.0f}원")

    # ── 외국인 보유율 추세 ──
    if all(x is not None for x in hp):
        t_idx = list(range(len(hp)))
        res = ols(hp, [t_idx], ["거래일"])
        print(f"\n▸ 외국인 보유율 추세")
        print(f"    {hp[0]:.2f}% → {hp[-1]:.2f}%   ({hp[-1]-hp[0]:+.2f}%p)")
        if res:
            slope = res["beta"][1]
            # hp가 이미 퍼센트 단위(38.64)이므로 기울기도 %p/일이다. 100을 곱하면 안 된다.
            print(f"    회귀 기울기 {slope:+.4f}%p/일"
                  f"  (거래일 20일당 {slope*20:+.2f}%p,"
                  f" 1년이면 {slope*TRADING_DAYS:+.1f}%p)"
                  + stars(res["t"][1]))
            print(f"    R² {res['r2']:.3f}"
                  + ("  → 추세가 뚜렷하다. 노이즈가 아니다" if res["r2"] > 0.5
                     else "  → 방향은 있으나 흔들림이 크다"))

    # ── 수급 → 당일 수익률 (동시성) ──
    if all(x is not None for x in fo):
        sh = blob.get("shares_out")
        f1, i1, d1 = fo[1:], ins[1:], ind[1:]
        res = ols(ret, [f1, i1], ["외국인", "기관"])
        print(f"\n▸ 수급 → 당일 수익률  (동시성 — 누가 가격을 움직였나)")
        if res:
            print(f"    R² {res['r2']:.3f}")
            for k, nm in enumerate(res["names"]):
                if nm == "상수":
                    continue
                b, t = res["beta"][k], res["t"][k]
                print(f"    {nm:<8} 10만주당 {b*100000*100:+.3f}%p"
                      + (f"   t={t:+.2f}" if t else "") + stars(t))
        print(f"    개인 순매수 vs 수익률 상관 {corr(d1, ret):+.3f}"
              "   (음수면 개인이 반대편에 선다는 뜻)")

        # ── 수급 → 익일 수익률 (예측력) ──
        print(f"\n▸ 수급 → 익일 수익률  (예측력 — 이게 진짜 질문이다)")
        fx, ix, nxt = fo[1:-1], ins[1:-1], ret[1:]
        res2 = ols(nxt, [fx, ix], ["외국인", "기관"])
        if res2:
            print(f"    R² {res2['r2']:.4f}")
            for k, nm in enumerate(res2["names"]):
                if nm == "상수":
                    continue
                b, t = res2["beta"][k], res2["t"][k]
                print(f"    {nm:<8} 10만주당 {b*100000*100:+.3f}%p"
                      + (f"   t={t:+.2f}" if t else "") + stars(t))
            if res2["r2"] < 0.05:
                print("    → 오늘의 수급으로 내일을 못 맞춘다."
                      " '외국인이 샀으니 오를 것'은 근거가 아니다")

    # ── 자기상관 ──
    print(f"\n▸ 수익률 자기상관")
    for lag in (1, 2, 5):
        a, b = ret[:-lag], ret[lag:]
        c = corr(a, b)
        if c is None:
            continue
        tag = ("모멘텀" if c > 0.15 else "평균회귀" if c < -0.15 else "무작위에 가깝다")
        print(f"    lag {lag}일  {c:+.3f}   {tag}")

    # ── 거래량 급증일 ──
    if all(v is not None for v in vol):
        v1 = vol[1:]
        mv = mean(v1)
        big = [(r, v) for r, v in zip(ret, v1) if v > mv * 1.8]
        norm = [r for r, v in zip(ret, v1) if v <= mv * 1.8]
        if big:
            br = [r for r, _ in big]
            print(f"\n▸ 거래량 급증일 (평균의 1.8배 초과, {len(big)}일)")
            print(f"    평균 수익률 {mean(br)*100:+.2f}%   "
                  f"변동성 {stdev(br)*100 if len(br)>1 else 0:.2f}%")
            print(f"    보통날 평균 {mean(norm)*100:+.2f}%   "
                  f"변동성 {stdev(norm)*100:.2f}%")
            print("    → 대량 거래일은 방향이 아니라 변동성을 키운다"
                  if stdev(br) and stdev(br) > stdev(norm) else "")

    print("\n" + "=" * 60)
    print("  과거 관계다. 유의하지 않은 계수를 근거로 쓰지 않는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
