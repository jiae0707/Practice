#!/usr/bin/env python3
"""보유 종목의 상관관계·리스크 기여도·회귀를 계산한다. 의존성 없음(표준 라이브러리만).

"9종목 가졌으니 분산됐다"는 착각을 깨는 게 이 도구의 목적이다.
종목이 아홉이어도 전부 같이 움직이면 실제로는 한 종목이다.

    # data/prices-*.json을 전부 모아 시계열을 만든다
    python3 correlation.py

    # 특정 쌍의 회귀 (현대차우가 현대차를 얼마나 따라가는가)
    python3 correlation.py --pair 현대차우 현대차

    # 다중회귀 — 종목을 여러 팩터에 회귀
    python3 correlation.py --regress 현대차 --factors KOSPI USDKRW

계산하는 것:
  · 일간 수익률 상관계수 행렬
  · 유효 종목 수 — 진짜 몇 종목짜리 포트폴리오인가
  · 리스크 기여도 — 비중 77%가 리스크의 몇 %인가
  · 포트 변동성·VaR — 원화로
  · 페어 회귀 — 베타·R²·잔차 z점수 (괴리가 통계적 이상치인가)

관측치가 적으면 숫자를 내되 **신뢰할 수 없다고 표시한다.**
30개 미만이면 참고용, 60개 이상이어야 판단에 쓴다.
"""

import argparse
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
PORTFOLIO = os.path.join(DATA, "portfolio.json")

MIN_USABLE = 60      # 판단에 쓸 수 있는 최소 관측치
MIN_INDICATIVE = 30  # 이 아래는 참고도 어렵다
TRADING_DAYS = 250


# ────────────────────────────── 통계 기본 ──────────────────────────────

def mean(xs):
    return sum(xs) / len(xs)


def stdev(xs, sample=True):
    if len(xs) < 2:
        return None
    m = mean(xs)
    d = sum((x - m) ** 2 for x in xs)
    return math.sqrt(d / (len(xs) - (1 if sample else 0)))


def cov(xs, ys, sample=True):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    s = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return s / (len(xs) - (1 if sample else 0))


def corr(xs, ys):
    c = cov(xs, ys)
    sx, sy = stdev(xs), stdev(ys)
    if c is None or not sx or not sy:
        return None
    return c / (sx * sy)


def solve(A, b):
    """가우스 소거법. 작은 정규방정식용."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[piv][i]) < 1e-12:
            return None
        M[i], M[piv] = M[piv], M[i]
        for r in range(i + 1, n):
            f = M[r][i] / M[i][i]
            for c in range(i, n + 1):
                M[r][c] -= f * M[i][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][c] * x[c] for c in range(i + 1, n))) / M[i][i]
    return x


def ols(y, Xcols, names):
    """상수항 포함 최소자승. 반환: 계수, R², 잔차, 표준오차, t값."""
    n = len(y)
    X = [[1.0] + [col[i] for col in Xcols] for i in range(n)]
    k = len(X[0])
    if n <= k:
        return None
    XtX = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    Xty = [sum(X[r][i] * y[r] for r in range(n)) for i in range(k)]
    beta = solve(XtX, Xty)
    if beta is None:
        return None

    fit = [sum(beta[j] * X[r][j] for j in range(k)) for r in range(n)]
    resid = [y[r] - fit[r] for r in range(n)]
    ybar = mean(y)
    ss_res = sum(e * e for e in resid)
    ss_tot = sum((v - ybar) ** 2 for v in y)
    r2 = None if ss_tot == 0 else 1 - ss_res / ss_tot
    dof = n - k
    sigma2 = ss_res / dof if dof > 0 else None

    # (X'X)^-1 대각만 필요 — 단위벡터를 풀어서 얻는다
    ses = []
    for j in range(k):
        e = [1.0 if i == j else 0.0 for i in range(k)]
        col = solve(XtX, e)
        ses.append(None if (col is None or sigma2 is None) or col[j] < 0
                   else math.sqrt(sigma2 * col[j]))
    tvals = [None if (s in (None, 0)) else beta[i] / s for i, s in enumerate(ses)]

    return {"names": ["상수"] + names, "beta": beta, "r2": r2, "resid": resid,
            "se": ses, "t": tvals, "n": n, "sigma": math.sqrt(sigma2) if sigma2 else None}


# ────────────────────────────── 데이터 적재 ──────────────────────────────

def load_series(pattern=None, extra=None):
    """data/prices-YYYYMMDD.json을 전부 모아 날짜순 시계열로 만든다."""
    files = sorted(glob.glob(pattern or os.path.join(DATA, "prices-*.json")))
    by_date = {}
    for f in files:
        base = os.path.basename(f)
        date = base.replace("prices-", "").replace(".json", "")
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        by_date[date] = {k: v for k, v in d.items() if not k.startswith("_")}

    if extra and os.path.exists(extra):
        with open(extra, encoding="utf-8") as fh:
            hist = json.load(fh)
        for date, row in hist.items():
            if date.startswith("_"):
                continue
            by_date.setdefault(date, {}).update(
                {k: v for k, v in row.items() if not k.startswith("_")})

    dates = sorted(by_date)
    names = sorted({n for d in by_date.values() for n in d})
    return dates, by_date, names


def returns(dates, by_date, name):
    """연속된 두 날짜 모두 값이 있는 구간의 로그수익률."""
    out, ds = [], []
    prev = None
    for d in dates:
        v = by_date[d].get(name)
        if v is None or v <= 0:
            prev = None
            continue
        if prev is not None:
            out.append(math.log(v / prev))
            ds.append(d)
        prev = v
    return ds, out


def aligned(dates, by_date, names):
    """모든 종목에 값이 있는 날짜만 남겨 수익률 행렬을 만든다."""
    common = [d for d in dates if all(by_date[d].get(n) for n in names)]
    series = {}
    for n in names:
        vals = [by_date[d][n] for d in common]
        series[n] = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
    return common[1:], series


# ────────────────────────────── 리포트 ──────────────────────────────

def confidence(n):
    if n >= MIN_USABLE:
        return f"관측치 {n}개 — 판단에 쓸 수 있다"
    if n >= MIN_INDICATIVE:
        return f"관측치 {n}개 — 참고용. {MIN_USABLE}개는 있어야 판단에 쓴다"
    return (f"⚠️  관측치 {n}개뿐 — 이 숫자로 판단하지 마라. "
            f"최소 {MIN_INDICATIVE}, 권장 {MIN_USABLE}개")


def corr_matrix(names, series):
    n_obs = len(series[names[0]])
    # 관측치 2개면 상관계수가 수학적으로 반드시 ±1이 된다. 참이지만 무의미하고,
    # 표로 찍어놓으면 "전부 같이 움직인다"는 결론으로 오독된다. 아예 내지 않는다.
    if n_obs < 3:
        print(f"\n=== 일간 수익률 상관계수 ===\n"
              f"  관측치 {n_obs}개로는 계산하지 않는다. 두 점을 지나는 직선은 항상 완벽해서\n"
              f"  상관계수가 반드시 ±1로 나온다. 참이지만 아무 정보가 없다.")
        return

    w = max(len(n) for n in names) + 1
    print("\n=== 일간 수익률 상관계수 ===")
    if n_obs < MIN_INDICATIVE:
        print(f"  ⚠️  관측치 {n_obs}개. 아래 숫자는 우연일 가능성이 크다 — "
              f"판단에 쓰지 말 것")
    print(" " * w + "".join(f"{n[:5]:>7}" for n in names))
    for a in names:
        row = f"{a:<{w}}"
        for b in names:
            c = 1.0 if a == b else corr(series[a], series[b])
            row += "      —" if c is None else f"{c:>7.2f}"
        print(row)

    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            c = corr(series[a], series[b])
            if c is not None:
                pairs.append((abs(c), c, a, b))
    if pairs:
        pairs.sort(reverse=True)
        print("\n  가장 강하게 같이 움직이는 쌍")
        for _, c, a, b in pairs[:5]:
            tag = ("같은 자산으로 봐야 한다" if c > 0.8 else
                   "분산 효과 거의 없다" if c > 0.6 else
                   "반대로 움직인다" if c < -0.3 else "부분적으로 분산")
            print(f"    {a} ↔ {b}   {c:+.2f}   {tag}")


def risk_report(names, series, weights, total_value):
    """리스크 기여도. 비중과 리스크 비중은 다르다 — 이게 핵심이다."""
    n = len(names)
    C = [[cov(series[a], series[b]) for b in names] for a in names]
    if any(v is None for row in C for v in row):
        print("\n=== 리스크 기여도 ===\n  공분산 계산 불가 (관측치 부족)")
        return
    w = [weights[nm] for nm in names]

    var = sum(w[i] * w[j] * C[i][j] for i in range(n) for j in range(n))
    if var <= 0:
        print("\n=== 리스크 기여도 ===\n  분산이 0 이하 — 계산 불가")
        return
    sd = math.sqrt(var)
    ann = sd * math.sqrt(TRADING_DAYS)

    print("\n=== 리스크 기여도 ===")
    print(f"  포트 일간 변동성 {sd*100:.2f}%   연환산 {ann*100:.1f}%")
    print(f"  1일 VaR(95%)  {1.645*sd*100:.2f}%  =  {1.645*sd*total_value:,.0f}원")
    print(f"  1일 VaR(99%)  {2.326*sd*100:.2f}%  =  {2.326*sd*total_value:,.0f}원")

    print(f"\n  {'종목':<10}{'비중':>9}{'리스크 비중':>13}{'차이':>9}")
    print("  " + "-" * 41)
    rcs = []
    for i, nm in enumerate(names):
        mctr = sum(w[j] * C[i][j] for j in range(n)) / sd
        rc = w[i] * mctr / sd
        rcs.append(rc)
        print(f"  {nm:<10}{w[i]*100:>8.1f}%{rc*100:>12.1f}%{(rc-w[i])*100:>+8.1f}%p")

    # 유효 종목 수
    eff_w = 1 / sum(x * x for x in w)
    eff_r = 1 / sum(x * x for x in rcs) if sum(x * x for x in rcs) > 0 else None
    wavg = sum(w[i] * math.sqrt(C[i][i]) for i in range(n))
    dr = wavg / sd

    print(f"\n  유효 종목 수(비중 기준)   {eff_w:.2f}종목  / 실제 {n}종목")
    if eff_r:
        print(f"  유효 종목 수(리스크 기준) {eff_r:.2f}종목  ← 이게 실질이다")
    print(f"  분산비율(DR)              {dr:.3f}  "
          + ("(1에 가까울수록 분산 효과가 없다)" if dr < 1.15 else ""))
    if eff_r and eff_r < 1.5:
        print(f"  ⚠️  {n}종목을 갖고 있지만 리스크는 사실상 {eff_r:.1f}종목짜리다")


def pair_report(y_name, x_name, dates, by_date, weights=None):
    ds, sy = returns(dates, by_date, y_name)
    dx, sx = returns(dates, by_date, x_name)
    common = sorted(set(ds) & set(dx))
    if len(common) < 3:
        print(f"\n=== {y_name} ~ {x_name} ===\n  겹치는 관측치 {len(common)}개 — 회귀 불가")
        return
    yy = [sy[ds.index(d)] for d in common]
    xx = [sx[dx.index(d)] for d in common]

    res = ols(yy, [xx], [x_name])
    print(f"\n=== 회귀:  {y_name} ~ {x_name} ===")
    print(f"  {confidence(len(common))}")
    if not res:
        print("  회귀 실패")
        return
    b = res["beta"][1]
    print(f"  베타 {b:+.3f}"
          + (f"  (t={res['t'][1]:+.2f})" if res["t"][1] is not None else ""))
    print(f"  R²   {res['r2']:.3f}  → {x_name} 움직임이 {y_name}의 "
          f"{res['r2']*100:.0f}%를 설명한다")
    print(f"  해석: {x_name}가 1% 오르면 {y_name}는 평균 {b:+.2f}% 움직인다")

    # 가격비 괴리의 z점수
    lv = [(by_date[d].get(y_name), by_date[d].get(x_name)) for d in dates]
    ratios = [a / bb for a, bb in lv if a and bb]
    if len(ratios) >= 3:
        m, s = mean(ratios), stdev(ratios)
        cur = ratios[-1]
        print(f"\n  가격비 {y_name}/{x_name}")
        print(f"    현재 {cur*100:.1f}%   평균 {m*100:.1f}%   표준편차 {s*100:.2f}%p")
        if s and s > 0:
            z = (cur - m) / s
            print(f"    z점수 {z:+.2f}   " + (
                "→ 통계적 이상치. 되돌림을 노릴 자리다" if abs(z) > 2 else
                "→ 정상 범위. 괴리를 근거로 매매하지 마라"))
        if len(ratios) < MIN_INDICATIVE:
            print(f"    ⚠️  {len(ratios)}개 관측으로 계산한 평균이다. 아직 평균이라 부를 수 없다")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", help="prices 파일 패턴")
    ap.add_argument("--history", help="추가 시계열 JSON {날짜:{종목:종가}}",
                    default=os.path.join(DATA, "history.json"))
    ap.add_argument("--pair", nargs=2, metavar=("Y", "X"), help="두 종목 회귀")
    ap.add_argument("--regress", help="이 종목을 --factors에 회귀")
    ap.add_argument("--factors", nargs="+", help="설명변수 이름들")
    args = ap.parse_args()

    dates, by_date, names = load_series(args.glob, args.history)
    if len(dates) < 2:
        print(f"날짜가 {len(dates)}개뿐이다. 상관·회귀를 계산할 수 없다.\n")
        print("빠르게 채우는 법: 증권사 앱의 [일별] 탭을 캡처하면 한 장에 20일치가 나온다.")
        print("종목당 3장이면 60거래일이 모이고, 그때부터 이 도구가 의미를 갖는다.")
        print(f"모은 값은 {os.path.join(DATA,'history.json')}에 "
              '{"2026-08-14": {"현대차": 459500, ...}} 형태로 넣는다.')
        return 1

    print(f"기간 {dates[0]} ~ {dates[-1]}   날짜 {len(dates)}개   종목 {len(names)}개")
    print(confidence(len(dates) - 1))

    with open(PORTFOLIO, encoding="utf-8") as fh:
        pf = json.load(fh)
    held = {h["name"]: h["qty"] for h in pf["holdings"]}

    if args.pair:
        pair_report(args.pair[0], args.pair[1], dates, by_date)
        return 0

    if args.regress:
        rd, ry = returns(dates, by_date, args.regress)
        cols, keep = [], []
        for f in (args.factors or []):
            fd, fy = returns(dates, by_date, f)
            common = sorted(set(rd) & set(fd))
            if len(common) >= 3:
                keep.append(f)
                cols.append((fd, fy))
        if not keep:
            print(f"\n{args.regress}: 쓸 수 있는 설명변수가 없다")
            return 1
        common = sorted(set(rd).intersection(*[set(d) for d, _ in cols]))
        y = [ry[rd.index(d)] for d in common]
        X = [[fy[fd.index(d)] for d in common] for fd, fy in cols]
        res = ols(y, X, keep)
        print(f"\n=== 다중회귀:  {args.regress} ~ {' + '.join(keep)} ===")
        print(f"  {confidence(len(common))}")
        if res:
            print(f"  R² {res['r2']:.3f}")
            for i, nm in enumerate(res["names"]):
                t = res["t"][i]
                sig = "" if t is None else ("  ***" if abs(t) > 2.6 else
                                            "  **" if abs(t) > 2.0 else "  (유의하지 않음)")
                print(f"    {nm:<12}{res['beta'][i]:+.4f}"
                      + ("" if t is None else f"   t={t:+.2f}") + sig)
        return 0

    # 기본: 보유 종목 전체
    port = [n for n in names if n in held]
    ds, series = aligned(dates, by_date, port)
    usable = [n for n in port if len(series[n]) >= 2]
    if len(usable) < 2 or len(series[usable[0]]) < 2:
        print("\n공통 관측일이 부족해 상관을 계산할 수 없다.")
        print("증권사 앱 [일별] 탭 캡처로 과거 시세를 채우면 바로 계산된다.")
        return 1

    corr_matrix(usable, series)

    last = dates[-1]
    vals = {n: by_date[last].get(n, 0) * held[n] for n in usable}
    total = sum(vals.values())
    if total > 0:
        risk_report(usable, series, {n: vals[n] / total for n in usable}, total)

    print("\n" + "=" * 60)
    print("  상관은 과거의 관계다. 시장이 무너질 때는 상관이 1로 수렴한다.")
    print("  분산이 가장 필요한 순간에 분산이 사라진다는 뜻이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
