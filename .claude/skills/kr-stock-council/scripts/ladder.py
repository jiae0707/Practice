#!/usr/bin/env python3
"""적정주가를 넘는 구간에 분할 매도 사다리를 만든다. 의존성 없음.

**고점에서 못 파는 이유는 판단이 늦어서가 아니라 규칙이 없어서다.**
750,000원일 때 "더 오를까"를 생각하면 못 판다. 그 자리에서 판단하면
누구도 못 판다 — 오르는 중에는 항상 더 오를 것 같기 때문이다.

그래서 **오르기 전에 미리 정하고 지정가로 걸어둔다.** 그러면 판단이
아니라 체결이 된다. 사다리로 나누는 이유는 두 가지다:

  · 한 번에 다 팔면 그 위로 더 갔을 때 후회가 남는다
  · 한 번에 안 팔면 되돌림에서 전부 놓친다

    python3 ladder.py --name 현대차 --price 453000 --qty 2302 \
        --fair 317500 370300 --keep 0.5

`--fair`는 적정주가 밴드(하단 상단)다. 밴드 상단부터 사다리를 시작한다.
`--keep`은 끝까지 남길 비율 — **전량을 팔지 않는 이유**는 서사가 맞을
수도 있기 때문이다. 틀려도 되고 맞아도 되게 만든다.
"""
import argparse, sys

TAX = 0.0020 + 0.00015     # 증권거래세 + 수수료
STEPS = 4                   # 사다리 칸 수


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--price", type=float, required=True, help="현재가")
    ap.add_argument("--qty", type=int, required=True, help="보유 주수")
    ap.add_argument("--fair", type=float, nargs=2, required=True,
                    metavar=("하단", "상단"), help="적정주가 밴드")
    ap.add_argument("--keep", type=float, default=0.5,
                    help="끝까지 남길 비율 (0~1). 기본 0.5")
    ap.add_argument("--avg", type=float, help="평단. 있으면 손익을 같이 낸다")
    ap.add_argument("--peak", type=float, help="과거 고점. 있으면 대조한다")
    args = ap.parse_args()

    lo, hi = args.fair
    sellable = int(args.qty * (1 - args.keep))
    over = args.price / hi - 1

    print(f"\n{'='*70}\n  {args.name} — 분할 매도 사다리\n{'='*70}")
    print(f"  현재가 {args.price:,.0f}   보유 {args.qty:,}주")
    print(f"  적정주가 밴드 {lo:,.0f} ~ {hi:,.0f}")
    print(f"  → 현재가는 밴드 상단 대비 **{over*100:+.1f}%**")

    if over > 0:
        print(f"\n  ⚠️ **이미 적정주가를 넘었다.** 첫 칸은 오르기를 기다리지 않는다.")
        start = args.price
    else:
        print(f"\n  아직 밴드 안이다. 사다리는 밴드 상단부터 시작한다.")
        start = hi

    print(f"  끝까지 보유할 물량 {args.qty - sellable:,}주 ({args.keep*100:.0f}%)"
          f" — **서사가 맞을 경우를 남겨둔다**")

    # 사다리 — 위로 갈수록 더 판다. 오를수록 고평가가 커지기 때문이다.
    weights = [1, 2, 3, 4][:STEPS]
    tot_w = sum(weights)
    print(f"\n▸ 사다리 — 위로 갈수록 많이 판다 (오를수록 괴리가 커지므로)")
    print(f"    {'가격':>10}{'현재가 대비':>11}{'매도':>8}{'세후 수령':>12}"
          f"{'누적 매도':>10}{'남는 주수':>10}")
    done = 0
    for i, w in enumerate(weights):
        px = start * (1 + 0.08 * i)          # 8%씩 위로
        q = int(sellable * w / tot_w)
        if i == len(weights) - 1:
            q = sellable - done               # 마지막 칸이 잔여를 흡수
        done += q
        net = px * q * (1 - TAX)
        print(f"    {px:>10,.0f}{px/args.price*100-100:>+10.1f}%{q:>7,}주"
              f"{net/1e4:>10,.0f}만{done:>9,}주{args.qty-done:>9,}주")

    if args.avg:
        print(f"\n▸ 손익 (평단 {args.avg:,.0f})")
        g = args.price / args.avg - 1
        print(f"    현재 수익률 {g*100:+.1f}% → **{'익절' if g > 0 else '손절'}이다**")
        if g > 0:
            print(f"    사다리 전량({sellable:,}주) 체결 시 세전 차익 "
                  f"{(start-args.avg)*sellable/1e8:.2f}억 이상")

    if args.peak:
        print(f"\n▸ 과거 고점 {args.peak:,.0f}과 대조")
        print(f"    지금은 고점 대비 {args.price/args.peak*100-100:+.1f}%다.")
        hit = [i for i, w in enumerate(weights)
               if start * (1 + 0.08 * i) <= args.peak]
        if hit:
            print(f"    **이 사다리가 그때 걸려 있었다면 {len(hit)}칸이 체결됐다.**")
            print(f"    고점에서 판단하려 했기 때문에 한 주도 못 판 것이다.")

    print(f"\n{'='*70}")
    print("  이 사다리의 목적은 **최고점을 맞히는 것이 아니다.** 그건 불가능하다.")
    print("  목적은 **오르는 중에 판단하지 않는 것**이다. 미리 걸어두면 체결된다.")
    print("  밴드가 바뀌면(실적·서사 검증) 사다리도 다시 만든다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
