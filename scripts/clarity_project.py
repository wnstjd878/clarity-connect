#!/usr/bin/env python3
# style-guard:off (화면 조작 도구)
"""
== 운영 맥락 ==
실행 시점: clarity-connect 1단계. 클라리티에 로그인할 크롬이 있는 컴퓨터에서 사람이 돌린다(Windows·Mac)
  python clarity_project.py launch                       전용 크롬(원격 조작 포트 9333)을 띄운다
  python clarity_project.py check                        로그인 상태와 프로젝트 목록(이름·ID)
  python clarity_project.py create --name 이름 --url 주소 --industry "경력 및 교육" [--dry-run]
  python clarity_project.py token --project <ID> --site <이름> [--out 파일] [--verify]
준비: pip install playwright  (크롬은 설치된 것을 쓴다)
입력: 로그인된 크롬 화면. 로그인 자체는 사람이 한다(자동 입력 안 함)
출력: create → 프로젝트 ID 한 줄 / token → ~/.config/clarity-connect/clarity_<site>.tok (권한 600)
외부 의존: clarity.microsoft.com 화면, 확인 조회 1회(내보내기 창구 하루 10회 한도 중 하나)
의도적 미구현:
  - 로그인 자동 입력. 마이크로소프트 계정 보호에 걸리면 사람이 풀어야 한다
  - 마스킹 설정 바꾸기. 화면 모양이 자주 바뀌어 사람이 설정에서 엄격(Strict)으로 한 번 고른다.
    사이트 코드도 body 전체를 가리므로 두 겹이 된다
  - 열쇠를 화면·명령 인자에 남기기. 클립보드에서 읽어 권한 600 파일에만 쓰고, 길이·지문 앞 8자만 찍는다
마지막 점검: 2026-09-15

실제로 됐던 조작(운영 사이트 두 곳에서 프로젝트를 만들고 열쇠를 받을 때):
  - 새 프로젝트 창의 입력란은 id 가 매번 바뀐다. 자리표시 글(Contoso …)로 찾는다
  - 업계는 목록 상자를 열고 [role=option] 글자로 고른다. 제출 단추는 "새 프로젝트 추가"
  - 열쇠는 창 DOM 에 안 보인다. "토큰 복사" 단추 + navigator.clipboard.readText 로만 잡힌다
  - 화면 글자는 한국어 설정 기준이다. 영어 화면이면 괄호 속 영어 이름으로도 찾는다
"""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

CDP = "http://127.0.0.1:9333"
BASE = "https://clarity.microsoft.com"


def fp(v: str) -> str:
    return f"길이 {len(v)} · 지문 {hashlib.sha256(v.encode()).hexdigest()[:8]}"


def cdp_up() -> bool:
    try:
        with urllib.request.urlopen(CDP + "/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def chrome_path():
    if platform.system() == "Windows":
        cands = [os.path.join(os.environ.get(k, ""), "Google/Chrome/Application/chrome.exe")
                 for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    elif platform.system() == "Darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        cands = ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
    return next((p for p in cands if p and os.path.exists(p)), None)


def launch():
    if cdp_up():
        print("이미 떠 있습니다(9333).")
        return
    profile = str(pathlib.Path.home() / ".clarity-connect-chrome")
    chrome = chrome_path()
    if not chrome:
        sys.exit("크롬을 못 찾았습니다.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0
    subprocess.Popen([chrome, "--remote-debugging-port=9333", f"--user-data-dir={profile}", BASE + "/projects"],
                     creationflags=flags)
    for _ in range(20):
        if cdp_up():
            print("띄웠습니다. 로그인이 안 되어 있으면 그 창에서 사람이 로그인하세요(이 프로필에 남습니다).")
            return
        time.sleep(1)
    sys.exit("크롬은 띄웠지만 9333 이 20초 안에 안 열렸습니다.")


def page_of(p):
    if not cdp_up():
        sys.exit("9333 크롬이 없습니다. 먼저  python clarity_project.py launch")
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "clarity.microsoft.com" in x.url), None) or ctx.new_page()
    pg.bring_to_front()
    return b, ctx, pg


def logged_in(pg) -> bool:
    return "clarity.microsoft.com" in pg.url and "login" not in pg.url.lower()


def list_projects(pg):
    pg.goto(BASE + "/projects", wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    if not logged_in(pg):
        return None
    return pg.evaluate("""() => {
      const seen = new Map();
      for (const a of document.querySelectorAll('a[href*="/projects/view/"]')) {
        const m = a.getAttribute('href').match(/projects\\/view\\/([a-z0-9]+)/i);
        if (!m) continue;
        const card = a.closest('[role=listitem], li, [class*=card], [class*=Card]') || a;
        const text = (card.innerText || a.innerText || '').trim().split('\\n').filter(Boolean);
        if (!seen.has(m[1])) seen.set(m[1], text.slice(0, 3));
      }
      return [...seen].map(([id, t]) => ({ id, text: t }));
    }""")


def cmd_check(a):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        _, _, pg = page_of(p)
        items = list_projects(pg)
        if items is None:
            print("로그인이 풀려 있습니다. 크롬 창에서 사람이 로그인한 뒤 다시 check.")
            sys.exit(2)
        print(f"로그인 됨. 프로젝트 {len(items)}개")
        for it in items:
            print(f"  {it['id']}  {' / '.join(it['text'])}")


def find_existing(items, name, url):
    host = re.sub(r"^https?://", "", url).strip("/").lower()
    for it in items:
        joined = " ".join(it["text"]).lower()
        if (host and host in joined) or (name and name.lower() in joined):
            return it["id"]
    return None


def cmd_create(a):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        _, _, pg = page_of(p)
        items = list_projects(pg)
        if items is None:
            sys.exit("로그인이 풀려 있습니다.")
        found = find_existing(items, a.name, a.url)
        if found:
            print(f"이미 있습니다. 새로 안 만듭니다.\nPROJECT_ID={found}")
            return
        btn = pg.locator("button:has-text('새 프로젝트'), button:has-text('New project')").first
        if not btn.count():
            sys.exit("「새 프로젝트」 단추를 못 찾았습니다. 화면이 바뀌었을 수 있습니다.")
        btn.click()
        pg.wait_for_timeout(2500)
        filled = {"이름": False, "주소": False}
        for el in pg.query_selector_all("[role=dialog] input, input"):
            if not el.is_visible():
                continue
            key = " ".join(filter(None, [el.get_attribute("placeholder"), el.get_attribute("aria-label"),
                                         el.get_attribute("name")])).lower()
            if not filled["주소"] and any(k in key for k in ("contoso.com", "url", "website", "웹사이트", "사이트")):
                el.fill(re.sub(r"^https?://", "", a.url).strip("/"))
                filled["주소"] = True
            elif not filled["이름"] and any(k in key for k in ("contoso", "name", "이름")):
                el.fill(a.name)
                filled["이름"] = True
        if not all(filled.values()):
            sys.exit(f"입력란을 다 못 찾았습니다: {filled}")
        combo = pg.locator("[role=dialog] [role=combobox], [role=combobox]").first
        if combo.count():
            combo.click()
            pg.wait_for_timeout(800)
            opt = pg.locator("[role=option]", has_text=a.industry)
            if not opt.count():
                names = [x.strip() for x in pg.locator("[role=option]").all_inner_texts()]
                sys.exit(f"업계 「{a.industry}」 가 목록에 없습니다. 있는 것: {', '.join(names)}")
            opt.first.click()
            pg.wait_for_timeout(500)
        shot = str(pathlib.Path.cwd() / f"clarity_create_{re.sub(r'[^0-9A-Za-z가-힣_-]', '_', a.name)}.png")
        pg.screenshot(path=shot)
        if a.dry_run:
            print(f"(시험) 제출 전에서 멈췄습니다. 화면: {shot}")
            return
        pg.get_by_role("button", name=re.compile("새 프로젝트 추가|Add new project")).first.click()
        for _ in range(20):
            pg.wait_for_timeout(1000)
            m = re.search(r"/projects/view/([a-z0-9]+)", pg.url)
            if m:
                print(f"만들었습니다.\nPROJECT_ID={m.group(1)}")
                return
        found = find_existing(list_projects(pg) or [], a.name, a.url)
        if found:
            print(f"만들었습니다(목록에서 확인).\nPROJECT_ID={found}")
            return
        sys.exit("제출은 눌렀는데 새 프로젝트 ID 를 못 찾았습니다. 크롬 화면을 확인하세요.")


def save_local(path: pathlib.Path, token: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"저장: {path}")


def verify_local(path: pathlib.Path):
    token = path.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(
        "https://www.clarity.ms/export-data/api/v1/project-live-insights?numOfDays=1&dimension1=Device",
        headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("확인 조회", r.status)
    except urllib.error.HTTPError as e:
        print("확인 조회 실패", e.code)


def cmd_token(a):
    from playwright.sync_api import sync_playwright
    out = pathlib.Path(a.out).expanduser() if a.out else pathlib.Path.home() / ".config/clarity-connect" / f"clarity_{a.site}.tok"
    with sync_playwright() as p:
        _, ctx, pg = page_of(p)
        pg.goto(f"{BASE}/projects/view/{a.project}/settings", wait_until="domcontentloaded")
        pg.wait_for_timeout(3500)
        if not logged_in(pg):
            sys.exit("로그인이 풀려 있습니다.")
        tab = pg.get_by_text(re.compile("데이터 내보내기|Data export")).first
        if tab.count():
            tab.click()
            pg.wait_for_timeout(1500)
        pg.get_by_role("button", name=re.compile("새 API 토큰 생성|Generate new API token")).first.click()
        pg.wait_for_timeout(1500)
        box = pg.locator("[role=dialog] input").first
        if not box.count():
            sys.exit("토큰 이름 입력란을 못 찾았습니다.")
        box.fill(a.token_name)
        pg.get_by_role("button", name=re.compile("^추가$|^Add$|생성|Generate")).first.click()
        pg.wait_for_timeout(3000)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
        copy = pg.get_by_role("button", name=re.compile("토큰 복사|Copy token")).first
        if not copy.count():
            sys.exit("「토큰 복사」 단추를 못 찾았습니다. 열쇠는 이 단추로만 잡힌다(창 DOM 에 안 보임).")
        copy.click()
        pg.wait_for_timeout(800)
        token = (pg.evaluate("navigator.clipboard.readText()") or "").strip()
        pg.evaluate("navigator.clipboard.writeText('')")  # 클립보드에 열쇠가 남지 않게
        if not (200 <= len(token) <= 4000) or " " in token:
            sys.exit(f"클립보드에서 열쇠 모양을 못 읽었습니다({fp(token) if token else '비어 있음'}).")
        print("열쇠 읽음:", fp(token))
        save_local(out, token)
        del token
    if a.verify:
        verify_local(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("launch")
    sub.add_parser("check")
    c = sub.add_parser("create")
    c.add_argument("--name", required=True)
    c.add_argument("--url", required=True)
    c.add_argument("--industry", required=True, help="클라리티 업계 목록 글자 그대로. 예: 경력 및 교육, B2B 서비스")
    c.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("token")
    t.add_argument("--project", required=True)
    t.add_argument("--site", required=True)
    t.add_argument("--out", default="", help="열쇠 파일 경로. 기본 ~/.config/clarity-connect/clarity_<site>.tok")
    t.add_argument("--token-name", default="clarity-connect")
    t.add_argument("--verify", action="store_true", help="조회 1회로 확인(하루 10회 한도 중 하나)")
    a = ap.parse_args()
    {"launch": lambda: launch(), "check": lambda: cmd_check(a), "create": lambda: cmd_create(a),
     "token": lambda: cmd_token(a)}[a.cmd]()


if __name__ == "__main__":
    main()
