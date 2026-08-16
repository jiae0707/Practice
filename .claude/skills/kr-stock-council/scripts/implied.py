#!/usr/bin/env python3
"""현재 주가에 반영된 기대치를 역산한다. 의존성 없음.

**미래를 예측하지 않는다.** 예측은 틀리고, 틀린 예측으로 판단하면 판단도 틀린다.
대신 방향을 뒤집는다 — **지금 이 가격이 성립하려면 무엇이 참이어야 하는가**를 푼다.
그러면 "시장이 이 회사를 어떻게 보고 있는지"가 숫자로 나오고,
사용자는 **거기에 동의하는지만** 판단하면 된다.

    python3 implied.py --name 현대차 --cap 92.7 --nopat 8.79 --beta 0.613
    python3 implied.py --name 현대차 --cap 92.7 --nopat 8.79 --beta 0.613 --story 로봇:15

단위는 조원. 자본비용은 측정된 베타로 CAPM을 쓴다(가정을 줄이려는 것이지
정답이라는 뜻은 아니다).
"""

import argparse
import json
import os
import sys

RF = 0.03          # 무위험수익률 가정 (한국 10년물 근처)
ERP = 0.06         # 주식 위험프리미엄 가정
TAX = 0.242
HERE = os.path.dirname(os.path.abspath(__file__))
FIN = os.path.join(HERE, "..", "data", "financials.json")


def ke(beta):
    return RF + beta * ERP


def cycle(name, price, beta, growths=(0.0, 0.02, 0.03, 0.05)):
    """정점이익 종목을 역산으로 다룬다.

    **경기민감주는 PER이 낮을 때가 고점이다.** 이익이 정점이면 EPS가 커서
    PER이 작아지고, 그걸 '싸다'로 읽으면 정확히 꼭대기에서 산다.

    그래서 당기 ROE를 정상 수준으로 쓰지 않는다. 대신 뒤집는다 —
    **지금 PBR이 성립하려면 ROE가 영구히 몇 %여야 하는가**를 푼다.

        PBR = (ROE − g) / (r − g)   →   ROE = PBR × (r − g) + g

    이 값이 과거 ROE 이력과 얼마나 떨어져 있는지가 판단 재료다.
    """
    with open(FIN, encoding="utf-8") as fh:
        fin = json.load(fh)
    if name not in fin:
        print(f"{name}이 financials.json에 없다.")
        return 1
    ann = fin[name]["annual"]
    yrs = sorted(ann)
    cur = ann[yrs[-1]]
    bps, pbr, cur_roe = cur["bps"], cur["pbr"], cur["roe"]
    r = ke(beta)

    print(f"\n{'='*68}\n  {name} — 정점이익 검사와 역산된 지속가능 ROE\n{'='*68}")
    print(f"  현재가 {price:,.0f}   BPS {bps:,.0f}   PBR {pbr:.2f}   "
          f"당기 ROE {cur_roe:.2f}%")
    print(f"  자본비용 {r*100:.2f}%  (무위험 {RF*100:.0f}% + 베타 {beta:.2f} "
          f"× 프리미엄 {ERP*100:.0f}%)")

    print(f"\n▸ ROE 이력")
    print(f"    {'연도':<10}{'영업이익':>10}{'ROE':>9}{'EPS':>10}{'PER':>8}{'PBR':>7}")
    for y in yrs:
        a = ann[y]
        op = f"{a['op']/10000:,.1f}조" if a.get("op") else "—"
        per = f"{a['per']:.2f}" if a.get("per") else "—"
        print(f"    {y:<10}{op:>10}{a['roe']:>8.2f}%{a.get('eps',0):>10,.0f}"
              f"{per:>8}{a.get('pbr',0):>7.2f}")

    past = [ann[y]["roe"] for y in yrs[:-1]]
    avg, peak = sum(past) / len(past), max(past)
    print(f"\n▸ 정점 판정")
    print(f"    과거 {len(past)}년 평균 ROE {avg:.2f}%   최고 {peak:.2f}%"
          f"   당기 {cur_roe:.2f}%")
    if cur_roe > peak * 1.8:
        print(f"    ⚠️ **당기 ROE가 과거 최고의 {cur_roe/peak:.1f}배다. 정점이익으로 다룬다.**")
        print(f"       이 ROE를 정상 수준으로 놓고 계산하면 적정주가가 폭주한다.")
        if cur.get("per"):
            print(f"       PER {cur['per']:.2f}는 싸 보이지만 **분모가 정점 EPS**다.")
    else:
        print(f"    당기 ROE가 과거 범위 안이다. 일반 절차를 써도 된다.")

    print(f"\n▸ 지금 가격이 성립하려면 ROE가 영구히 몇 %여야 하나")
    print(f"    {'영구성장 g':>10}{'필요 ROE':>11}{'당기 대비':>11}   시장이 보는 것")
    for g in growths:
        if g >= r:
            continue
        need = pbr * (r - g) + g
        share = need * 100 / cur_roe * 100   # need는 소수, cur_roe는 %
        print(f"    {g*100:>9.0f}%{need*100:>10.2f}%{share:>10.0f}%"
              f"   당기 이익의 {share:.0f}%만 지속된다고 본다")

    g0 = 0.03
    need0 = pbr * (r - g0) + g0
    print(f"\n    → 성장 {g0*100:.0f}% 기준 **{need0*100:.1f}%**."
          f" 과거 최고 {peak:.2f}%의 {need0*100/peak:.1f}배다.")
    print(f"       **시장은 이미 큰 폭의 정상화를 가격에 넣었다.**"
          f" 당기 {cur_roe:.2f}%를 믿는 게 아니다.")

    print(f"\n▸ ROE가 어디에 안착하느냐에 따른 가격  (g {g0*100:.0f}%, 자본비용 {r*100:.2f}%)")
    print(f"    {'지속 ROE':>10}{'적정 PBR':>11}{'적정주가':>13}{'현재가 대비':>13}"
          f"{'정규화 PER':>12}")
    scen = sorted(set([round(x, 2) for x in past]
                      + [10.0, 15.0, 20.0, round(need0 * 100, 2), 30.0, cur_roe]))
    for x in scen:
        fp = (x / 100 - g0) / (r - g0)
        if fp <= 0:
            continue
        px = fp * bps
        eps_n = x / 100 * bps
        mark = "  ← 역산값" if abs(x - need0 * 100) < 0.01 else (
               "  ← 당기" if abs(x - cur_roe) < 0.01 else "")
        print(f"    {x:>9.2f}%{fp:>11.2f}{px:>12,.0f}원"
              f"{px/price*100-100:>+12.1f}%{price/eps_n:>11.1f}배{mark}")

    print(f"\n{'='*68}")
    print(f"  이 표는 예측이 아니다. **어느 ROE를 믿느냐가 곧 가격**이라는 지도다.")
    print(f"  물어야 할 것은 '얼마까지 오르나'가 아니라")
    print(f"  **'{name}의 이익이 사이클을 지나 어디에 안착하나'**이다.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", metavar="종목",
                    help="정점이익 검사 + 역산된 지속가능 ROE (financials.json 사용)")
    ap.add_argument("--price", type=float, help="--cycle에서 쓰는 현재가")
    ap.add_argument("--name")
    ap.add_argument("--cap", type=float, help="시가총액(조원)")
    ap.add_argument("--nopat", type=float, help="연 세후영업이익(조원)")
    ap.add_argument("--beta", type=float, default=1.0, help="측정된 시장 베타")
    ap.add_argument("--net-debt", type=float, default=0.0, help="순부채(조원). 모르면 0")
    ap.add_argument("--story", help="서사 이름:추정가치(조원). 예 로봇:15")
    ap.add_argument("--wacc", type=float, help="직접 지정. 생략하면 CAPM")
    args = ap.parse_args()

    if args.cycle:
        if not args.price:
            ap.error("--cycle에는 --price가 필요하다")
        return cycle(args.cycle, args.price, args.beta)
    missing = [f"--{k}" for k in ("name", "cap", "nopat") if getattr(args, k) is None]
    if missing:
        ap.error("필요한 인자: " + ", ".join(missing))

    r = args.wacc if args.wacc else ke(args.beta)
    ev = args.cap + args.net_debt          # 기업가치
    steady = args.nopat / r                # 무성장 영구가치

    print(f"\n{'='*62}\n  {args.name} — 지금 가격에 반영된 기대치\n{'='*62}")
    print(f"  시가총액 {args.cap:.1f}조   순부채 {args.net_debt:.1f}조   "
          f"기업가치 {ev:.1f}조")
    print(f"  세후영업이익(NOPAT) {args.nopat:.2f}조/년")
    print(f"  자본비용 {r*100:.2f}%   "
          + (f"(CAPM: 무위험 {RF*100:.0f}% + 베타 {args.beta:.3f} × 프리미엄 {ERP*100:.0f}%)"
             if not args.wacc else "(직접 지정)"))

    print(f"\n▸ 이익이 지금 수준으로 영원히 유지된다면")
    print(f"    가치 = {args.nopat:.2f} ÷ {r:.4f} = {steady:.1f}조")
    gap = ev / steady - 1
    print(f"    현재 기업가치 {ev:.1f}조 → 그 값의 {ev/steady*100:.0f}%  ({gap*100:+.1f}%)")

    if gap < -0.05:
        print(f"\n    → **시장은 이익이 줄어든다고 보고 있다.**")
        print(f"       현재 가격이 성립하려면 NOPAT이 {args.nopat*ev/steady:.2f}조까지"
              f" 내려가면 된다 ({(ev/steady-1)*100:+.0f}%).")
        print(f"       바꿔 말하면 **이익만 지켜도 {(steady/ev-1)*100:+.0f}% 상승 여력**이다.")
    elif gap > 0.05:
        implied_g = r - args.nopat / ev
        print(f"\n    → **시장은 성장을 기대하고 있다.**")
        print(f"       현재 가격이 성립하려면 NOPAT이 매년 {implied_g*100:.2f}%씩"
              f" 영구히 늘어야 한다.")
        print(f"       이 숫자가 산업 성장률보다 높으면 가격이 앞서간 것이다.")
    else:
        print(f"\n    → 시장은 **지금 이익이 그대로 유지**된다고 보고 있다. 성장 프리미엄 0.")

    # 민감도 — 가정이 흔들리면 결론이 얼마나 바뀌나
    print(f"\n▸ 자본비용 가정에 따른 무성장 가치")
    print(f"    {'자본비용':>8}{'무성장 가치':>13}{'현재가 대비':>13}")
    for rr in (r - 0.02, r - 0.01, r, r + 0.01, r + 0.02):
        if rr <= 0:
            continue
        v = args.nopat / rr
        mark = "  ← 현재 가정" if abs(rr - r) < 1e-9 else ""
        print(f"    {rr*100:>7.2f}%{v:>13.1f}조{(ev/v-1)*100:>+12.1f}%{mark}")
    print("    자본비용 1%p 차이로 가치가 크게 흔들린다. **이 표를 같이 보여준다.**")

    # 순부채 민감도 — 이 가정 하나가 결론을 뒤집는다
    if args.net_debt == 0:
        print(f"\n▸ ⚠️  순부채를 0으로 뒀다. 이 가정이 결론을 통째로 바꾼다")
        print(f"    {'순부채':>8}{'기업가치':>11}{'무성장 대비':>13}   시장이 보는 것")
        for nd in (0, 20, 40, 60, 80):
            e = args.cap + nd
            g = e / steady - 1
            view = ("이익 감소 예상" if g < -0.05 else
                    "성장 기대" if g > 0.05 else "이익 유지")
            print(f"    {nd:>7.0f}조{e:>10.1f}조{g*100:>+12.1f}%   {view}")
        print("    **순부채를 확인하기 전에는 결론을 내지 않는다.**")
        print("    증권사 앱 기업정보 → 재무 → 총차입금·현금성자산으로 구한다.")

    # 서사 검증
    if args.story:
        nm, val = args.story.split(":")
        val = float(val)
        core = ev - val
        print(f"\n▸ 서사 검증 — '{nm}'에 {val:.1f}조가 붙어 있다고 보면")
        print(f"    본업 가치 = {ev:.1f} − {val:.1f} = {core:.1f}조")
        print(f"    본업만으로 계산한 무성장 가치 {steady:.1f}조와 비교하면"
              f" {core/steady*100:.0f}%")
        need = val * r
        print(f"    '{nm}'이 {val:.1f}조 값을 하려면 **연 {need:.2f}조의 세후이익**을"
              f" 내야 한다")
        print(f"    → 그 사업이 언제 그 이익을 내는지 답할 수 없으면,"
              f" 그 {val:.1f}조는 근거가 아니라 기대다")

    print(f"\n{'='*62}")
    print("  이건 예측이 아니라 역산이다. 가정(자본비용·NOPAT)이 바뀌면 답도 바뀐다.")
    print("  그래서 **결론이 아니라 질문**으로 쓴다 —")
    print("  '시장은 이렇게 보고 있는데, 나는 동의하는가?'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
