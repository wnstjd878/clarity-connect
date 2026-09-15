/**
 * 클라리티 대조 (clarity-connect 틀) — 설치 코드와 녹화 가림이 약속대로 도는지 본다.
 *
 * [바꿀 곳] 아래 설정 네 가지만 사이트에 맞게 고친다.
 * 사용법: 앱 폴더에서  npx tsx ../scripts/클라리티대조.ts  (경로는 사이트에 맞게)
 *
 * 잡는 것:
 *   1. ID 가 비면 아무것도 안 붙는다
 *   2. 끄는 주소(관리자·주소가 열쇠인 링크)에서는 스스로 멈춘다
 *   3. 켜는 화면에서는 클라리티를 부를 수 있고 스크립트 한 줄이 head 에 붙는다
 *   4. 꼬리표에 클릭 식별자·유입경로·랜딩주소가 섞이지 않는다
 *   5. 광고 주소에 전화번호·사업자번호·메일 꼴을 넣어 와도 꼬리표로 안 나간다
 *   6. 녹화 가림은 body 전체가 기본이고, 푸는 곳은 허용한 파일뿐이다
 *   7. (방침 파일이 있으면) 방침은 클라리티를 켤 때만 Microsoft 를 적는다
 *   8. 클라리티가 없는 브라우저에서 호출해도 오류가 안 난다
 * 붙인 뒤에는 규칙을 일부러 되돌려 빨간불이 뜨는지 한 번 본다(끄는 주소를 지우면 2번이 실패해야 한다).
 */
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import { 클라리티코드 } from "../app/클라리티";
import { 클라리티방문, 클라리티단계 } from "../app/클라리티호출";

// ── [바꿀 곳] ─────────────────────────────────────────────
const 앱 = fileURLToPath(new URL("../app/", import.meta.url));
const 켜는주소 = ["/", "/pricing", "/privacy"];
const 끄는주소 = ["/admin", "/admin/leads"];
const 푸는곳허용 = ["랜딩.tsx"]; // app 폴더 기준 상대 경로. 개인정보 없는 화면만
const 방침파일 = ""; // 예: "privacy/방침문서.tsx". 없으면 빈 글자
// ─────────────────────────────────────────────────────────

type 기록 = unknown[];

function 돌리기(id: string, 주소: string) {
  const 붙인것: string[] = [];
  const 머리 = { appendChild: (새것: { src: string }) => 붙인것.push(새것.src) };
  const window: Record<string, unknown> = {};
  window.window = window;
  window.document = { createElement: () => ({ async: 0, src: "" }), head: 머리, documentElement: 머리 };
  window.location = { pathname: 주소 };
  runInNewContext(클라리티코드(id), window);
  return { window, 붙인것 };
}

let 실패 = 0;
function 확인(이름: string, 됐나: boolean, 설명 = "") {
  console.log(`${됐나 ? "통과" : "실패"}  ${이름}${설명 ? "  " + 설명 : ""}`);
  if (!됐나) 실패 += 1;
}

function 꼬리표보기(유입: Record<string, string | null>) {
  const { window } = 돌리기("test123", 켜는주소[0]);
  (globalThis as Record<string, unknown>).window = window;
  클라리티방문("방문-1", 유입);
  클라리티단계("방문-1", "결과");
  const q = ((window.clarity as { q?: 기록[] }).q ?? []) as 기록[];
  delete (globalThis as Record<string, unknown>).window;
  return q.map((a) => Array.from(a as ArrayLike<unknown>).join("|"));
}

{
  const { window, 붙인것 } = 돌리기("", 켜는주소[0]);
  확인("ID 가 비면 아무것도 안 붙는다", 붙인것.length === 0 && window.clarity === undefined);
}
for (const 주소 of 끄는주소) {
  const { window, 붙인것 } = 돌리기("test123", 주소);
  확인(`끄는 주소에서 멈춘다 (${주소})`, 붙인것.length === 0 && window.clarity === undefined);
}
for (const 주소 of 켜는주소) {
  const { window, 붙인것 } = 돌리기("test123", 주소);
  확인(`켜는 화면에서 켜진다 (${주소})`,
    typeof window.clarity === "function" && 붙인것.length === 1 && 붙인것[0] === "https://www.clarity.ms/tag/test123",
    `붙인 주소 ${붙인것.join(",") || "없음"}`);
}
{
  const 줄 = 꼬리표보기({ 매체: "meta", 캠페인: "가을_9월", 소재: "a1", 클릭id: "fbclid-xyz", 유입경로: "https://m.facebook.com/", 랜딩주소: "/?utm_source=meta" });
  확인("identify 한다", 줄.includes("identify|방문-1"));
  확인("매체·캠페인·소재 꼬리표", 줄.includes("set|매체|meta") && 줄.includes("set|캠페인|가을_9월") && 줄.includes("set|소재|a1"));
  확인("단계는 event", 줄.includes("event|결과"));
  확인("클릭 식별자·유입경로·랜딩주소는 안 싣는다", !["fbclid-xyz", "m.facebook.com", "utm_source"].some((s) => 줄.some((n) => n.includes(s))), 줄.join(" / "));
  const 나쁜 = 꼬리표보기({ 매체: "a@b.com", 캠페인: "01012345678", 소재: "123-45-67890" });
  확인("번호·메일 꼴은 꼬리표로 안 나간다", !["01012345678", "123-45-67890", "a@b.com"].some((s) => 나쁜.some((n) => n.includes(s))), 나쁜.join(" / "));
  const 날짜 = 꼬리표보기({ 매체: "meta", 캠페인: "가을_20260915", 소재: null });
  확인("날짜가 든 캠페인 이름은 남는다", 날짜.includes("set|캠페인|가을_20260915"));
}
{
  const 레이아웃 = readFileSync(join(앱, "layout.tsx"), "utf-8");
  확인("body 가 기본으로 가려져 있다", /<body[^>]*data-clarity-mask="true"/.test(레이아웃));
  const 푸는곳: string[] = [];
  const 훑기 = (폴더: string) => {
    for (const 이름 of readdirSync(폴더)) {
      const 경로 = join(폴더, 이름);
      if (statSync(경로).isDirectory()) { 훑기(경로); continue; }
      if (/\.(tsx|ts|jsx|js)$/.test(이름) && /data-clarity-unmask/.test(readFileSync(경로, "utf-8"))) 푸는곳.push(경로.slice(앱.length));
    }
  };
  훑기(앱);
  const 벗어남 = 푸는곳.filter((f) => !푸는곳허용.includes(f));
  확인("가림을 푸는 곳은 허용한 파일뿐이다", 벗어남.length === 0, `푸는 곳: ${푸는곳.join(", ") || "없음"}`);
}
if (방침파일) {
  const 방침경로 = join(앱, 방침파일);
  const 방침 = existsSync(방침경로) ? readFileSync(방침경로, "utf-8") : "";
  확인("방침이 클라리티와 같은 환경변수를 본다", /클라리티ID/.test(방침));
  확인("방침의 Microsoft 줄은 클라리티를 켤 때만 나온다", /클라리티ID\s*\?[\s\S]{0,80}Microsoft/.test(방침));
}
{
  let 오류 = "";
  try { 클라리티단계("방문-2", "랜딩"); } catch (e) { 오류 = String(e); }
  확인("클라리티가 없는 브라우저에서도 오류가 안 난다", !오류, 오류);
}

console.log(실패 ? `\n실패 ${실패}건` : "\n전부 통과");
process.exit(실패 ? 1 : 0);
