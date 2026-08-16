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
import sys

RF = 0.03          # 무위험수익률 가정 (한국 10년물 근처)
ERP = 0.06         # 주식 위험프리미엄 가정
TAX = 0.242


def ke(beta):
    return RF + beta * ERP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--cap", type=float, required=True, help="시가총액(조원)")
    ap.add_argument("--nopat", type=float, required=True, help="연 세후영업이익(조원)")
    ap.add_argument("--beta", type=float, default=1.0, help="측정된 시장 베타")
    ap.add_argument("--net-debt", type=float, default=0.0, help="순부채(조원). 모르면 0")
    ap.add_argument("--story", help="서사 이름:추정가치(조원). 예 로봇:15")
    ap.add_argument("--wacc", type=float, help="직접 지정. 생략하면 CAPM")
    args = ap.parse_args()

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
