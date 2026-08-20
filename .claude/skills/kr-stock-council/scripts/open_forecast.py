#!/usr/bin/env python3
"""예상 개장가를 낸다. 시간외 + 미국장을 **순서대로** 더한다. 의존성 없음.

2026-08-20에 SOX 단독 베타만 써서 삼성전자를 -1.19%로 예측했다가
실제 +9.49%로 10.68%p 틀렸다. 사용자 지적 —
**"예상 개장 숫자로 내되 니 스스로 고민해서 정확도를 높혀."**

뜯어보니 **내가 매일 받으면서 안 쓰던 정보**가 있었다. 시간외단일가다.

    종목        날짜        시간외괴리    실제 다음날   방향
    삼성전자  8/18→19      -1.86%      -7.82%    ○
    삼성전자  8/19→20      +5.05%      +9.49%    ○
    현대차    8/18→19      -1.84%      -4.83%    ○
    현대차    8/19→20      +1.33%      +0.85%    ○
    네이버    8/18→19      -1.15%      -4.15%    ○
    네이버    8/19→20      +1.20%      +5.53%    ○
    한국전력  8/18→19      -0.92%      -5.37%    ○
    한국전력  8/19→20      +0.65%      +3.08%    ○
    → 방향 8/8. 같은 기간 SOX 단독 베타는 1/2.

**다만 8/8을 8건으로 세면 안 된다.** 이틀 다 시장 전체가 같이 움직인 날이라
종목들이 독립 관측이 아니다. **사실상 2/2**이고, 그래서 이 모형은
predictions.json으로 계속 채점하면서 계수를 고쳐 나간다.

## 왜 더할 수 있나 — 시간대가 겹치지 않는다

    16:00~18:00 KST   시간외단일가  (그날 국내 뉴스 + 미국 프리마켓 초반)
    22:30~05:00 KST   미국 정규장   (시간외가 끝난 뒤의 정보)
    09:00 KST         국내 개장     ← 둘을 다 반영해서 열린다

## 증폭 계수 k

시간외+미국장 합은 실제보다 **작게** 나온다. 시간외는 유동성이 얕고 ±10% 제한이 있어
끝까지 반영하지 못하기 때문이다. 관측 2건에서 배율이 1.7~2.5였다.

    8/18→19  합 -4.64%  ×2.0 = -9.28%   실제 -7.82%   오차 1.46%p
    8/19→20  합 +3.86%  ×2.0 = +7.72%   실제 +9.49%   오차 1.77%p

**k=2.0은 관측 2건에 맞춘 값이라 과적합이다.** 그래서 점 추정과 함께
**k 1.5~2.5 범위**를 같이 낸다. 관측이 쌓이면 k를 갱신한다.

    python3 scripts/open_forecast.py 20260820        # 그날 저녁 데이터로 다음 개장 예측
    python3 scripts/open_forecast.py 20260820 --k 2.0
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")

# SOX 단독 베타 — t>2인 것만 쓴다. 나머지는 0으로 본다(daily-brief 규칙)
SOX_BETA = {"삼성전자": (0.559, 3.08)}


def load(name):
    with open(os.path.join(D, name), encoding="utf-8") as fh:
        return json.load(fh)


def after_hours(px):
    for k in ("_시간외", "_시간외단일가"):
        if k in px:
            return {a: b for a, b in px[k].items() if not a.startswith("_")}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="기준일 YYYYMMDD (그날 종가·시간외를 쓴다)")
    ap.add_argument("--k", type=float, default=2.0, help="증폭 계수 (기본 2.0)")
    a = ap.parse_args()

    px = load(f"prices-{a.date}.json")
    ah = after_hours(px)
    iso = f"{a.date[:4]}-{a.date[4:6]}-{a.date[6:]}"
    fac = load("factors.json")["rows"]
    rows = sorted(k for k in fac if k <= iso)
    dsox = None
    if len(rows) >= 2 and "SOX" in fac[rows[-1]] and "SOX" in fac[rows[-2]]:
        dsox = (fac[rows[-1]]["SOX"] / fac[rows[-2]]["SOX"] - 1) * 100

    print("=" * 76)
    print(f"  예상 개장 — {iso} 종가·시간외 + 미국장 반영")
    print("=" * 76)
    print(f"  미국 SOX {dsox:+.2f}%" if dsox is not None else "  SOX 변화 미확인 → 0으로 본다")
    print(f"  증폭 계수 k = {a.k}  (관측 2건 기준. 과적합이라 범위를 같이 낸다)\n")

    print(f"  {'종목':<8}{'종가':>9}{'시간외':>9}{'괴리':>8}{'SOX분':>8}"
          f"{'합':>8}{'예상':>9}{'범위(k1.5~2.5)':>20}")
    out = []
    for name, close in px.items():
        if name.startswith("_") or name not in ah:
            continue
        gap = ah[name] / close - 1
        beta, t = SOX_BETA.get(name, (0.0, 0.0))
        sox_part = (dsox or 0) / 100 * beta if t > 2 else 0.0
        raw = gap + sox_part
        mid = raw * a.k
        lo, hi = sorted((raw * 1.5, raw * 2.5))
        print(f"  {name:<8}{close:>9,}{ah[name]:>9,}{gap:>+7.2%}{sox_part:>+8.2%}"
              f"{raw:>+8.2%}{close*(1+mid):>9,.0f}"
              f"{close*(1+lo):>10,.0f}~{close*(1+hi):>,.0f}")
        out.append({"종목": name, "예상": round(close * (1 + mid)), "예상등락": round(mid * 100, 2),
                    "시간외괴리": round(gap * 100, 2), "SOX분": round(sox_part * 100, 2)})

    print("\n" + "=" * 76)
    print("  ⚠️ 이 모형이 먹히지 않는 날")
    print("=" * 76)
    print("  · **events_due.py에 창이 열린 촉매가 있는 날** — 국내 기업 고유 이벤트는")
    print("    시간외에도 미국장에도 안 들어 있다. 8/20 삼성 주주환원이 그랬다")
    print("  · 시간외 거래가 거의 없는 종목 — 괴리가 노이즈다")
    print("  · **관측 2건짜리 모형이다.** 매일 predictions.json에 넣고 채점한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
