// style-guard:off (검증 도구)
/**
 * == 운영 맥락 ==
 * 실행 시점: clarity-connect 3단계. 클라리티 ID 를 넣고 만든 빌드본을 띄운 뒤 사람이 돌린다
 *   node .claude/skills/clarity-connect/scripts/probe.js <설정.json>
 *   (playwright 가 있는 폴더에서 NODE_PATH 로 불러도 된다)
 * 입력: 설정 파일(JSON). 예시는 scripts/probe.example.json
 * 출력: 화면마다 통과·실패와 이유, 전부 통과면 종료코드 0
 * 외부 의존: 없음. 클라리티 서버 요청과 운영 DB 쓰기 요청은 막는다(시험 값이 밖으로 새지 않게)
 * 의도적 미구현: 실서버 확인. 실서버는 쓰기를 막아도 로그인·주문 같은 흐름이 있어 사이트마다 따로 본다
 * 마지막 점검: 2026-09-15
 *
 * 무엇을 보나(세 사이트에서 터진 것들):
 *   - 켜야 할 화면에서 클라리티가 켜지고 클라리티로 요청이 나가려 하나
 *   - 끌 화면(관리자, 주소가 열쇠인 링크)에서 요청이 0 인가
 *   - identify 가 쌓이나(방문과 녹화가 이어지나)
 *   - 화면 맞춰 끼우기 오류(React #418 등)가 없나. dev 서버에서는 안 나서 빌드본으로만 본다
 *   - 가림: 지정한 요소의 가장 가까운 표시가 가림/풀림 중 기대한 것인가
 *   - 자동 조작 브라우저는 사이트가 내부 방문으로 보고 기록을 안 보낼 수 있어 webdriver 표시를 가린다
 */
const { chromium } = require("playwright");
const fs = require("node:fs");

const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const BASE = cfg.base.replace(/\/$/, "");
const HYDRATION = /Minified React error #(418|419|421|422|423|425)|Hydration|hydrat/i;

(async () => {
  const browser = await chromium.launch();
  let 실패 = 0;
  const 확인 = (이름, 됐나, 설명 = "") => {
    console.log(`${됐나 ? "통과" : "실패"}  ${이름}${설명 ? "  " + 설명 : ""}`);
    if (!됐나) 실패 += 1;
  };

  async function 열기(page경로, identify기다림 = false) {
    const ctx = await browser.newContext({ viewport: cfg.viewport || { width: 390, height: 844 } });
    await ctx.addInitScript(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));
    const 클라리티 = [];
    const 막은쓰기 = [];
    await ctx.route("**/*", (route) => {
      const req = route.request();
      const u = req.url();
      if (/clarity\.ms/.test(u)) { 클라리티.push(u); return route.abort(); }
      if (cfg.block_writes !== false && req.method() !== "GET" && req.method() !== "HEAD" && new URL(u).origin === new URL(BASE).origin) {
        막은쓰기.push(`${req.method()} ${new URL(u).pathname}`);
        return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
      }
      return route.continue();
    });
    const page = await ctx.newPage();
    const 오류 = [];
    page.on("console", (m) => { if (m.type() === "error") 오류.push(m.text()); });
    page.on("pageerror", (e) => 오류.push(String(e.message || e)));
    const res = await page.goto(BASE + page경로, { waitUntil: "networkidle" }).catch((e) => ({ status: () => 0, e }));
    await page.waitForTimeout(cfg.wait_ms || 1500);
    // identify 는 화면이 다 뜬 뒤(하이드레이션 뒤)에 붙는다. 컴퓨터가 바쁘면 고정 대기로는 모자라
    // 헛실패가 났다(부하 60 에서 1.8초로 부족). 붙을 때까지 기다리되 한도를 둔다.
    if (identify기다림) {
      await page.waitForFunction(
        () => window.clarity && window.clarity.q && Array.from(window.clarity.q).some((a) => a[0] === "identify"),
        null, { timeout: cfg.identify_timeout_ms || 10000 },
      ).catch(() => {});
    }
    const 상태 = await page.evaluate(() => ({
      켜짐: typeof window.clarity === "function",
      쌓임: window.clarity && window.clarity.q ? Array.from(window.clarity.q).map((a) => Array.from(a).map(String).join("|")) : [],
    })).catch(() => ({ 켜짐: false, 쌓임: [] }));
    return { ctx, page, 상태, 클라리티, 막은쓰기, 오류, 응답: res.status() };
  }

  async function 가림(page, selector) {
    return page.evaluate((s) => {
      const el = document.querySelector(s);
      if (!el) return "요소 없음";
      const n = el.closest("[data-clarity-mask],[data-clarity-unmask]");
      if (!n) return "표시 없음";
      return n.hasAttribute("data-clarity-unmask") ? "풀림" : "가림";
    }, selector);
  }

  for (const 경로 of cfg.on || []) {
    // expect_identify: true(켜는 화면 전부) / false(안 봄) / ["/"](그 화면만). 방문 기록이 없는 화면(방침 등)은 빼야 한다
    const idPages = cfg.expect_identify;
    const idHere = idPages === true || idPages === undefined || (Array.isArray(idPages) && idPages.includes(경로));
    const r = await 열기(경로, idHere);
    확인(`켜짐 ${경로}`, r.상태.켜짐 && r.클라리티.length > 0, `응답 ${r.응답}, 클라리티 요청 ${r.클라리티.length}`);
    if (idHere) {
      확인(`identify ${경로}`, r.상태.쌓임.some((s) => s.startsWith("identify|")), r.상태.쌓임.slice(0, 6).join(" / ") || "쌓인 것 없음");
    }
    const 끼우기 = r.오류.filter((t) => HYDRATION.test(t));
    확인(`화면 오류 없음 ${경로}`, 끼우기.length === 0, 끼우기.join(" | ").slice(0, 200));
    for (const m of (cfg.mask || []).filter((x) => x.page === 경로)) {
      const got = await 가림(r.page, m.selector);
      확인(`${m.expect} ${경로} ${m.selector}`, got === m.expect, `실제 ${got}`);
    }
    if (r.막은쓰기.length) console.log(`      막은 쓰기: ${[...new Set(r.막은쓰기)].join(", ")}`);
    await r.ctx.close();
  }

  for (const 경로 of cfg.off || []) {
    const r = await 열기(경로);
    확인(`꺼짐 ${경로}`, !r.상태.켜짐 && r.클라리티.length === 0, `응답 ${r.응답}, 클라리티 요청 ${r.클라리티.length}`);
    await r.ctx.close();
  }

  await browser.close();
  console.log(실패 ? `\n실패 ${실패}건` : "\n전부 통과");
  process.exit(실패 ? 1 : 0);
})();
