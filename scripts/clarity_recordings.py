#!/usr/bin/env python3
# style-guard:off (코드 주석)
"""
== 운영 맥락 ==
쓰는 곳: 5단계(선택) 지시 C. 매일 보고의 주요 방문에 재생 링크를 짝짓고,
        「고치기」가 무엇을 바꿀지 모를 때 녹화를 읽어 제안을 만든다. 참고 구현이다.
        사이트가 TypeScript 면 이 파일을 읽고 같은 약속을 그 언어로 옮긴다.
입력:  Clarity 녹화 목록 창구 POST https://clarity.microsoft.com/mcp/recordings/sample
       (Clarity 설정 > 데이터 내보내기의 API 토큰. 보고에 쓰는 CLARITY_API_TOKEN 그대로 통한다.
        명령 인자에 절대 넣지 않는다. 환경변수나 권한 600 파일에서만 읽는다)
출력:  방문마다 재생 링크·시각·머문 시간·쪽수·클릭/죽은 클릭/분노 클릭 한 줄
외부 의존: 위 창구뿐(표준 라이브러리만). 응답이 JSON 목록이 아니면 실패로 본다(200 + 로그인 화면 함정).
한도: 문서에 없음. 한 번에 count 건까지 받으므로 보고 1번, 과제 1건마다 1~2번만 부른다.
확인된 사실(2026-09-21 실측):
  - filters.date(start, end, 밀리초까지 ISO)가 없으면 500.
  - timestamp 는 'YYYY-MM-DD HH:MM:SS' UTC.
  - 오류 문구는 안 준다(javascriptErrors 는 걸러 주기만). 문구는 사이트가 직접 기록해야 한다.
  - 재생 링크는 Clarity 에 로그인한 브라우저에서만 열린다. 비로그인은 로그인 화면.
  - 시작 시각 ±180초 + 첫 화면 경로로 짝지으면 100건 중 87건이 맞았다.
의도적 미구현:
  - 재생 화면 캡처: 로그인이 필요해 자동으로 못 본다
마지막 점검: 2026-09-22

손으로 확인:
  CLARITY_API_TOKEN 을 환경변수로 둔 뒤  python3 clarity_recordings.py [건수]
  또는  python3 clarity_recordings.py [건수] --token-file ~/.config/clarity-connect/clarity_<site>.tok
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

RECORDINGS_URL = "https://clarity.microsoft.com/mcp/recordings/sample"
KST = dt.timezone(dt.timedelta(hours=9))
SORT_RECENT = 0  # 최근 시작 순
EVENT_LABEL = {"Click": "클릭", "Dead click": "죽은 클릭", "Rage clicks": "분노 클릭", "Entered Text": "입력", "Selected Text": "글자 선택", "Quickback": "빠른 뒤로가기"}


def _iso(d):
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch(token, start, end, count=30, device=None, campaigns=None, entry_paths=None, js_errors=None, sort=SORT_RECENT, timeout=45):
    """녹화 목록을 받는다. start·end 는 시간대가 있는 datetime. entry_paths 는 진입 주소 경로 목록(예: ["/ebooks/abc"]).
    실패하면 RuntimeError(원인 한 줄)."""
    # 설정 파일 줄 끝의 \r·공백이 붙어 오면 머리글 검사가 열쇠 값을 통째로 오류 문구에 찍는다(2026-09-22 실제 발생)
    token = (token or "").strip()
    if not token:
        raise RuntimeError("CLARITY_API_TOKEN 이 없습니다")
    filters = {"date": {"start": _iso(start), "end": _iso(end)}}
    if device:
        # 창구 값: Mobile / Tablet / PC / Email / Other. mobile/desktop 도 받는다
        filters["deviceType"] = [{"mobile": "Mobile", "desktop": "PC"}.get(str(device).lower(), device)]
    if campaigns:
        filters["campaign"] = list(campaigns)[:5]
    if entry_paths:
        # 창구의 주소 조건은 부분 일치(문자열 포함)로 동작한다
        filters["entryUrls"] = [{"url": p, "operator": "contains"} for p in list(entry_paths)[:5]]
    if js_errors:
        filters["javascriptErrors"] = list(js_errors)[:5]
    body = {"sortBy": sort, "start": _iso(start), "end": _iso(end), "filters": filters, "count": max(1, min(int(count), 100))}
    req = urllib.request.Request(
        RECORDINGS_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "clarity-connect/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Clarity 녹화 창구 HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Clarity 녹화 창구 연결 실패: {e}") from e
    except ValueError:
        # 머리글 값 오류는 열쇠 원문을 담고 있다. 원문 없이 다시 던진다
        raise RuntimeError("Clarity 녹화 창구 요청을 만들지 못했습니다(열쇠에 쓸 수 없는 글자가 섞임)") from None
    if "json" not in ctype:
        raise RuntimeError(f"Clarity 녹화 창구 응답이 JSON 이 아닙니다: {raw[:80]!r}")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise RuntimeError(f"Clarity 녹화 창구 응답이 목록이 아닙니다: {raw[:120]!r}")
    return data


def _duration_sec(text):
    """'09 minutes and 05 seconds' / '48 seconds' → 초"""
    m = re.findall(r"(\d+)\s*(hour|minute|second)", text or "")
    unit = {"hour": 3600, "minute": 60, "second": 1}
    return sum(int(n) * unit[u] for n, u in m)


def _path_of(url):
    try:
        return urlsplit(url).path or "/"
    except Exception:  # noqa: BLE001
        return url


def _started_at(rec):
    try:
        return dt.datetime.strptime(rec.get("timestamp", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def events_line(rec, limit=6):
    """녹화 한 건의 사건을 사람 말 한 줄로. 예: '죽은 클릭 2, 클릭 「목차 전체 보기」(0:43), 2쪽'"""
    counts = {}
    named = []
    for pg in rec.get("timeline") or []:
        for e in pg.get("timelineEvents") or []:
            kind = EVENT_LABEL.get(e.get("eventtype"), e.get("eventtype") or "사건")
            if e.get("eventtype") == "Click" and e.get("text"):
                if len(named) < limit:
                    named.append(f"클릭 「{str(e['text']).strip()[:30]}」({e.get('start', '')})")
            else:
                counts[kind] = counts.get(kind, 0) + 1
    parts = [f"{k} {v}" for k, v in counts.items()] + named
    pages = rec.get("pagesCount") or len(rec.get("timeline") or [])
    if pages and pages > 1:
        parts.append(f"{pages}쪽")
    return ", ".join(parts) if parts else "클릭 없음"


def summarize(rec, device="", errors=""):
    """제안 근거(proposal_basis) 한 항목. device·errors 는 사이트 자체 기록에서 짝지어 넣는다."""
    started = _started_at(rec)
    if started:
        k = started.astimezone(KST)
        time_label = f"{k.month}/{k.day} {k:%H:%M}"
    else:
        time_label = rec.get("timestamp") or ""
    return {
        "link": str(rec.get("link") or "")[:400],
        "time": time_label[:40],
        "device": (device or "")[:40],
        "durationSec": _duration_sec(rec.get("totalDuration")),
        "pages": int(rec.get("pagesCount") or 0),
        "events": events_line(rec)[:600],
        "errors": (errors or "")[:600],
    }


def match_sessions(recs, sessions, tolerance_sec=180):
    """사이트 자체 방문 기록과 Clarity 녹화를 짝짓는다 → {sessionId: 녹화}.
    sessions 항목 모양: {"sessionId", "startedAt"(ISO), "pages":[{"path"}...]}.
    기준: 시작 시각 차이 ≤ tolerance, 첫 화면 경로 같음(둘 다 있으면). 가장 가까운 것 하나, 한 녹화는 한 방문에만."""
    used = set()
    out = {}
    cands = []
    for i, rec in enumerate(recs):
        st = _started_at(rec)
        if not st:
            continue
        tl = rec.get("timeline") or []
        first_path = _path_of(tl[0].get("url", "")) if tl else None
        cands.append((i, rec, st, first_path))
    for s in sessions:
        try:
            s_start = dt.datetime.fromisoformat(str(s.get("startedAt", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        s_first = (s.get("pages") or [{}])[0].get("path")
        best = None
        for i, rec, st, first_path in cands:
            if i in used:
                continue
            gap = abs((st - s_start).total_seconds())
            if gap > tolerance_sec:
                continue
            if s_first and first_path and s_first != first_path:
                continue
            if best is None or gap < best[0]:
                best = (gap, i, rec)
        if best:
            used.add(best[1])
            out[s["sessionId"]] = best[2]
    return out


if __name__ == "__main__":
    import argparse
    import os

    ap = argparse.ArgumentParser(description="최근 24시간 녹화 몇 건을 받아 한 줄씩 보여 준다")
    ap.add_argument("count", nargs="?", type=int, default=3)
    ap.add_argument("--token-file", help="토큰이 든 파일(권한 600). 없으면 환경변수 CLARITY_API_TOKEN")
    a = ap.parse_args()
    if a.token_file:
        with open(os.path.expanduser(a.token_file), encoding="utf-8-sig") as f:
            tok = f.read().strip()
    else:
        tok = os.environ.get("CLARITY_API_TOKEN", "").strip()
    end = dt.datetime.now(dt.timezone.utc)
    for r in fetch(tok, end - dt.timedelta(days=1), end, count=a.count):
        print(json.dumps(summarize(r), ensure_ascii=False))
