#!/usr/bin/env python3
"""기간별 목표주가를 시나리오로 낸다. 의존성 없음.

**하나의 목표주가는 내지 않는다.** "1년 뒤 55만원"은 틀릴 뿐 아니라,
틀렸을 때 어디서 갈렸는지도 알 수 없다.

대신 **밸류에이션 배수를 시나리오로 두고** 기간별 가격을 낸다.
그러면 "PBR이 0.75로 돌아가면 얼마"가 되고, 사용자는
**배수 가정에만 동의하면** 나머지는 산수다.

    python3 target.py --name 현대차 --price 453000 --bps 471042 --eps 38028 \
                      --roe 8.45 --payout 28.1 --dps 10670 \
                      --pbr-band 0.51 0.96 --per-band 4.60 11.91
"""
import argparse, sys

HORIZONS = [("6개월", 0.5), ("1년", 1.0), ("2년", 2.0), ("3년", 3.0)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--price", type=float, required=True)
    ap.add_argument("--bps", type=float, required=True, help="직전 추정 BPS")
    ap.add_argument("--eps", type=float, required=True, help="직전 추정 EPS")
    ap.add_argument("--roe", type=float, required=True, help="%")
    ap.add_argument("--payout", type=float, required=True, help="배당성향 %")
    ap.add_argument("--dps", type=float, default=0)
    ap.add_argument("--pbr-band", type=float, nargs=2, required=True,
                    metavar=("LOW", "HIGH"))
    ap.add_argument("--eps-growth", type=float, default=0.0, help="연 EPS 성장 가정 %")
    args = ap.parse_args()

    g = args.roe / 100 * (1 - args.payout / 100)   # 자기자본 내부성장률
    lo, hi = args.pbr_band
    mid = (lo + hi) / 2
    cur_pbr = args.price / args.bps

    print(f"\n{'='*66}\n  {args.name} — 기간별 목표주가 (PBR 시나리오)\n{'='*66}")
    print(f"  현재가 {args.price:,.0f}   BPS {args.bps:,.0f}   "
          f"현재 PBR {cur_pbr:.2f}")
    print(f"  ROE {args.roe:.2f}% × 유보율 {100-args.payout:.1f}% "
          f"→ BPS 연 {g*100:.2f}% 증가 가정")
    print(f"  PBR 밴드 {lo:.2f} ~ {hi:.2f}  (중간 {mid:.2f})")
    if cur_pbr > hi * 0.98:
        print(f"  ⚠️  현재 PBR {cur_pbr:.2f}는 **밴드 상단**이다. "
              "'싸다'는 근거는 성립하지 않는다")
    elif cur_pbr < lo * 1.15:
        print(f"  · 현재 PBR {cur_pbr:.2f}는 **밴드 하단** 근처다")

    # ROE가 비정상적으로 높으면 영구성장 가정이 깨진다
    if args.roe > 25:
        print(f"  🚨 ROE {args.roe:.2f}%는 **피크 수치**일 가능성이 크다.")
        print(f"     이걸 영구 성장률(연 {g*100:.1f}%)에 쓰면 BPS가 폭주한다.")
        print(f"     정상화된 ROE를 --roe로 직접 넣어 다시 돌린다.")

    print(f"\n  {'기간':<7}{'예상 BPS':>11}"
          f"{'비관 '+f'{lo:.2f}':>13}{'중립 '+f'{mid:.2f}':>13}{'낙관 '+f'{hi:.2f}':>13}")
    print("  " + "-" * 62)
    for lbl, yrs in HORIZONS:
        bps = args.bps * (1 + g) ** yrs
        row = f"  {lbl:<7}{bps:>11,.0f}"
        for m in (lo, mid, hi):
            row += f"{bps*m:>13,.0f}"
        print(row)

    print(f"\n  ▸ 현재가 대비 (배당 재투자 제외)")
    print(f"  {'기간':<7}{'비관':>13}{'중립':>13}{'낙관':>13}")
    print("  " + "-" * 48)
    for lbl, yrs in HORIZONS:
        bps = args.bps * (1 + g) ** yrs
        row = f"  {lbl:<7}"
        for m in (lo, mid, hi):
            row += f"{(bps*m/args.price-1)*100:>+12.1f}%"
        print(row)

    if args.dps:
        dy = args.dps / args.price
        print(f"\n  ▸ 배당까지 더한 총수익률 (배당수익률 {dy*100:.2f}% 가정)")
        print(f"  {'기간':<7}{'비관':>13}{'중립':>13}{'낙관':>13}")
        print("  " + "-" * 48)
        for lbl, yrs in HORIZONS:
            bps = args.bps * (1 + g) ** yrs
            row = f"  {lbl:<7}"
            for m in (lo, mid, hi):
                row += f"{((bps*m/args.price-1)+dy*yrs)*100:>+12.1f}%"
            print(row)

    print(f"\n{'='*66}")
    print("  이 표의 유일한 가정은 **PBR이 밴드 안으로 돌아온다**는 것이다.")
    print("  회사의 성격이 바뀌면(예: 로봇 기업으로 재평가) 밴드 자체가 이동한다.")
    print("  그때는 밴드를 다시 잡아야지, 이 표를 그대로 쓰면 안 된다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
