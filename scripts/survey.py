#!/usr/bin/env python3
# style-guard:off (조사 도구. 판정 문구가 짧은 목록이다)
"""
== 운영 맥락 ==
실행 시점: 새 사이트에 클라리티를 붙이기 전 (clarity-connect 0단계)
  python3 .claude/skills/clarity-connect/scripts/survey.py <저장소 경로> --site <이름> [--mine 내계정,내조직]
입력: 저장소 경로. 읽기만 한다
출력: ./clarity-connect-out/<site>/survey.json + 화면 요약(판정 / 사람이 정할 것)
외부 의존: 없음 (git 명령만)
의도적 미구현: 코드 수정. 판정만 한다. 고치는 것은 scaffold 단계에서 사람 확인 뒤
마지막 점검: 2026-09-15

왜 있나: 운영 사이트 세 곳에 손으로 붙이며 매번 같은 것을 뒤늦게 찾았다.
  관리자 화면이 녹화됐다, 주소의 id 가 곧 열쇠인 결과 링크가 있었다, 방침에 클라리티가 빠졌다,
  남의 저장소를 자동으로 올리는 폴더에 뒀다, 배포가 git push 로 안 됐다. 붙이기 전에 이것부터 판정한다.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess

SKIP_DIRS = {"node_modules", ".next", ".git", "build", "dist", ".turbo", ".vercel", ".wrangler",
             "coverage", "playwright-report", "test-results", ".cache", "public", "out"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
MAX_BYTES = 800_000

AUTH_HINT = re.compile(
    r"cookies\(\)|getServerSession|auth\(\)|currentUser|requireUser|requireAdmin|verifyAdmin|"
    r"redirect\(\s*[\"'`][^\"'`]*login|getUser\(|session\s*=|withAuth|isAdmin")
LINK_IS_KEY_HINT = re.compile(r"서명|로그인\s*없이|링크를\s*아는|토큰으로\s*연다|share|공유\s*링크")
ADMIN_NAMES = {"admin", "ops", "console", "dashboard", "manage", "backoffice", "admin-login"}


def walk(root: pathlib.Path):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            yield pathlib.Path(dp) / fn


def read(p: pathlib.Path) -> str:
    try:
        if p.stat().st_size > MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rel(root, p):
    return str(pathlib.Path(p).relative_to(root))


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def find_apps(root):
    """package.json 이 있는 앱 폴더를 찾아 스택을 가른다."""
    apps = []
    for pj in walk(root):
        if pj.name != "package.json":
            continue
        try:
            data = json.loads(read(pj) or "{}")
        except json.JSONDecodeError:
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        d = pj.parent
        stack = None
        if "next" in deps:
            if any((d / "app" / f).exists() for f in ("layout.tsx", "layout.jsx", "layout.js")):
                stack = "next-app"
            elif (d / "pages").exists():
                stack = "next-pages"
            else:
                stack = "next-?"
        elif "@react-router/dev" in deps or ("react-router" in deps and (d / "app" / "root.tsx").exists()):
            stack = "react-router"
        elif "@remix-run/react" in deps:
            stack = "remix"
        if not stack:
            continue
        db = [k for k in ("@supabase/supabase-js", "@neondatabase/serverless", "drizzle-orm", "prisma", "@prisma/client") if k in deps]
        apps.append({
            "path": rel(root, d) or ".",
            "name": data.get("name", ""),
            "stack": stack,
            "next": deps.get("next"),
            "react": deps.get("react"),
            "db": db,
            "admin_app": any(n in rel(root, d).lower() for n in ("admin", "ops", "console")),
        })
    return apps


def scan_app(root, app):
    base = root / app["path"]
    out = {"clarity_present": [], "meta_pixel": [], "csp": [], "privacy": [], "admin_routes": [],
           "link_is_key_candidates": [], "visit_tracking": [], "css_archive": []}
    appdir = base / "app"
    for p in walk(base):
        r = rel(root, p)
        text = None
        if p.suffix in CODE_EXT or p.name.startswith(("next.config", "middleware", "vercel.json")):
            text = read(p)
            if "clarity.ms" in text or "window.clarity" in text or 'clarity("' in text:
                out["clarity_present"].append(r)
            if "fbevents.js" in text:
                # 주석에 "next/script 가 아니라" 같은 글이 있어도 속지 않게 가져오기 줄로만 가른다
                uses_next_script = re.search(r"""from\s+["']next/script["']""", text)
                style = "next-script" if uses_next_script else ("inline" if "dangerouslySetInnerHTML" in text else "기타")
                out["meta_pixel"].append({"file": r, "style": style})
            if "Content-Security-Policy" in text:
                out["csp"].append(r)
            if "sessionStorage" in text and re.search(r"/api/(visit|track)|방문키|visitor|sid", text):
                out["visit_tracking"].append(r)
            if "archive-css" in p.name or "css-archive" in text:
                out["css_archive"].append(r)
        low = r.lower()
        if any(k in low for k in ("privacy", "개인정보", "방침")) and p.suffix in CODE_EXT:
            out["privacy"].append(r)

    if appdir.exists() and app["stack"].startswith("next"):
        for d in appdir.iterdir():
            if d.is_dir() and d.name.strip("()").lower() in ADMIN_NAMES:
                out["admin_routes"].append("/" + d.name.strip("()"))
        for dp, dns, fns in os.walk(appdir):
            dns[:] = [x for x in dns if x not in SKIP_DIRS]
            dpath = pathlib.Path(dp)
            parts = [x.lower() for x in dpath.relative_to(appdir).parts]
            if not parts or "api" in parts or any(x.strip("()") in ADMIN_NAMES for x in parts):
                continue
            if not re.fullmatch(r"\[.+\]", dpath.name):
                continue
            page = next((dpath / f for f in ("page.tsx", "page.jsx", "page.js") if (dpath / f).exists()), None)
            if not page:
                continue
            body = read(page)
            route = "/" + "/".join(pathlib.Path(dp).relative_to(appdir).parts)
            out["link_is_key_candidates"].append({
                "route": route,
                "auth_seen": bool(AUTH_HINT.search(body)),
                "comment_says_link_is_key": bool(LINK_IS_KEY_HINT.search(body)),
            })
    elif app["stack"] == "react-router":
        routes = base / "app" / "routes"
        if routes.exists():
            for f in routes.iterdir():
                n = f.stem.lower()
                if any(n.startswith(a) for a in ADMIN_NAMES):
                    out["admin_routes"].append(f.name)
                if "$" in f.stem and not n.startswith(("api", "admin")):
                    out["link_is_key_candidates"].append({"route": f.name, "auth_seen": bool(AUTH_HINT.search(read(f))),
                                                          "comment_says_link_is_key": bool(LINK_IS_KEY_HINT.search(read(f)))})
    return out


def deploy_info(root):
    found = []
    for name in ("vercel.json", "wrangler.json", "wrangler.jsonc", "wrangler.toml", "fly.toml", "netlify.toml"):
        for p in walk(root):
            if p.name == name:
                found.append(rel(root, p))
    manual = []
    for doc in ("CLAUDE.md", "AGENTS.md", "README.md"):
        t = read(root / doc)
        m = re.search(r"(npx\s+vercel[^\n`]*--prod[^\n`]*)", t)
        if m:
            manual.append({"doc": doc, "command": m.group(1).strip()})
        if re.search(r"git push`?\s*로\s*안|push`?\s*로\s*안\s*걸린다", t):
            manual.append({"doc": doc, "note": "git push 로 배포되지 않는다고 적혀 있음"})
    return {"files": sorted(set(found)), "doc_hints": manual}


def ownership(root, mine):
    url = git(root, "remote", "get-url", "origin")
    owner = ""
    m = re.search(r"github\.com[:/]([^/]+)/", url)
    if m:
        owner = m.group(1)
    # 내 계정·조직은 --mine 으로 받는다. 비워 두면 원격 주소가 없는 저장소만 내 것으로 본다
    is_mine = owner == "" or owner.lower() in mine
    return {"remote_owner": owner, "is_mine": is_mine, "branch": git(root, "branch", "--show-current"),
            "dirty_files": len([x for x in git(root, "status", "--short").splitlines() if x.strip()])}


def verdict(site, apps, scans, dep, own):
    lines, human = [], []
    if not own["is_mine"]:
        lines.append(f"남의 저장소입니다(소유 {own['remote_owner']}). 올리기·배포 전에 확인받습니다.")
        human.append("자동으로 커밋·올리는 도구를 쓰고 있다면 이 저장소는 그 대상에서 빼세요. 그쪽 main 에 내 작업이 올라갑니다.")
    if own["dirty_files"]:
        human.append(f"커밋 안 된 변경이 {own['dirty_files']}개 있습니다. 다른 세션 작업일 수 있어 먼저 확인하세요.")
    if any(h.get("note") for h in dep["doc_hints"]):
        lines.append("배포가 git push 로 안 됩니다. 문서의 배포 명령을 따라야 합니다: "
                     + ", ".join(h["command"] for h in dep["doc_hints"] if h.get("command")) )
    for app, sc in zip(apps, scans):
        tag = f"[{app['path']}] {app['stack']}"
        if app["admin_app"]:
            lines.append(f"{tag}: 관리자 앱으로 보입니다. 클라리티를 싣지 않습니다.")
            continue
        if sc["clarity_present"]:
            lines.append(f"{tag}: 클라리티가 이미 있습니다 → {', '.join(sc['clarity_present'][:4])}")
        style = ", ".join(f"{m['file']}({m['style']})" for m in sc["meta_pixel"]) or "없음"
        lines.append(f"{tag}: 메타 픽셀 설치 모양 {style}. 같은 모양으로 넣습니다(React 19 화면 오류 #418 이 난 모양은 피함).")
        if sc["admin_routes"]:
            lines.append(f"{tag}: 끌 주소(관리자) {', '.join(sc['admin_routes'])}")
        keys = [c for c in sc["link_is_key_candidates"] if not c["auth_seen"]]
        if keys:
            human.append(f"{tag}: 로그인 확인이 안 보이는 id 주소 {', '.join(c['route'] for c in keys)}. "
                         "주소 자체가 열쇠인 링크면 클라리티를 꺼야 합니다(클라리티는 주소를 모은다). 맞는지 정하세요.")
        lines.append(f"{tag}: CSP {'있음 → 클라리티 주소를 더해야 함: ' + ', '.join(sc['csp']) if sc['csp'] else '없음'}")
        if sc["privacy"]:
            human.append(f"{tag}: 개인정보처리방침 파일 {', '.join(sc['privacy'][:3])}. 클라리티(Microsoft) 줄을 켤 때만 나오게 묶고, "
                         "방침 변경 공지 기간(보통 7일)을 정하세요.")
        else:
            human.append(f"{tag}: 개인정보처리방침 파일을 못 찾았습니다. 클라리티를 켜기 전에 방침이 어디 있는지 확인하세요.")
        lines.append(f"{tag}: 방문 기록 {'있음 → ' + ', '.join(sc['visit_tracking'][:3]) if sc['visit_tracking'] else '없음 → 방문키를 새로 만들어야 녹화와 이을 수 있음'}")
        if not sc["css_archive"]:
            human.append(f"{tag}: 배포마다 CSS 파일 이름이 바뀌면 옛 녹화가 스타일 없이 재생됩니다. 빌드 뒤 옛 CSS 를 남겨 두는 보관을 붙일지 정하세요.")
        lines.append(f"{tag}: 녹화 가림은 전체 기본 + 개인정보 없는 랜딩만 풀기로 합니다(화면마다 찾아 가리면 빠뜨림).")
    return lines, human


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--site", required=True)
    ap.add_argument("--mine", default="", help="내 GitHub 계정·조직 이름, 쉼표로. 이 소유자가 아니면 남의 저장소로 본다")
    ap.add_argument("--out", default="clarity-connect-out")
    a = ap.parse_args()
    root = pathlib.Path(a.repo).expanduser().resolve()
    if not (root / ".git").exists():
        raise SystemExit(f"git 저장소가 아닙니다: {root}")
    apps = find_apps(root)
    if not apps:
        raise SystemExit("화면 앱(package.json + next/react-router)을 못 찾았습니다.")
    scans = [scan_app(root, app) for app in apps]
    dep = deploy_info(root)
    own = ownership(root, {x.strip().lower() for x in a.mine.split(",") if x.strip()})
    lines, human = verdict(a.site, apps, scans, dep, own)
    result = {"site": a.site, "repo": str(root), "apps": [dict(app, **sc) for app, sc in zip(apps, scans)],
              "deploy": dep, "ownership": own, "verdict": lines, "human_decisions": human}
    od = pathlib.Path(a.out) / a.site
    od.mkdir(parents=True, exist_ok=True)
    (od / "survey.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"== {a.site} 조사 ({root})")
    print("앱:", ", ".join(f"{x['path']}({x['stack']})" for x in apps))
    print("\n[판정]")
    for x in lines:
        print(" -", x)
    print("\n[사람이 정할 것]")
    for x in human or ["없음"]:
        print(" -", x)
    print(f"\n저장: {od / 'survey.json'}")


if __name__ == "__main__":
    main()
