#!/usr/bin/env python3
"""DART 전자공시 원문을 직접 읽는다. 의존성 없음(표준 라이브러리만).

**이 스킬에서 가장 자주 틀린 원인은 검색 요약을 사실로 쓴 것이다.**
1급 자료(공시 원문·IR) 4건은 전부 맞았고, 검색 요약 7건 중 확인된 4건은
전부 틀렸다. 넥스틸 소송 3,500억, KT 배당 6.69%, 하나금융 PBR 0.5,
8/17 미국 지수 3개 — 전부 검색 요약이었다.

DART는 그 문제를 구조적으로 없앤다. **금감원이 받은 원문 그대로**이고
회사가 제출한 숫자다. 여기서 나온 값은 1급이다.

    export DART_API_KEY=...            # opendart.fss.or.kr에서 발급(무료)
    python3 dart.py --setup            # 고유번호 목록을 받아 캐시한다(최초 1회)
    python3 dart.py --list 넥스틸 --since 20251101
    python3 dart.py --fin 화인베스틸 --year 2026 --quarter 2
    python3 dart.py --doc 20251127000123

**두 가지가 다 있어야 작동한다.**
  1. API 키 (환경변수 DART_API_KEY)
  2. opendart.fss.or.kr 도메인이 이 환경의 네트워크 정책에 허용돼 있을 것

2에서 막히면 `--check`가 그렇게 말해준다. 키가 있어도 도메인이 막혀 있으면
한 글자도 못 읽는다. 그 경우 사용자가 환경 설정에서 도메인을 열어야 한다.
"""
import argparse, json, os, sys, urllib.request, urllib.error, urllib.parse
import io, zipfile, xml.etree.ElementTree as ET

BASE = "https://opendart.fss.or.kr/api"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
CACHE = os.path.join(DATA, "dart-corpcodes.json")

# 보유·후보 종목. 종목명으로 부르면 종목코드를 찾아준다.
KNOWN = {
    "현대차": "005380", "현대차우": "005385", "네이버": "035420",
    "한국전력": "015760", "삼성전자": "005930", "동국산업": "005160",
    "넥스틸": "092790", "비츠로셀": "082920", "화인베스틸": "133820",
    "KT": "030200", "하나금융지주": "086790",
}

# 보고서 코드 — 분기를 이 코드로 바꿔 부른다
REPRT = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}

# 재무제표에서 실제로 쓰는 계정. 나머지는 노이즈라 안 뽑는다.
WANT = ["자산총계", "부채총계", "자본총계", "매출액", "영업이익",
        "당기순이익", "이익잉여금", "자본금"]


def _fail(msg, hint=""):
    print(f"\n⛔ {msg}", file=sys.stderr)
    if hint:
        print(f"   {hint}", file=sys.stderr)
    return 2


def _key():
    k = os.environ.get("DART_API_KEY", "").strip()
    if not k:
        _fail("DART_API_KEY가 없다.",
              "export DART_API_KEY=... 로 넣는다. 키는 opendart.fss.or.kr에서 무료 발급.")
        sys.exit(2)
    return k


def _get(path, **params):
    """DART 호출. 실패 원인을 **키 문제와 네트워크 문제로 갈라서** 알려준다."""
    params["crtfc_key"] = _key()
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(_fail(f"DART가 HTTP {e.code}를 돌려줬다.",
                               "키가 틀렸거나 호출 한도를 넘겼을 수 있다."))
    except urllib.error.URLError as e:
        raise SystemExit(_fail(
            f"opendart.fss.or.kr에 닿지 못했다 — {e.reason}",
            "이건 키 문제가 아니라 **네트워크 정책** 문제다. "
            "이 환경이 도메인을 막고 있으면 키가 있어도 못 읽는다. "
            "사용자가 환경 설정에서 opendart.fss.or.kr을 허용해야 한다."))


def _json(path, **params):
    d = json.loads(_get(path, **params).decode("utf-8"))
    st = d.get("status")
    if st == "013":
        print("  (조회 결과 없음)")
        return None
    if st != "000":
        raise SystemExit(_fail(f"DART status {st}: {d.get('message','')}"))
    return d


def check():
    """키와 도메인 중 무엇이 막혔는지 **갈라서** 확인한다."""
    print(f"\n{'='*70}\n  DART 접속 점검\n{'='*70}")
    k = os.environ.get("DART_API_KEY", "").strip()
    print(f"  1. API 키        {'있음 (' + k[:6] + '...)' if k else '⛔ 없음'}")
    try:
        urllib.request.urlopen(BASE + "/list.json", timeout=20)
        net = "열림"
    except urllib.error.HTTPError:
        net = "열림"           # 4xx는 서버가 답한 것 — 도메인은 뚫린 것이다
    except Exception as e:
        net = f"⛔ 막힘 ({e.__class__.__name__})"
    print(f"  2. 도메인 접속    {net}")
    ok = bool(k) and not net.startswith("⛔")
    print(f"\n  → {'✅ 쓸 수 있다' if ok else '아직 못 쓴다. 둘 다 있어야 한다'}")
    if not ok:
        print(f"\n  둘은 서로 다른 문제다. **키를 받아도 도메인이 막혀 있으면 못 읽는다.**")
    return 0 if ok else 1


def setup():
    """고유번호(corp_code) 목록을 받아 캐시한다. DART는 종목코드가 아니라
    자체 8자리 고유번호로 회사를 식별해서, 이 매핑이 없으면 아무것도 못 부른다."""
    print("고유번호 목록을 받는다 (약 20MB, 최초 1회)...")
    raw = _get("corpCode.xml")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])
    m = {}
    for e in ET.fromstring(xml).iter("list"):
        stock = (e.findtext("stock_code") or "").strip()
        if stock:                       # 상장사만 남긴다
            m[stock] = {"corp_code": e.findtext("corp_code").strip(),
                        "name": (e.findtext("corp_name") or "").strip()}
    os.makedirs(DATA, exist_ok=True)
    json.dump(m, open(CACHE, "w"), ensure_ascii=False)
    print(f"✅ 상장사 {len(m):,}개를 {CACHE}에 캐시했다.")
    for n, c in KNOWN.items():
        print(f"    {n:<8} {c}  →  {m.get(c, {}).get('corp_code', '⛔ 못 찾음')}")
    return 0


def _corp(name_or_code):
    if not os.path.exists(CACHE):
        raise SystemExit(_fail("고유번호 캐시가 없다.", "먼저 --setup을 실행한다."))
    m = json.load(open(CACHE))
    code = KNOWN.get(name_or_code, name_or_code)
    if code not in m:
        raise SystemExit(_fail(f"'{name_or_code}'의 종목코드를 못 찾았다.",
                               f"아는 이름: {', '.join(KNOWN)}"))
    return m[code]["corp_code"], m[code]["name"], code


def disclosures(name, since, until=None, limit=30):
    cc, nm, sc = _corp(name)
    p = {"corp_code": cc, "bgn_de": since, "page_count": min(limit, 100)}
    if until:
        p["end_de"] = until
    d = _json("list.json", **p)
    print(f"\n{'='*78}\n  {nm} ({sc}) — 공시 목록  {since}~{until or '오늘'}\n{'='*78}")
    if not d:
        return 0
    for it in d.get("list", [])[:limit]:
        print(f"  {it['rcept_dt']}  {it['report_nm']}")
        print(f"              접수번호 {it['rcept_no']}   제출 {it['flr_nm']}")
    print(f"\n  → 원문은 `--doc <접수번호>`로 읽는다. "
          f"**제목만 보고 판단하지 않는다** — 넥스틸 불성실공시를 제목만 보고\n"
          f"     관리종목 위험으로 오판했는데 원문엔 벌점 0점이었다.")
    return 0


def financials(name, year, quarter, consolidated=True):
    cc, nm, sc = _corp(name)
    d = _json("fnlttSinglAcntAll.json", corp_code=cc, bsns_year=str(year),
              reprt_code=REPRT[quarter], fs_div="CFS" if consolidated else "OFS")
    print(f"\n{'='*78}\n  {nm} ({sc}) — {year}년 {quarter}분기 "
          f"{'연결' if consolidated else '별도'} 재무제표\n{'='*78}")
    if not d:
        return 0
    rows = {}
    for it in d.get("list", []):
        nmv = it.get("account_nm", "").strip()
        if nmv in WANT and nmv not in rows:
            rows[nmv] = it
    print(f"    {'계정':<12}{'당기':>18}{'전기':>18}")
    for w in WANT:
        it = rows.get(w)
        if not it:
            continue
        cur = it.get("thstrm_amount", "").replace(",", "")
        pre = it.get("frmtrm_amount", "").replace(",", "")
        f = lambda v: f"{int(v)/1e8:>15,.0f}억" if v.lstrip("-").isdigit() else f"{'—':>16}"
        print(f"    {w:<12}{f(cur)}{f(pre)}")

    # 이 스킬에서 실제로 쓰는 파생값만 계산한다
    try:
        eq = int(rows["자본총계"]["thstrm_amount"].replace(",", ""))
        li = int(rows["부채총계"]["thstrm_amount"].replace(",", ""))
        print(f"\n  ▸ 부채비율 **{li/eq*100:,.1f}%**   자본총계 {eq/1e8:,.0f}억")
        if eq <= 0:
            print(f"  ⚠️ **자본잠식이다.** 소멸 위험 판정에 바로 들어간다.")
        cap = int(rows["자본금"]["thstrm_amount"].replace(",", ""))
        if eq < cap:
            print(f"  ⚠️ **부분 자본잠식** — 자본총계({eq/1e8:,.0f}억)가 "
                  f"자본금({cap/1e8:,.0f}억)보다 작다.")
    except (KeyError, ValueError, ZeroDivisionError):
        pass
    return 0


def document(rcept_no):
    """공시 원문. **제목이 아니라 표를 읽으려고** 있는 기능이다."""
    raw = _get("document.xml", rcept_no=rcept_no)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            raw = z.read(z.namelist()[0])
    except zipfile.BadZipFile:
        pass
    txt = raw.decode("utf-8", "replace")
    import re
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    print(txt.strip()[:20000])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="키·도메인을 갈라서 점검")
    ap.add_argument("--setup", action="store_true", help="고유번호 캐시 생성(최초 1회)")
    ap.add_argument("--list", metavar="종목", help="공시 목록")
    ap.add_argument("--since", default="20260101", help="시작일 YYYYMMDD")
    ap.add_argument("--until", help="종료일 YYYYMMDD")
    ap.add_argument("--fin", metavar="종목", help="재무제표")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--quarter", type=int, default=2, choices=[1, 2, 3, 4])
    ap.add_argument("--separate", action="store_true", help="연결 대신 별도")
    ap.add_argument("--doc", metavar="접수번호", help="공시 원문")
    a = ap.parse_args()

    if a.check:  return check()
    if a.setup:  return setup()
    if a.list:   return disclosures(a.list, a.since, a.until)
    if a.fin:    return financials(a.fin, a.year, a.quarter, not a.separate)
    if a.doc:    return document(a.doc)
    ap.print_help()
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
