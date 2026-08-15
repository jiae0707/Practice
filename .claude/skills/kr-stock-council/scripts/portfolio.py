#!/usr/bin/env python3
"""보유 종목의 평가·손익·비중·세후 실현금액을 계산한다.

사용법:
    python3 portfolio.py                                  # 매입 기준 비중만
    python3 portfolio.py --prices '{"현대차":250000}'      # 현재가를 넣어 평가·손익
    python3 portfolio.py --prices prices.json             # 파일로도 가능
    python3 portfolio.py --prices ... --sell '{"현대차":500}'   # 매도 시 세후 금액

손으로 계산하지 않는다 — 틀리면 판단 전체가 무너진다.
세율이 바뀌면 아래 상수를 고친다 (references/tax-and-fees.md 참고).
"""

import argparse
import json
import os
import sys

# --- 2026년 기준 (매도 시, 매도금액 대비) ---
TAX = {"KOSPI": 0.0020, "KOSDAQ": 0.0020}   # 거래세+농특세
BROKER_FEE = 0.00015                         # 증권사 위탁수수료 (계좌마다 다름)
DIVIDEND_TAX = 0.154                         # 배당소득세
FINANCIAL_INCOME_THRESHOLD = 20_000_000      # 금융소득종합과세 기준
MAJOR_SHAREHOLDER_KRW = 5_000_000_000        # 대주주 판정 (종목당 평가액)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORTFOLIO = os.path.join(HERE, "..", "data", "portfolio.json")


def won(n):
    return f"{round(n):,}"


def load_json_arg(value):
    """JSON 문자열이거나 파일 경로."""
    if value is None:
        return {}
    if os.path.exists(value):
        with open(value, encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portfolio", default=DEFAULT_PORTFOLIO)
    ap.add_argument("--prices", help='현재가. {"현대차":250000} 또는 파일 경로')
    ap.add_argument("--sell", help='매도 계획. {"현대차":500} = 500주 매도')
    ap.add_argument("--dividends", help='연간 배당 예상. {"현대차":11400} = 주당 배당금')
    args = ap.parse_args()

    with open(args.portfolio, encoding="utf-8") as fh:
        pf = json.load(fh)
    holdings = pf["holdings"]
    prices = load_json_arg(args.prices)
    sells = load_json_arg(args.sell)
    divs = load_json_arg(args.dividends)

    missing = [h["name"] for h in holdings if h["name"] not in prices]
    if prices and missing:
        print(f"⚠️  현재가 없음: {', '.join(missing)} — 이 종목은 매입 기준으로만 표시\n")

    rows = []
    for h in holdings:
        cost = h["avg_price"] * h["qty"]
        px = prices.get(h["name"])
        value = px * h["qty"] if px else None
        pnl = value - cost if value is not None else None
        rows.append({**h, "cost": cost, "price": px, "value": value, "pnl": pnl})

    total_cost = sum(r["cost"] for r in rows)
    valued = [r for r in rows if r["value"] is not None]
    total_value = sum(r["value"] for r in valued) if valued else None
    base = total_value if (total_value and len(valued) == len(rows)) else total_cost
    base_label = "평가금액" if base == total_value else "매입금액"

    # ---------- 표 ----------
    head = f"{'종목':<12}{'평단':>10}{'현재가':>10}{'수량':>7}{'매입금액':>15}{'평가금액':>15}{'손익':>15}{'수익률':>9}{'비중':>8}"
    print(head)
    print("-" * len(head))
    for r in sorted(rows, key=lambda x: -(x["value"] or x["cost"])):
        w = (r["value"] or r["cost"]) / base * 100
        px = won(r["price"]) if r["price"] else "-"
        val = won(r["value"]) if r["value"] is not None else "-"
        pnl = won(r["pnl"]) if r["pnl"] is not None else "-"
        rate = f"{r['pnl']/r['cost']*100:+.1f}%" if r["pnl"] is not None else "-"
        print(f"{r['name']:<12}{won(r['avg_price']):>10}{px:>10}{r['qty']:>7,}"
              f"{won(r['cost']):>15}{val:>15}{pnl:>15}{rate:>9}{w:>7.1f}%")

    print("-" * len(head))
    print(f"총 매입금액 {won(total_cost)}원")
    if total_value is not None and len(valued) == len(rows):
        pnl = total_value - total_cost
        print(f"총 평가금액 {won(total_value)}원   손익 {won(pnl)}원 ({pnl/total_cost*100:+.1f}%)")

    # ---------- 집중도 ----------
    print(f"\n=== 집중도 ({base_label} 기준) ===")
    ranked = sorted(rows, key=lambda x: -(x["value"] or x["cost"]))
    top1 = (ranked[0]["value"] or ranked[0]["cost"]) / base * 100
    top3 = sum((r["value"] or r["cost"]) for r in ranked[:3]) / base * 100
    print(f"  1위 {ranked[0]['name']} {top1:.1f}%   ·   상위 3종목 {top3:.1f}%")
    if top1 >= 30:
        print(f"  ⚠️  단일 종목이 {top1:.0f}% — 이 종목의 사건이 포트 전체를 좌우한다")

    # 같은 회사 묶음 (보통주+우선주)
    groups = {}
    for r in rows:
        key = r["name"].replace("우", "") if r["name"].endswith("우") else r["name"]
        groups.setdefault(key, []).append(r)
    for key, items in groups.items():
        if len(items) > 1:
            s = sum((i["value"] or i["cost"]) for i in items) / base * 100
            names = "+".join(i["name"] for i in items)
            print(f"  ⚠️  {names} 합계 {s:.1f}% — 같은 기업이므로 하나의 포지션으로 봐야 한다")

    tiny = [r for r in rows if (r["value"] or r["cost"]) / base * 100 < 1.0]
    if tiny:
        print(f"  · 1% 미만 종목: {', '.join(r['name'] for r in tiny)} — 분석 비용 대비 실익이 적다")

    # 대주주 판정
    for r in rows:
        v = r["value"] or r["cost"]
        if v >= MAJOR_SHAREHOLDER_KRW * 0.8:
            print(f"  ⚠️  {r['name']} {won(v)}원 — 대주주 기준(50억) 근접. 연말 보유액 확인 필요")

    # ---------- 매도 시뮬레이션 ----------
    if sells:
        print("\n=== 매도 시 세후 ===")
        total_net = 0
        for name, qty in sells.items():
            r = next((x for x in rows if x["name"] == name), None)
            if not r:
                print(f"  ⚠️  보유하지 않은 종목: {name}")
                continue
            if not r["price"]:
                print(f"  ⚠️  {name}: 현재가가 없어 계산 불가")
                continue
            if qty > r["qty"]:
                print(f"  ⚠️  {name}: 보유 {r['qty']}주보다 많이 매도 ({qty}주)")
                continue
            gross = r["price"] * qty
            tax = gross * TAX.get(r["market"], 0.0020)
            fee = gross * BROKER_FEE
            net = gross - tax - fee
            realized = net - r["avg_price"] * qty
            total_net += net
            print(f"  {name} {qty:,}주 @ {won(r['price'])}")
            print(f"     매도금액 {won(gross)}  −거래세 {won(tax)}  −수수료 {won(fee)}")
            print(f"     → 세후 실현 {won(net)}원   실현손익 {won(realized)}원 "
                  f"({realized/(r['avg_price']*qty)*100:+.1f}%)")
        if len(sells) > 1:
            print(f"  합계 세후 회수 {won(total_net)}원")

    # ---------- 배당 ----------
    if divs:
        print("\n=== 배당 (연간 예상) ===")
        gross_total = 0
        for name, per_share in divs.items():
            r = next((x for x in rows if x["name"] == name), None)
            if not r:
                continue
            g = per_share * r["qty"]
            gross_total += g
            print(f"  {name}: 주당 {won(per_share)} × {r['qty']:,}주 = {won(g)}원")
        net_total = gross_total * (1 - DIVIDEND_TAX)
        print(f"  세전 합계 {won(gross_total)}원 → 세후 {won(net_total)}원 (15.4% 원천징수)")
        if gross_total > FINANCIAL_INCOME_THRESHOLD:
            print(f"  ⚠️  금융소득종합과세 기준({won(FINANCIAL_INCOME_THRESHOLD)}원) 초과 — "
                  "다른 소득과 합산 누진과세 대상. 세무 확인 필요")
        elif gross_total > FINANCIAL_INCOME_THRESHOLD * 0.8:
            print(f"  · 종합과세 기준의 {gross_total/FINANCIAL_INCOME_THRESHOLD*100:.0f}% 수준 — 연말에 다시 확인")

    # ---------- 확인 필요 플래그 ----------
    flagged = [r for r in rows if r.get("flag")]
    if flagged:
        print("\n=== 확인 필요 ===")
        for r in flagged:
            print(f"  · {r['name']}: {r['flag']}")

    if not prices:
        print("\n※ 현재가를 넣지 않아 매입 기준으로만 계산했다. "
              "판단하려면 --prices로 현재가를 넣어야 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
