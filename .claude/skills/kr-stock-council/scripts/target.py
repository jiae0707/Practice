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

**밴드 위치만 보는 건 위험하다.** PBR은 ROE를 따라가므로 이익이 줄어서
PBR이 같이 내려온 걸 저평가로 오독한다. `--roe-adjust`로 검산한다.

    python3 target.py --roe-adjust 한국전력 --price 33250
"""
import argparse, json, os, sys

HORIZONS = [("6개월", 0.5), ("1년", 1.0), ("2년", 2.0), ("3년", 3.0)]
HERE = os.path.dirname(os.path.abspath(__file__))
FIN = os.path.join(HERE, "..", "data", "financials.json")


def roe_adjust(name, price):
    """PBR과 ROE의 관계로 적정 PBR을 구한다.

    같은 ROE인데 PBR이 높아졌다면 밴드 하단이어도 비싸진 것이다.
    관계는 종목마다 다른 게 정상이라 **같은 종목의 시계열로만** 비교한다.

    두 가지 방법을 같이 낸다.
      · 비율법  적정PBR = 평균(PBR/ROE) × 당기ROE
      · 회귀법  PBR = a + b×ROE 를 적합하고 당기 ROE를 넣는다

    **비율법은 ROE가 낮은 해에서 폭주한다.** PBR/ROE는 ROE로 나눈 값이라
    ROE 4%인 해 하나가 평균을 통째로 끌어올린다. 둘이 갈리면 회귀법을 쓰고,
    갈렸다는 사실 자체를 결론에 적는다.
    """
    with open(FIN, encoding="utf-8") as fh:
        fin = json.load(fh)
    if name not in fin:
        print(f"{name}이 financials.json에 없다. 있는 것: "
              f"{[k for k in fin if not k.startswith('_')]}")
        return 1
    ann = fin[name]["annual"]
    rows, suspect, loss = [], [], []
    prev_rev = None
    for yr in sorted(ann):
        a = ann[yr]
        roe, pbr, bps, rev = a.get("roe"), a.get("pbr"), a.get("bps"), a.get("revenue")
        if roe is not None and roe <= 0:
            # 적자 연도. PBR/ROE는 음수가 되어 못 쓴다. 다만 **버리면 안 된다** —
            # 경기민감주에서 적자 해는 사이클 바닥이고, 가장 정보가 많은 관측치다.
            loss.append((yr, roe, a.get("op")))
            continue
        if not roe or not pbr:
            continue
        # 캡처 오류 감지 — 이 숫자를 그대로 쓰면 결론이 통째로 틀린다
        if a.get("_suspect"):
            suspect.append((yr, a["_suspect"]))
        else:
            rows.append((yr, a.get("op"), roe, pbr, pbr / roe, bps))
        prev_rev = rev or prev_rev

    print(f"\n{'='*66}\n  {name} — ROE로 보정한 적정 PBR\n{'='*66}")
    print(f"  {'연도':<10}{'영업이익':>10}{'ROE':>8}{'PBR':>7}{'PBR/ROE':>10}")
    for yr, op, roe, pbr, ratio, _ in rows:
        op_s = f"{op/10000:,.1f}조" if op else "—"
        print(f"  {yr:<10}{op_s:>10}{roe:>7.2f}%{pbr:>7.2f}{ratio:>10.4f}")

    if loss:
        print(f"\n  ⛔ **적자 연도가 있다. 이 종목에 PBR/ROE 방법을 쓰지 않는다.**")
        for yr, roe, op in loss:
            op_s = f"영업이익 {op/10000:+.1f}조" if op else ""
            print(f"     {yr}: ROE {roe:.2f}%  {op_s}")
        print(f"     적자 해는 PBR/ROE가 음수라 계산에서 빠지는데, **버리면 안 되는 관측치**다.")
        print(f"     경기민감주에서 적자 해는 사이클 바닥이고 정보가 가장 많다.")
        print(f"     남은 {len(rows)}년으로 평균을 내면 **사이클의 좋은 쪽만 보는 것**이 된다.")
        print(f"     → 정상화 이익(사이클 전체 평균)과 `implied.py`의 EV 기준으로 간다.")
        return 1

    if suspect:
        print(f"\n  ⚠️  제외한 연도 — 데이터가 검증되지 않았다")
        for yr, why in suspect:
            print(f"     {yr}: {why}")
        print(f"     **검증 전에는 이 종목 결론을 내지 않는다.**")
        return 1

    # 정점이익 차단 — 여기서 걸리면 이 방법 자체가 성립하지 않는다
    if len(rows) >= 2:
        cur_roe = rows[-1][2]
        peak = max(r[2] for r in rows[:-1])
        if cur_roe > peak * 1.8:
            print(f"\n  ⛔ **당기 ROE {cur_roe:.2f}%가 과거 최고 {peak:.2f}%의"
                  f" {cur_roe/peak:.1f}배다. 정점이익이다.**")
            print(f"     이 방법은 ROE가 정상 수준일 때만 쓴다. 정점 ROE를 넣으면")
            print(f"     적정 PBR이 그만큼 부풀어 **터무니없는 상승여력**이 나온다.")
            print(f"     → `implied.py --cycle {name} --price <현재가>`로 역산한다.")
            return 1

    if len(rows) < 3:
        print("\n  관측치가 3년 미만이라 관계를 추정할 수 없다. 계산하지 않는다.")
        return 1
    if len(rows) - 1 < 3:
        print(f"\n  과거 관측치가 {len(rows)-1}년뿐이다. **회귀는 하지 않는다** —")
        print(f"  두 점을 지나는 직선은 항상 완벽해서 참이지만 아무 정보가 없다.")

    # 당기(마지막 연도)를 빼고 과거로만 관계를 만든다 — 당기를 넣으면 자기 자신으로 자기를 평가한다
    past = rows[:-1]
    cur_yr, _, cur_roe, cur_pbr, _, cur_bps = rows[-1]

    avg = sum(r[4] for r in past) / len(past)
    pbr_ratio = avg * cur_roe

    # 회귀법 — 단순 2변수 OLS. ROE로 나누지 않으므로 저ROE 해에 휘둘리지 않는다
    xs = [r[2] for r in past]
    ys = [r[3] for r in past]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs))) / sxx if sxx else 0
    a = my - b * mx
    pbr_reg = a + b * cur_roe
    use_reg = len(past) >= 3 and b > 0

    print(f"\n▸ 당기 {cur_yr}는 평가 대상이라 빼고, 과거 {len(past)}년으로만 관계를 만든다")
    print(f"  {'방법':<8}{'적정 PBR':>10}{'적정주가':>13}{'현재가 대비':>13}")
    methods = [("비율법", pbr_ratio)] + ([("회귀법", pbr_reg)] if len(past) >= 3 else [])
    for lbl, p in methods:
        fv = p * cur_bps
        gap = f"{fv/price*100-100:>+12.1f}%" if price else " " * 13
        print(f"  {lbl:<8}{p:>10.3f}{fv:>12,.0f}원{gap}")
    print(f"  {'현재':<8}{cur_pbr:>10.2f}{cur_pbr*cur_bps:>12,.0f}원")
    print(f"    비율법: 평균 PBR/ROE {avg:.4f} × ROE {cur_roe:.2f}%")
    if len(past) >= 3:
        print(f"    회귀법: PBR = {a:+.3f} {b:+.4f}×ROE, 여기에 ROE {cur_roe:.2f}% 대입")

    if len(past) >= 3 and b <= 0:
        print(f"\n  ⛔ **ROE 기울기가 음수({b:+.4f})다. 이 종목에는 모형이 안 맞는다.**")
        print(f"     ROE가 떨어지는 동안 PBR이 올랐다는 뜻이다. 그러면 이 가격은")
        print(f"     이익이 아니라 **다른 이유로 매겨진 것**이고, 적정주가라고 부를 수 없다.")
        print(f"     위 숫자는 밸류에이션이 아니라 **ROE로 설명되지 않는 부분의 크기**로만 읽는다.")
        print(f"     → 그 '다른 이유'가 무엇인지 대고, 그게 값을 하는지를 따로 검증한다.")
    lo_roe = min(xs)
    if lo_roe < 6:
        print(f"\n  ⚠️  과거에 ROE {lo_roe:.2f}%인 해가 있다. PBR/ROE는 ROE로 나눈 값이라")
        print(f"     그 해 하나가 비율법 평균을 끌어올린다."
              + ("  **회귀법을 쓴다.**" if use_reg else ""))
    if len(past) >= 3 and pbr_ratio and abs(pbr_reg / pbr_ratio - 1) > 0.2:
        print(f"\n  ⚠️  두 방법이 {abs(pbr_reg/pbr_ratio-1)*100:.0f}% 갈린다."
              f" 3~4개 관측치로는 어느 쪽도 정밀하지 않다.")
        print(f"     **숫자를 결론으로 쓰지 말고 방향만 쓴다.**")

    print(f"\n▸ 같은 ROE였던 해와 비교 — 이게 가장 덜 가공된 근거다")
    close = sorted(past, key=lambda r: abs(r[2] - cur_roe))[0]
    print(f"  {close[0]}: ROE {close[2]:.2f}%  PBR {close[3]:.2f}")
    print(f"  {cur_yr}: ROE {cur_roe:.2f}%  PBR {cur_pbr:.2f}"
          f"   → ROE는 {cur_roe-close[2]:+.2f}%p인데 PBR은 "
          f"{cur_pbr/close[3]*100-100:+.1f}%")
    print(f"\n  밴드 위치와 이 값이 어긋나면 **ROE 기준을 따른다.**")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roe-adjust", metavar="종목",
                    help="financials.json의 PBR/ROE 시계열로 적정 PBR 검산")
    ap.add_argument("--name")
    ap.add_argument("--price", type=float)
    ap.add_argument("--bps", type=float, help="직전 추정 BPS")
    ap.add_argument("--eps", type=float, help="직전 추정 EPS")
    ap.add_argument("--roe", type=float, help="%")
    ap.add_argument("--payout", type=float, help="배당성향 %")
    ap.add_argument("--dps", type=float, default=0)
    ap.add_argument("--pbr-band", type=float, nargs=2, metavar=("LOW", "HIGH"))
    ap.add_argument("--eps-growth", type=float, default=0.0, help="연 EPS 성장 가정 %")
    args = ap.parse_args()

    if args.roe_adjust:
        return roe_adjust(args.roe_adjust, args.price)
    missing = [f"--{k}" for k in ("name", "price", "bps", "eps", "roe", "payout")
               if getattr(args, k) is None]
    if missing or not args.pbr_band:
        ap.error("필요한 인자: " + ", ".join(missing + ([] if args.pbr_band else ["--pbr-band"])))

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
