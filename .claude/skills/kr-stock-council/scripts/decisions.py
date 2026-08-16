#!/usr/bin/env python3
"""결론 이력을 기록하고, 번복이 정당한지 기계적으로 판정한다. 의존성 없음.

**이 스킬의 가장 큰 실패는 틀린 것이 아니라 자주 뒤집힌 것이다.**
사용자가 지적할 때마다 결론이 바뀌면, 맞은 결론도 믿을 수 없다.

번복에는 두 종류가 있고 **완전히 다르게 취급한다**:

  · **갱신(update)** — 새 정보가 들어와서 바뀌었다. 정당하다.
    사전에 등록한 반증 조건에 실제로 걸린 경우다.
  · **표류(drift)** — 같은 데이터로 다른 방법을 써서 바뀌었다. 정당하지 않다.
    이건 새 판단이 아니라 **첫 판단이 덜 검증됐다는 뜻**이다.

    python3 decisions.py --list
    python3 decisions.py --log 한국전력 --verdict 보유 --confidence 중 \
        --basis "ROE 보정 -26.1%" --falsify "2027E ROE가 12% 위로 올라오면"
    python3 decisions.py --flip 한국전력 --reason "요금 인상 확정" --new 추매
    python3 decisions.py --audit
"""
import argparse, json, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "..", "data", "decisions.json")

# 신뢰등급 — 결론마다 반드시 붙인다. 등급이 곧 번복 문턱이다.
#
# **두 가지를 혼동하지 않는다.**
#   1) 종목의 신뢰도가 아니라 **내 판단의 신뢰도**다.
#      한국전력이 '하'인 건 나쁜 회사라서가 아니라 판단할 근거가 없어서다.
#   2) "맞을 확률"이 아니라 **"내가 말을 바꿀 확률"**이다.
#      수익률 확률은 못 낸다. 근거가 얼마나 두꺼운지는 셀 수 있다.
CONF = {
    "상": "방법 둘이 같은 방향 + 확인된 사실. 번복하려면 새 사실이 필요하다 "
          "(다시 계산해봤다고 바뀌지 않는다) → 사용자: 이걸로 움직여도 된다",
    "중": "방법 하나. 가정에 민감하다. 가정이 틀리면 바뀐다 "
          "→ 사용자: 가정을 보고 동의하면 움직인다",
    "하": "데이터가 얇거나 모형이 안 맞는다. 언제든 바뀐다 "
          "→ 사용자: **믿지 말고 아무것도 안 하는 게 맞다.** 결론이 아니라 관찰로 쓴다",
}


def load():
    if not os.path.exists(LOG):
        return {"_note": "결론 이력. 번복할 때 사전 등록된 반증 조건과 대조한다.",
                "decisions": []}
    with open(LOG, encoding="utf-8") as fh:
        return json.load(fh)


def save(d):
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)


def latest(d, name):
    hits = [x for x in d["decisions"] if x["name"] == name]
    return hits[-1] if hits else None


def cmd_list(d, name=None):
    rows = [x for x in d["decisions"] if not name or x["name"] == name]
    if not rows:
        print("기록된 결론이 없다.")
        return 0
    print(f"\n{'='*76}\n  결론 이력\n{'='*76}")
    cur = None
    for x in rows:
        if x["name"] != cur:
            cur = x["name"]
            print(f"\n▸ {cur}")
        kind = x.get("kind", "신규")
        mark = {"표류": "⛔", "갱신": "✅", "신규": "  "}.get(kind, "  ")
        print(f"  {mark} {x['date']}  [{x['confidence']}] {x['verdict']}")
        print(f"       근거   {x['basis']}")
        print(f"       반증   {x['falsify']}")
        if x.get("flip_reason"):
            print(f"       번복   {x['flip_reason']}  → **{kind}**")
    return 0


def cmd_log(d, args):
    if args.confidence not in CONF:
        print(f"신뢰등급은 {list(CONF)} 중 하나다.")
        return 1
    prev = latest(d, args.name)
    rec = dict(name=args.name, date=args.date or date.today().isoformat(),
               verdict=args.verdict, confidence=args.confidence,
               basis=args.basis, falsify=args.falsify, kind="신규")
    if prev:
        print(f"⚠️  {args.name}에는 이미 결론이 있다 ({prev['date']} {prev['verdict']}).")
        print(f"    바꾸려면 --log가 아니라 **--flip**을 쓴다. 그래야 표류인지 판정된다.")
        return 1
    d["decisions"].append(rec)
    save(d)
    print(f"기록: {args.name} [{args.confidence}] {args.verdict}")
    print(f"  반증 조건 — {args.falsify}")
    print(f"  {CONF[args.confidence]}")
    return 0


def cmd_flip(d, args):
    name = args.flip
    prev = latest(d, name)
    if not prev:
        print(f"{name}에 기존 결론이 없다. --log로 먼저 기록한다.")
        return 1
    print(f"\n{'='*72}\n  {name} — 번복 검사\n{'='*72}")
    print(f"  기존  {prev['date']}  [{prev['confidence']}] {prev['verdict']}")
    print(f"        근거 {prev['basis']}")
    print(f"  사전 등록된 반증 조건:")
    print(f"        {prev['falsify']}")
    print(f"\n  번복 사유: {args.reason}")
    print(f"  새 결론  : {args.new}")

    print(f"\n▸ 판정")
    if args.new_fact:
        kind = "갱신"
        print(f"    ✅ **갱신** — 새 사실이 들어왔다: {args.new_fact}")
        print(f"       사전 조건에 걸렸으므로 번복이 정당하다.")
    else:
        kind = "표류"
        print(f"    ⛔ **표류** — 새 사실 없이 방법만 바뀌었다.")
        print(f"       (새 사실이 있으면 --new-fact 로 명시한다)")
        print(f"\n    이건 새 판단이 아니라 **첫 판단이 덜 검증됐다는 증거**다.")
        print(f"    출고 전에 다음을 해야 했다:")
        print(f"      · 같은 질문에 방법을 둘 이상 돌려서 방향이 같은지 확인")
        print(f"      · 갈리면 결론을 내지 않고 '갈린다'를 결론으로 낸다")
        print(f"\n    **표류로 기록하고, 사용자에게 표류였다고 말한다.**")
        print(f"    조용히 고치면 신뢰가 더 깎인다.")

    rec = dict(name=name, date=args.date or date.today().isoformat(),
               verdict=args.new, confidence=args.confidence or prev["confidence"],
               basis=args.reason, falsify=args.falsify or prev["falsify"],
               kind=kind, flip_reason=args.reason)
    if args.new_fact:
        rec["new_fact"] = args.new_fact
    d["decisions"].append(rec)
    save(d)
    return 0


def cmd_audit(d):
    rows = d["decisions"]
    flips = [x for x in rows if x.get("kind") in ("표류", "갱신")]
    drift = [x for x in flips if x["kind"] == "표류"]
    print(f"\n{'='*72}\n  번복 감사\n{'='*72}")
    print(f"  전체 결론 {len(rows)}건   번복 {len(flips)}건   그중 표류 {len(drift)}건")
    if flips:
        print(f"  표류율 **{len(drift)/len(flips)*100:.0f}%**")
    by = {}
    for x in drift:
        by[x["name"]] = by.get(x["name"], 0) + 1
    if by:
        print(f"\n▸ 표류가 잦은 종목 — 여기는 결론을 내기 전에 더 검증한다")
        for n, c in sorted(by.items(), key=lambda kv: -kv[1]):
            print(f"    {n:<10} {c}회")
    low = [x for x in rows if x["confidence"] == "하"]
    if low:
        print(f"\n▸ 신뢰등급 '하'인 결론 {len(low)}건 — **결론이 아니라 관찰로 쓴다**")
        for x in low:
            print(f"    {x['name']:<10} {x['verdict']}")
    print(f"\n  표류율이 높으면 문제는 판단력이 아니라 **출고 기준**이다.")
    print(f"  방법 하나만 돌리고 결론을 내지 않는다.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", nargs="?", const="", metavar="종목")
    ap.add_argument("--log", metavar="종목", dest="name")
    ap.add_argument("--flip", metavar="종목")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--verdict")
    ap.add_argument("--new", help="--flip의 새 결론")
    ap.add_argument("--reason", help="--flip의 사유")
    ap.add_argument("--new-fact", help="새로 들어온 사실. 없으면 표류로 판정된다")
    ap.add_argument("--confidence", choices=list(CONF))
    ap.add_argument("--basis")
    ap.add_argument("--falsify", help="이 결론이 틀렸다고 인정할 관찰 가능한 조건")
    ap.add_argument("--date")
    args = ap.parse_args()
    d = load()

    if args.audit:
        return cmd_audit(d)
    if args.flip:
        if not (args.reason and args.new):
            ap.error("--flip에는 --reason과 --new가 필요하다")
        return cmd_flip(d, args)
    if args.name:
        for k in ("verdict", "confidence", "basis", "falsify"):
            if not getattr(args, k):
                ap.error(f"--log에는 --{k}가 필요하다. "
                         f"특히 --falsify 없이는 결론을 기록하지 않는다")
        return cmd_log(d, args)
    return cmd_list(d, args.list or None)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:      # `| head` 로 잘렸을 때 역추적을 뱉지 않는다
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
