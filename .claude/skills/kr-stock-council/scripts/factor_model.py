#!/usr/bin/env python3
"""거시 팩터로 종목 수익률을 설명하고, 설명 안 되는 날을 골라낸다. 의존성 없음.

이 스크립트의 핵심은 베타가 아니라 **잔차**다.
팩터로 설명되는 부분은 시장이 한 일이고, 남는 부분(이상수익률)이
그 기업에 실제로 일어난 일이다. **뉴스는 거기서 찾아야 한다.**

    python3 factor_model.py --name 현대차
    python3 factor_model.py --name 현대차 --factors VIX USDKRW WTI
    python3 factor_model.py --all --top 8

시차 처리:
  미국 정규장은 한국시간 05:00(서머타임)에 끝난다. 즉 **미국 t일 종가는
  한국 t+1일 개장 전에 확정**된다. 그래서 미국계 팩터(VIX, WTI)는
  **1거래일 시차**를 두고 한국 수익률에 붙인다. 원/달러는 국내에서
  같이 거래되므로 동일자로 붙인다.

  이걸 안 맞추면 "오늘 한국 주가가 오늘 밤 미국 지수를 예측했다"는
  말이 되고, 계수가 엉뚱하게 나온다.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)
from correlation import ols, mean, stdev  # noqa: E402

# 팩터별 시차(거래일). 미국 지표는 1일 뒤 한국장에 반영된다.
LAG = {"VIX": 1, "WTI": 1, "SOX": 1, "NASDAQ": 1, "SP500": 1,
       "USDKRW": 0, "KOSPI": 0, "KOSPI_FUT": 1}
# 수준 그대로 볼 팩터(변화율이 아니라 차분). VIX는 이미 변동성 지수다.
DIFF = {"VIX"}


def news_series(name, dates, blind_only=True):
    """뉴스 점수(sentiment x surprise)를 팩터 열로 만든다.

    blind_only면 주가를 보고 매긴 점수(blind:false)를 제외한다.
    그걸 섞으면 "악재인 날 빠졌다"는 동어반복이 회귀로 나온다.
    """
    path = os.path.join(DATA, "news.json")
    if not os.path.exists(path):
        return None, 0
    with open(path, encoding="utf-8") as fh:
        nw = json.load(fh)
    col, scored = [], 0
    for d in dates:
        blk = nw.get(d) or {}
        v = blk.get(name) if isinstance(blk, dict) else None
        if not v or (blind_only and not v.get("blind", False)):
            col.append(0.0)   # 사건 없음 = 0. 확인 안 한 날과는 구분이 안 되는 한계
        else:
            col.append(float(v.get("sentiment", 0)) * float(v.get("surprise", 0)))
            scored += 1
    return col, scored


def load():
    with open(os.path.join(DATA, "history.json"), encoding="utf-8") as fh:
        hist = json.load(fh)
    with open(os.path.join(DATA, "factors.json"), encoding="utf-8") as fh:
        fac = json.load(fh)["rows"]
    hist = {k: v for k, v in hist.items() if not k.startswith("_")}
    return hist, fac


def series(hist, name):
    ds = sorted(d for d in hist if name in hist[d])
    return ds, [hist[d][name] for d in ds]


def factor_change(fac, key, dates):
    """dates 각 날짜에 대응하는 팩터 변화. 시차와 차분/수익률 구분을 적용."""
    fds = sorted(d for d in fac if key in fac[d])
    idx = {d: i for i, d in enumerate(fds)}
    lag = LAG.get(key, 1)
    out = []
    for d in dates:
        # d보다 앞선(또는 같은) 팩터 날짜 중 가장 최근 것을 찾고 lag만큼 뒤로
        prior = [x for x in fds if x <= d]
        if len(prior) < lag + 2:
            out.append(None)
            continue
        j = idx[prior[-1]] - lag
        if j < 1:
            out.append(None)
            continue
        a, b = fac[fds[j - 1]][key], fac[fds[j]][key]
        if key in DIFF:
            out.append(b - a)
        else:
            out.append(math.log(b / a) if a > 0 and b > 0 else None)
    return out


def analyze(hist, fac, name, keys, top):
    ds, px = series(hist, name)
    if len(ds) < 30:
        print(f"{name}: 거래일 {len(ds)}개 — 부족")
        return
    rdates = ds[1:]
    ret = [math.log(px[i] / px[i - 1]) for i in range(1, len(px))]

    cols, used = [], []
    if "NEWS" in keys:
        col, scored = news_series(name, rdates)
        if col is None or scored < 60:
            print(f"\n  ⚠️  뉴스 팩터: 편향 없이 채점된 건이 {scored if col else 0}건뿐이다.")
            print("     60건 미만이면 계수를 보지 않는다. 매일 브리핑에서 쌓인다.")
        else:
            cols.append(col)
            used.append("NEWS")
        keys = [k for k in keys if k != "NEWS"]
    for k in keys:
        c = factor_change(fac, k, rdates)
        if sum(1 for x in c if x is not None) >= 30:
            cols.append(c)
            used.append(k)
    if not used:
        print(f"{name}: 쓸 수 있는 팩터가 없다")
        return

    keep = [i for i in range(len(ret)) if all(c[i] is not None for c in cols)]
    y = [ret[i] for i in keep]
    X = [[c[i] for i in keep] for c in cols]
    dts = [rdates[i] for i in keep]

    res = ols(y, X, used)
    print(f"\n{'='*64}\n  {name}   관측치 {len(y)}일   팩터 {' + '.join(used)}\n{'='*64}")
    if not res:
        print("  회귀 실패")
        return

    print(f"  R² {res['r2']:.3f}"
          f"   → 거시로 설명되는 부분 {res['r2']*100:.1f}%,"
          f" 기업 고유 {100-res['r2']*100:.1f}%")
    for i, nm in enumerate(res["names"]):
        t = res["t"][i]
        sig = ("  *** 유의" if t and abs(t) > 2.6 else
               "  ** 유의" if t and abs(t) > 2.0 else "  · 유의하지 않음")
        unit = "1p 변화당" if nm in DIFF else ("1% 변화당" if nm != "상수" else "")
        print(f"    {nm:<9}{res['beta'][i]:+.4f} {unit:<10}"
              + (f"t={t:+.2f}" if t else "") + sig)

    # ── 이상수익률: 뉴스는 여기서 찾는다 ──
    resid = res["resid"]
    s = stdev(resid)
    print(f"\n  잔차 표준편차 {s*100:.2f}%/일  ← 거시로 설명 안 되는 고유 변동")
    print(f"\n  ▸ 이상수익률 상위 {top}일 — **뉴스를 찾아야 할 날짜**")
    print(f"    {'날짜':<12}{'실제':>9}{'거시설명':>10}{'이상수익률':>11}{'σ':>7}")
    ranked = sorted(range(len(resid)), key=lambda i: -abs(resid[i]))[:top]
    for i in sorted(ranked, key=lambda i: dts[i], reverse=True):
        explained = y[i] - resid[i]
        print(f"    {dts[i]:<12}{y[i]*100:>+8.2f}%{explained*100:>+9.2f}%"
              f"{resid[i]*100:>+10.2f}%{resid[i]/s:>+7.1f}")
    print("    → σ 3 이상이면 거시로 설명 불가능한 사건이 있었다는 뜻이다.")
    print("      그 날짜로 뉴스를 검색해야 한다. 반대로 σ 1 미만인 날의")
    print("      뉴스는 주가를 설명하지 못한다 — 사후 서사일 뿐이다.")
    return dts, resid, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--factors", nargs="+", default=["VIX", "USDKRW", "WTI"])
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()

    hist, fac = load()
    names = sorted({n for d in hist for n in hist[d]})
    targets = names if args.all else ([args.name] if args.name else names)

    avail = sorted({k for d in fac for k in fac[d]})
    print(f"사용 가능한 팩터: {', '.join(avail)}")
    # NEWS는 factors.json이 아니라 news.json에서 오므로 여기서 빼고 검사한다
    miss = [k for k in args.factors if k not in avail and k != "NEWS"]
    if miss:
        print(f"⚠️  없는 팩터: {', '.join(miss)} — 이 팩터는 빼고 돌린다")

    for n in targets:
        if n in hist[max(hist)]:
            analyze(hist, fac, n, args.factors, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
