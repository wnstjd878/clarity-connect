/**
 * 클라리티 녹화를 사이트의 방문 기록과 잇는다. (clarity-connect 틀)
 *
 * 클라리티 내보내기는 화면별 합계만 준다. 「이 녹화가 우리 표의 어느 방문인가」는 꼬리표로만 잇는다.
 * 시간으로 짝짓지 않는다(같은 분에 두 사람이 오면 틀린다).
 *
 * - identify: 방문 번호(무작위라 개인정보 아님). 클라리티 화면에서 이 번호로 녹화를 찾는다
 * - set: 매체·캠페인·소재. 광고 주소에서 온 값이라 번호·메일·주소 꼴은 거른다
 * - event: 사이트의 단계 이름(랜딩·결과·결제 같은 것). 단계가 한 주소 안에서 바뀌는 사이트는 이것이 유일한 단계 구분이다
 *
 * **사업자번호·성함·연락처·클릭 식별자는 절대 안 싣는다.** 꼬리표는 클라리티 서버에 남는다.
 * 클라리티가 없으면(ID 가 비었거나 광고 차단) 아무 일도 안 한다.
 *
 * [바꿀 곳] 부르는 자리: 방문 번호를 처음 만드는 곳에서 클라리티방문(), 단계를 남기는 곳에서 클라리티단계().
 */

type 클라리티함수 = (...인자: unknown[]) => void;

function 부르기(...인자: unknown[]) {
  if (typeof window === "undefined") return;
  const c = (window as unknown as { clarity?: 클라리티함수 }).clarity;
  if (typeof c !== "function") return;
  try {
    c(...인자);
  } catch {
    /* 녹화가 실패해도 화면은 계속돼야 한다 */
  }
}

/**
 * 광고 주소의 utm 값은 누가 무엇을 넣을지 모른다. 구분 기호를 떼고 숫자가 9자리 이상 이어지면
 * (전화번호·사업자번호) 거른다. 날짜(8자리)는 남긴다. @, ://, 60자 넘는 것도 거른다.
 */
export function 안전한꼬리표(값: string | null | undefined): string | null {
  if (!값) return null;
  const 글 = 값.trim();
  if (!글 || 글.length > 60) return null;
  if (/@|:\/\//.test(글)) return null;
  if (/\d{9,}/.test(글.replace(/[\s\-_.()]/g, ""))) return null;
  return 글;
}

/** 방문 번호를 새로 만들었을 때. 유입 꼬리표도 같이 붙인다 */
export function 클라리티방문(방문번호: string, 유입: Record<string, string | null> | null) {
  부르기("identify", 방문번호);
  if (!유입) return;
  for (const 이름 of ["매체", "캠페인", "소재"] as const) {
    const 값 = 안전한꼬리표(유입[이름]);
    if (값) 부르기("set", 이름, 값);
  }
}

/** 단계마다. 화면이 바뀌어도 같은 방문으로 묶이게 identify 를 다시 건다 */
export function 클라리티단계(방문번호: string, 단계: string) {
  부르기("identify", 방문번호);
  부르기("event", 단계);
}
