#!/usr/bin/env python3
"""아침 브리핑에서 **반드시 검색해야 할 목록**을 기계적으로 뽑는다.

2026-08-21에 사용자에게 지적당했다 — "내가 준 캡쳐만 사용하지 말고
니 스스로 종목 검색을 하랬지. 왜 안 해?"
그날 검색을 **한 번**만 했고, 원/달러·WTI·금리·VIX는 찾아보지도 않고
"미확인"이라고 썼다. **"검색을 안 한 것"과 "검색했는데 없는 것"은 다르다**는
규칙을 내가 어겼다. 규칙만으로는 안 되므로 목록을 기계가 뽑는다.

    python3 scripts/brief_checklist.py
"""
import json, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PF = os.path.join(HERE, "..", "data", "portfolio.json")

# 쿼리를 박아둔다. 생각할 여지를 없애야 빠뜨리지 않는다.
# {d} 자리에 날짜가 들어간다.
MACRO = [
    ("원/달러 · WTI · 미10년물 · VIX",
     "현대차 환율 · 한전 연료비 · 네이버 할인율",
     "원달러 환율 WTI 유가 미국 10년물 국채금리 {d} 마감"),
    ("미국 지수 (캡처가 없을 때만)",
     "나스닥·S&P500·다우·SOX",
     "뉴욕증시 마감 {d} 나스닥 S&P500 다우 필라델피아 반도체"),
]
WATCH = {
    "현대차": "GM·포드·테슬라, 원/달러, 미국 관세, BD 나스닥 상장",
    "현대차우": "보통주와 동일 + 우선주 괴리",
    "네이버": "나스닥, 미국 플랫폼주, 국내 플랫폼 규제",
    "삼성전자": "SOX, 마이크론·엔비디아·TSMC, HBM, **주주환원 발표**",
    "한국전력": "유가·LNG, 전기요금 정책, AI 데이터센터 전력",
    "넥스틸": "WTI, 미국 리그 카운트, 철강 관세",
    "동국산업": "중국 철강 가격, 국내 건설·조선 발주",
    "비츠로셀": "방산·군수 발주, 스마트미터 수주",
    "화인베스틸": "조선 수주, **재무 공시**(소멸 위험)",
}


def main():
    with open(PF, encoding="utf-8") as fh:
        pf = json.load(fh)
    names = [h["name"] for h in pf["holdings"]]

    print("=" * 72)
    print("  오늘 브리핑에서 검색할 것 — 빠짐없이 훑는다")
    print("=" * 72)
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print("\n▸ 거시 — **사용자에게 묻지 않는다. 내가 검색한다**")
    for k, why, q in MACRO:
        print(f"    [ ] {k}")
        print(f"        왜: {why}")
        print(f"        쿼리: {q.format(d=d)}")

    print(f"\n▸ 보유 {len(names)}종목 — 한 종목당 검색 한 번이면 된다")
    for n in names:
        print(f"    [ ] {n:<10} {WATCH.get(n, '뉴스·공시')}")

    print("\n" + "=" * 72)
    print("  규칙")
    print("=" * 72)
    print("  · 뉴스를 나열하지 않는다. **'내 어느 판단에 들어가는가'**를 붙인다")
    print("  · **±5% 이상 움직인 종목은 원인을 찾을 때까지 멈추지 않는다**")
    print("  · 못 찾았으면 '세 쿼리로 찾았는데 없었다'고 쓴다.")
    print("    **검색을 안 하고 '미확인'이라고 쓰는 건 거짓말이다**")
    print("  · 검색값이 캡처(1급)와 어긋나면 검색값을 버린다")
    print("  · **사용자에게 시세·환율·유가·뉴스를 묻지 않는다.** 내가 구할 수 있다.")
    print("    묻는 건 계좌 상태와 본인 의사뿐이다 (SKILL.md '내가 구할 수 있는 건 묻지 않는다')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
