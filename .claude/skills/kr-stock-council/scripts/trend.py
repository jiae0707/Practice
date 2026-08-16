#!/usr/bin/env python3
"""가격과 거래량을 함께 읽어 추세의 질을 판정한다. 의존성 없음.

가격만 보면 "빠졌다"까지밖에 모른다. **거래량을 붙여야 그 하락이
투매인지 소진인지**가 갈린다.

    python3 trend.py --file data/daily-kepco.json --name 한국전력
    python3 trend.py --compare data/daily-kepco.json:한국전력 data/daily-naver.json:네이버

보는 것:
  · 상승일 vs 하락일 거래량 — 어느 쪽에 힘이 실렸나
  · OBV 추세 — 누적 매수·매도 압력의 방향
  · 거래량 추세 — 최근 20일이 이전보다 늘었나 줄었나
  · 거래대금 가중 평균가 — 실제 매물이 쌓인 가격대
  · 신고가·신저가 빈도 — 추세가 살아 있나

가장 중요한 건 **주가와 OBV가 어긋나는 자리**다. 주가는 오르는데 OBV가
내려가면 오르는 동안 물량이 넘어가고 있다는 뜻이고, 그 상승은 힘이 없다.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from correlation import mean, stdev, corr, ols  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    rows = blob.get("rows", blob)
    ds = sorted(k for k in rows if not k.startswith("_"))
    c = [rows[d]["close"] for d in ds]
    v = [rows[d]["volume"] for d in ds]
    n = len(ds)
    ret = [math.log(c[i] / c[i - 1]) for i in range(1, n)]
    obv = [0.0]
    for i, r in enumerate(ret):
        obv.append(obv[-1] + (v[i + 1] if r > 0 else -v[i + 1] if r < 0 else 0))
    return ds, c, v, n, ret, obv


def compare(specs):
    """종목별 한 줄 요약. 주가 방향과 OBV 방향이 어긋나는 종목을 찾는 게 목적이다."""
    print(f"\n{'='*78}\n  가격 × 거래량 — 종목 비교\n{'='*78}")
    print(f"  {'종목':<10}{'20일 주가':>10}{'20일 거래량':>12}"
          f"{'최근 OBV t':>12}{'VWAP 대비':>11}   판정")
    print(f"  {'-'*74}")
    for spec in specs:
        path, _, name = spec.partition(":")
        ds, c, v, n, ret, obv = load(path)
        seg = max(20, n // 4)
        t_recent = ols(obv[-seg:], [list(range(seg))], ["t"])["t"][1]
        r20 = math.log(c[-1] / c[-21]) * 100
        dv = mean(v[-20:]) / mean(v[:-20]) * 100 - 100
        vwap = sum(c[i] * v[i] for i in range(n)) / sum(v)
        gap = c[-1] / vwap * 100 - 100
        if r20 > 0 and t_recent < -2:
            verdict = "**괴리** 주가↑ 물량↓ — 오르는 동안 넘기고 있다"
        elif r20 < 0 and t_recent > 2:
            verdict = "**괴리** 주가↓ 물량↑ — 빠지는 동안 받고 있다"
        elif r20 < 0 and dv < 0:
            verdict = "하락 + 거래량 감소 — 매도 소진"
        elif r20 < 0:
            verdict = "하락 + 거래량 증가 — 투매 진행"
        elif t_recent > 2:
            verdict = "상승 + 물량 유입 — 추세 유효"
        else:
            verdict = "판정 보류"
        print(f"  {name or path:<10}{r20:>+9.1f}%{dv:>+11.1f}%"
              f"{t_recent:>+12.2f}{gap:>+10.1f}%   {verdict}")
    print(f"\n  OBV t가 ±2를 넘으면 그 방향이 우연이 아니다.")
    print(f"  VWAP 대비가 음수면 그만큼 **위에 물린 물량**이 저항으로 남아 있다.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--name", default="종목")
    ap.add_argument("--compare", nargs="+", metavar="파일:이름")
    args = ap.parse_args()

    if args.compare:
        return compare(args.compare)
    if not args.file:
        ap.error("--file 또는 --compare 중 하나가 필요하다")

    ds, c, v, n, ret, obv = load(args.file)

    print(f"\n{'='*64}\n  {args.name} — 가격 × 거래량   {ds[0]} ~ {ds[-1]} ({n}일)\n{'='*64}")

    # ── 상승일 vs 하락일 거래량 ──
    up = [v[i + 1] for i, r in enumerate(ret) if r > 0]
    dn = [v[i + 1] for i, r in enumerate(ret) if r < 0]
    mu, md = mean(up), mean(dn)
    print(f"\n▸ 어느 쪽에 거래량이 실렸나")
    print(f"    상승일 {len(up):>3}일   평균 거래량 {mu:>12,.0f}")
    print(f"    하락일 {len(dn):>3}일   평균 거래량 {md:>12,.0f}")
    ratio = mu / md
    print(f"    비율 {ratio:.2f}   → " + (
        "**상승에 힘이 실린다**(매집)" if ratio > 1.15 else
        "**하락에 힘이 실린다**(분산·투매)" if ratio < 0.87 else
        "한쪽으로 치우치지 않음"))

    # ── OBV ──
    seg = max(20, n // 4)
    o_recent = ols(obv[-seg:], [list(range(seg))], ["t"])
    o_all = ols(obv, [list(range(n))], ["t"])
    print(f"\n▸ OBV (누적 매수−매도 거래량)")
    print(f"    전체 기울기   {o_all['beta'][1]:>+14,.0f}/일   t={o_all['t'][1]:+.2f}")
    print(f"    최근 {seg}일   {o_recent['beta'][1]:>+14,.0f}/일   t={o_recent['t'][1]:+.2f}")
    if o_all["beta"][1] < 0 < o_recent["beta"][1]:
        print("    → 전체는 매도 우위였는데 **최근 매수 우위로 전환**")
    elif o_all["beta"][1] > 0 > o_recent["beta"][1]:
        print("    → 전체는 매수 우위였는데 **최근 매도 우위로 전환**")
    else:
        print("    → 방향 유지")

    # 주가와 OBV가 어긋나는가 — 이게 이 스크립트의 핵심
    r_seg = math.log(c[-1] / c[-seg]) * 100
    t_r = o_recent["t"][1]
    print(f"    최근 {seg}일 주가 {r_seg:+.1f}%")
    if r_seg > 1 and t_r < -2:
        print("    → ⚠️ **괴리: 주가는 오르는데 물량은 넘어가고 있다.**")
        print("       오르는 동안 누군가 팔고 있다는 뜻이라 그 상승은 힘이 없다")
    elif r_seg < -1 and t_r > 2:
        print("    → **괴리: 주가는 빠지는데 물량은 들어오고 있다.**")
        print("       빠지는 동안 누군가 받고 있다는 뜻이라 바닥 신호로 읽는다")
    else:
        print("    → 주가와 OBV가 같은 방향. 괴리 없음")

    # ── 거래량 추세 ──
    v20, vprev = mean(v[-20:]), mean(v[:-20])
    print(f"\n▸ 거래량 추세")
    print(f"    최근 20일 평균 {v20:>12,.0f}")
    print(f"    그 이전 평균   {vprev:>12,.0f}   ({v20/vprev*100-100:+.1f}%)")
    r20 = math.log(c[-1] / c[-21])
    print(f"    같은 기간 주가 {r20*100:+.1f}%")
    if r20 < 0 and v20 < vprev:
        print("    → **하락 + 거래량 감소 = 매도 소진.** 바닥 신호일 수 있다")
    elif r20 < 0 and v20 > vprev:
        print("    → **하락 + 거래량 증가 = 투매 진행 중.** 아직 안 끝났다")
    elif r20 > 0 and v20 > vprev:
        print("    → **상승 + 거래량 증가 = 건강한 상승**")
    else:
        print("    → **상승 + 거래량 감소 = 힘이 빠진 상승.** 되돌림 주의")

    # ── 거래대금 가중 평균가 (매물대) ──
    tot = sum(v)
    vwap = sum(c[i] * v[i] for i in range(n)) / tot
    v60 = sum(v[-60:])
    vwap60 = sum(c[i] * v[i] for i in range(n - 60, n)) / v60 if n >= 60 else None
    print(f"\n▸ 거래대금 가중 평균가 (매물이 쌓인 자리)")
    print(f"    전체 기간 {vwap:>10,.0f}   현재가 대비 {c[-1]/vwap*100-100:+.1f}%")
    if vwap60:
        print(f"    최근 60일 {vwap60:>10,.0f}   현재가 대비 {c[-1]/vwap60*100-100:+.1f}%")
    print("    → 현재가가 이보다 낮으면 **위에 물린 물량**이 저항으로 남는다")

    # ── 신고가·신저가 ──
    hi20 = sum(1 for i in range(20, n) if c[i] >= max(c[i-20:i+1]))
    lo20 = sum(1 for i in range(20, n) if c[i] <= min(c[i-20:i+1]))
    hi20r = sum(1 for i in range(n-20, n) if c[i] >= max(c[i-20:i+1]))
    lo20r = sum(1 for i in range(n-20, n) if c[i] <= min(c[i-20:i+1]))
    print(f"\n▸ 20일 신고가·신저가")
    print(f"    전체   신고가 {hi20:>3}회   신저가 {lo20:>3}회")
    print(f"    최근 20일 신고가 {hi20r:>3}회   신저가 {lo20r:>3}회   → " + (
        "상승 추세" if hi20r > lo20r else "하락 추세" if lo20r > hi20r else "방향 없음"))

    # ── 가격변화 ↔ 거래량 상관 ──
    vc = [math.log(v[i]/v[i-1]) if v[i]>0 and v[i-1]>0 else 0 for i in range(1, n)]
    print(f"\n▸ |수익률| ↔ 거래량 변화 상관  {corr([abs(x) for x in ret], vc):+.3f}")
    print("    양수면 크게 움직이는 날 거래량도 늘어난다는 뜻(정상)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
