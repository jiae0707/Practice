#!/usr/bin/env python3
"""재무제표로 회계 품질과 부도 위험을 계산한다.

인상이 아니라 숫자로 말하기 위한 도구다. "실적이 좋아 보인다"는 분석이 아니고,
"F-Score 7/9, 발생액 -3.2%로 이익의 질이 좋다"가 분석이다.

    python3 fundamentals.py --financials data/financials.json
    python3 fundamentals.py --financials data/financials.json --only 현대차

계산하는 것:
  · Piotroski F-Score (0~9)  — 펀더멘털이 좋아지고 있는가
  · Altman Z-Score           — 부도 위험. "망하는 회사인가"에 대한 정량 답
  · Beneish M-Score          — 회계 조작 신호
  · Sloan 발생액 비율        — 이익의 질. 현금이 안 따라오는 이익인가
  · ROIC vs 자본비용         — 자본을 벌어들이는 만큼 쓰고 있는가

입력은 data/financials.json. **두 기간(당기 t, 전기 p)**이 있어야 대부분이 계산된다.
없는 항목은 null로 두면 그 지표만 건너뛴다. 지어내지 않는다.
"""

import argparse
import json
import os
import sys

# 법인세 실효세율. 2026년 기준 과표 200억 초과 22% + 지방소득세 2.2%
TAX_RATE = 0.242
# 자본비용(WACC) 기본 가정. 종목별로 financials.json에서 덮어쓸 수 있다
DEFAULT_WACC = 0.09

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FIN = os.path.join(HERE, "..", "data", "financials.json")


def g(d, key):
    """값이 없거나 null이면 None."""
    if d is None:
        return None
    v = d.get(key)
    return None if v is None else float(v)


def div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def pct(x, nd=1):
    return "—" if x is None else f"{x*100:+.{nd}f}%"


def num(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


# ────────────────────────────── Piotroski F-Score ──────────────────────────────

def f_score(t, p):
    """9개 항목. 각 1점. 7점 이상이면 개선 중, 3점 이하면 악화 중."""
    checks, unknown = [], []

    roa_t = div(g(t, "net_income"), g(t, "total_assets"))
    roa_p = div(g(p, "net_income"), g(p, "total_assets"))
    cfo_t = g(t, "cfo")
    ta_t = g(t, "total_assets")

    def add(name, cond, detail):
        if cond is None:
            unknown.append(name)
        else:
            checks.append((name, bool(cond), detail))

    # 수익성 4개
    add("ROA > 0", None if roa_t is None else roa_t > 0, pct(roa_t))
    add("영업현금흐름 > 0", None if cfo_t is None else cfo_t > 0,
        "—" if cfo_t is None else f"{cfo_t:,.0f}")
    add("ROA 개선", None if (roa_t is None or roa_p is None) else roa_t > roa_p,
        f"{pct(roa_p)} → {pct(roa_t)}")
    # 발생액: 영업현금흐름이 순이익보다 커야 이익의 질이 좋다
    add("CFO > 순이익", None if (cfo_t is None or g(t, "net_income") is None)
        else cfo_t > g(t, "net_income"),
        "—" if cfo_t is None else f"{cfo_t:,.0f} vs {g(t,'net_income'):,.0f}")

    # 레버리지·유동성 3개
    lev_t = div(g(t, "long_term_debt"), ta_t)
    lev_p = div(g(p, "long_term_debt"), g(p, "total_assets"))
    add("장기부채비율 하락", None if (lev_t is None or lev_p is None) else lev_t < lev_p,
        f"{pct(lev_p)} → {pct(lev_t)}")

    cr_t = div(g(t, "current_assets"), g(t, "current_liabilities"))
    cr_p = div(g(p, "current_assets"), g(p, "current_liabilities"))
    add("유동비율 개선", None if (cr_t is None or cr_p is None) else cr_t > cr_p,
        f"{num(cr_p)} → {num(cr_t)}")

    sh_t, sh_p = g(t, "shares_out"), g(p, "shares_out")
    add("신주발행 없음", None if (sh_t is None or sh_p is None) else sh_t <= sh_p * 1.001,
        "—" if sh_t is None else f"{sh_p:,.0f} → {sh_t:,.0f}")

    # 운영효율 2개
    gm_t = div(g(t, "gross_profit"), g(t, "revenue"))
    gm_p = div(g(p, "gross_profit"), g(p, "revenue"))
    add("매출총이익률 개선", None if (gm_t is None or gm_p is None) else gm_t > gm_p,
        f"{pct(gm_p)} → {pct(gm_t)}")

    at_t = div(g(t, "revenue"), ta_t)
    at_p = div(g(p, "revenue"), g(p, "total_assets"))
    add("자산회전율 개선", None if (at_t is None or at_p is None) else at_t > at_p,
        f"{num(at_p)} → {num(at_t)}")

    score = sum(1 for _, ok, _ in checks if ok)
    return score, len(checks), checks, unknown


# ────────────────────────────── Altman Z-Score ──────────────────────────────

def altman_z(t, market_cap, kind="manufacturing"):
    """제조업은 원본 Z, 그 외는 Z''(비제조·신흥시장 수정판)."""
    ta = g(t, "total_assets")
    tl = g(t, "total_liabilities")
    ca, cl = g(t, "current_assets"), g(t, "current_liabilities")
    re = g(t, "retained_earnings")
    ebit = g(t, "operating_income")
    rev = g(t, "revenue")
    if ta in (None, 0):
        return None, None, None

    wc = None if (ca is None or cl is None) else ca - cl
    x1, x2, x3 = div(wc, ta), div(re, ta), div(ebit, ta)

    if kind == "manufacturing":
        x4 = div(market_cap, tl)
        x5 = div(rev, ta)
        if None in (x1, x2, x3, x4, x5):
            return None, None, None
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        safe, grey = 2.99, 1.81
    else:
        x4 = div(g(t, "total_equity"), tl)
        if None in (x1, x2, x3, x4):
            return None, None, None
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        safe, grey = 2.60, 1.10

    zone = "안전" if z > safe else ("회색" if z > grey else "위험")
    return z, zone, (safe, grey)


# ────────────────────────────── Beneish M-Score ──────────────────────────────

def beneish_m(t, p):
    """8변수. M > -1.78이면 이익 조작 신호. 유죄 판정이 아니라 '들여다볼 이유'다."""
    def r(key_a, key_b, d):
        return div(g(d, key_a), g(d, key_b))

    dsri = div(r("receivables", "revenue", t), r("receivables", "revenue", p))

    gm_t, gm_p = r("gross_profit", "revenue", t), r("gross_profit", "revenue", p)
    gmi = div(gm_p, gm_t)

    def aq(d):
        ta = g(d, "total_assets")
        ca, ppe = g(d, "current_assets"), g(d, "ppe")
        if None in (ta, ca, ppe) or ta == 0:
            return None
        return 1 - (ca + ppe) / ta
    aqi = div(aq(t), aq(p))

    sgi = div(g(t, "revenue"), g(p, "revenue"))

    def dep_rate(d):
        dep, ppe = g(d, "depreciation"), g(d, "ppe")
        if None in (dep, ppe) or (dep + ppe) == 0:
            return None
        return dep / (dep + ppe)
    depi = div(dep_rate(p), dep_rate(t))

    sgai = div(r("sga", "revenue", t), r("sga", "revenue", p))

    ni, cfo, ta = g(t, "net_income"), g(t, "cfo"), g(t, "total_assets")
    tata = None if None in (ni, cfo, ta) or ta == 0 else (ni - cfo) / ta

    def lev(d):
        cl, ltd, ta_ = g(d, "current_liabilities"), g(d, "long_term_debt"), g(d, "total_assets")
        if None in (cl, ltd, ta_) or ta_ == 0:
            return None
        return (cl + ltd) / ta_
    lvgi = div(lev(t), lev(p))

    parts = {"DSRI": dsri, "GMI": gmi, "AQI": aqi, "SGI": sgi,
             "DEPI": depi, "SGAI": sgai, "TATA": tata, "LVGI": lvgi}
    if any(v is None for v in parts.values()):
        return None, parts

    m = (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
         + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
    return m, parts


# ────────────────────────────── 이익의 질 · ROIC ──────────────────────────────

def accruals(t, p):
    """Sloan 발생액. (순이익 − 영업현금흐름) / 평균총자산.
    양수가 크면 이익이 현금으로 안 들어오고 있다는 뜻이다."""
    ni, cfo = g(t, "net_income"), g(t, "cfo")
    ta_t, ta_p = g(t, "total_assets"), g(p, "total_assets")
    if None in (ni, cfo, ta_t):
        return None
    avg = ta_t if ta_p is None else (ta_t + ta_p) / 2
    return div(ni - cfo, avg)


def roic(t, wacc):
    """NOPAT / 투하자본. 자본비용을 못 넘으면 성장할수록 가치가 준다."""
    op = g(t, "operating_income")
    ta, cl = g(t, "total_assets"), g(t, "current_liabilities")
    if None in (op, ta, cl):
        return None, None
    invested = ta - cl
    if invested <= 0:
        return None, None
    r = op * (1 - TAX_RATE) / invested
    return r, r - wacc


# ────────────────────────────── 출력 ──────────────────────────────

def analyze(name, blk):
    t, p = blk.get("current"), blk.get("prior")
    mc = blk.get("market_cap")
    kind = blk.get("kind", "manufacturing")
    wacc = blk.get("wacc", DEFAULT_WACC)

    print(f"\n{'='*66}\n  {name}   ({blk.get('period','기간 미표기')})\n{'='*66}")
    if not t:
        print("  당기 재무 데이터 없음 — 계산 불가")
        return

    # F-Score
    score, total, checks, unknown = f_score(t, p or {})
    # 확인된 항목이 절반도 안 되면 점수 자체가 의미 없다. 낮은 점수를
    # 악화 신호로 읽으면 데이터가 없는 걸 나쁜 것으로 오해한다.
    if total < 5:
        verdict = f"판정 보류 — {9 - total}개 항목의 데이터가 없다"
    else:
        verdict = ("펀더멘털 개선 중" if score >= 7 else
                   "악화 신호" if score <= 3 else "중립")
    print(f"\n▸ Piotroski F-Score  {score} / {total}   → {verdict}")
    for nm, ok, detail in checks:
        print(f"    {'O' if ok else 'X'}  {nm:<18} {detail}")
    if unknown:
        print(f"    ?  데이터 없어 못 본 항목: {', '.join(unknown)}")

    # Altman Z
    z, zone, cut = altman_z(t, mc, kind)
    if z is None:
        print("\n▸ Altman Z-Score     데이터 부족")
    else:
        print(f"\n▸ Altman Z-Score     {z:.2f}   → {zone}"
              f"   (안전>{cut[0]}, 위험<{cut[1]}, {kind})")
        if zone == "위험":
            print("    !! 부도 위험 구간. '망하는 회사가 아니면 안 판다'는 원칙의 예외 후보")

    # Beneish M
    m, parts = beneish_m(t, p or {})
    if m is None:
        miss = [k for k, v in parts.items() if v is None]
        print(f"\n▸ Beneish M-Score    데이터 부족 ({', '.join(miss)})")
    else:
        flag = "조작 신호" if m > -1.78 else "정상"
        print(f"\n▸ Beneish M-Score    {m:.2f}   → {flag}   (기준 -1.78)")
        print("    " + "  ".join(f"{k} {v:.2f}" for k, v in parts.items()))
        if m > -1.78:
            print("    !! 유죄 판정이 아니다. 재무제표를 직접 들여다볼 이유가 생긴 것이다")

    # 발생액
    a = accruals(t, p or {})
    if a is None:
        print("\n▸ 발생액 비율        데이터 부족")
    else:
        q = "이익의 질 나쁨" if a > 0.10 else ("좋음" if a < 0 else "보통")
        print(f"\n▸ 발생액 비율        {pct(a)}   → {q}")
        if a > 0.10:
            print("    !! 이익이 현금으로 안 들어오고 있다. 매출채권·재고를 확인할 것")

    # ROIC
    r, spread = roic(t, wacc)
    if r is None:
        print("\n▸ ROIC               데이터 부족")
    else:
        print(f"\n▸ ROIC               {pct(r)}   (자본비용 {pct(wacc)} 가정)")
        print(f"    스프레드 {pct(spread)} — "
              + ("자본비용 이상을 벌고 있다" if spread > 0
                 else "!! 자본비용을 못 넘는다. 성장할수록 가치가 준다"))

    # 밸류에이션
    if mc:
        eq, ni = g(t, "total_equity"), g(t, "net_income")
        pbr, per = div(mc, eq), div(mc, ni)
        print(f"\n▸ 밸류에이션         PBR {num(pbr)}   PER {num(per)}"
              f"   (시총 {mc:,.0f})")
        if pbr is not None and pbr < 0.5:
            print("    · PBR 0.5 미만 — 자산가치 대비 저평가이거나 구조적 디레이팅이다. 둘을 구분할 것")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--financials", default=DEFAULT_FIN)
    ap.add_argument("--only", help="특정 종목만")
    args = ap.parse_args()

    if not os.path.exists(args.financials):
        print(f"재무 데이터 파일이 없다: {args.financials}")
        print("data/financials.json을 만들고 증권사 앱의 '기업정보 → 재무' 값을 넣는다.")
        return 1

    with open(args.financials, encoding="utf-8") as fh:
        data = json.load(fh)

    stocks = {k: v for k, v in data.items() if not k.startswith("_")}
    if args.only:
        stocks = {k: v for k, v in stocks.items() if k == args.only}
        if not stocks:
            print(f"'{args.only}' 없음. 있는 종목: {', '.join(data)}")
            return 1

    for name, blk in stocks.items():
        analyze(name, blk)

    print(f"\n{'='*66}")
    print("  숫자는 판단 재료다. F-Score가 8이어도 주가는 빠질 수 있고")
    print("  M-Score가 높다고 조작이 확정된 것도 아니다. 들여다볼 곳을 알려줄 뿐이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
