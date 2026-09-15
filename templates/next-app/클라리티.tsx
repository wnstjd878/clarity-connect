/**
 * == 운영 맥락 ==  (clarity-connect 틀. 사이트에 맞게 [바꿀 곳] 을 고친 뒤 이 줄은 지운다)
 * 실행 시점: 모든 화면이 그려질 때 (뿌리 layout.tsx 가 body 안 첫 줄에 싣는다)
 * 입력: 환경변수 NEXT_PUBLIC_CLARITY_PROJECT_ID (클라리티 프로젝트 ID)
 * 출력: 브라우저에 클라리티 설치 코드. ID 가 비면 한 글자도 안 나간다
 * 외부 의존: www.clarity.ms (마이크로소프트 클라리티)
 * 의도적 미구현: 녹화하지 않는 주소가 있다. 설치 코드가 첫 줄에서 스스로 멈춘다(아래 끄는 주소).
 *   - 관리자 화면: 손님 이름·연락처가 보인다
 *   - 주소의 id 가 곧 열쇠인 링크(로그인 없이 결과를 여는 공유 링크): 클라리티는 주소를 모으므로
 *     글자를 가려도 켜지면 링크를 넘기는 것과 같다
 *   그 화면으로 가는 길이 첫 로드뿐인지(화면 안에서 옮겨 가는 코드가 없는지) 확인하고 적는다.
 * 받아들인 위험: 주소 뒤 광고 값(utm·fbclid)은 화면 주소와 함께 간다. 지우면 유입 측정과 메타 픽셀이
 *   깨지므로 안 지운다. 규칙은 "광고 링크 utm 에 개인정보를 적지 않는다".
 *
 * 설치 모양 (세 사이트에서 터진 것 피하기):
 *   - next/script 가 아니라 서버가 HTML 에 그대로 싣는 인라인 스크립트. 첫 화면에서 바로 나가는 방문도 잡는다
 *   - 태그는 문서의 첫 script 앞(insertBefore)이 아니라 head 끝에 붙인다. 첫 script 가 body 속 div 안
 *     (예: JSON-LD)이면 insertBefore 가 트리를 어긋나게 해 React #418 이 났다(실제 운영 사이트에서 겪음)
 *   - JSX 로 <script async src> 를 두지 않는다(head 로 끌어올려져 수집 0), head 인라인 stub 도 안 쓴다
 */
export const 클라리티ID = process.env.NEXT_PUBLIC_CLARITY_PROJECT_ID ?? "";

// [바꿀 곳] 끄는 주소. survey.py 의 「끌 주소」와 「사람이 정할 것」의 id 주소를 넣는다.
// 정규식 글자라 / 는 \\/ 로 적는다. 예: ^\\/(admin|r\\/|br\\/)
const 끄는주소 = "^\\/(admin)";

/** 브라우저에 실려 나가는 설치 코드. 검사(scripts/클라리티대조.ts)가 이 함수를 그대로 돌린다 */
export const 클라리티코드 = (id: string) => `(function(){
var id=${JSON.stringify(id)};
if(!id)return;
if(new RegExp(${JSON.stringify(끄는주소)}).test(location.pathname))return;
(function(c,l,a,r,i,t){
c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
(l.head||l.documentElement).appendChild(t);
})(window,document,"clarity","script",id);
})()`;

export default function 클라리티() {
  if (!클라리티ID) return null;
  return <script id="ms-clarity" dangerouslySetInnerHTML={{ __html: 클라리티코드(클라리티ID) }} />;
}
