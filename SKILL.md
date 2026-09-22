---
name: clarity-connect
description: 사이트에 Microsoft Clarity 녹화를 안전하게 붙이는 정해진 순서. 조사 → 클라리티 프로젝트·열쇠 → 설치 → 빌드본 검증 → 켜기 → (선택) 매일 행동 보고. "클라리티 붙여", "클라리티 연동", "행동 분석 붙여", "녹화 달아", 또는 /clarity-connect 를 말하면 쓴다.
---

<!-- style-guard:off 절차 문서라 목록·명령이 대부분이다 -->

# 클라리티 연동 (clarity-connect)

이 폴더는 사이트 저장소의 `.claude/skills/clarity-connect/` 에 있다고 가정한다. 명령의 `$CC` 는 그 경로다.
**단계마다 관문이 있다. 앞 단계 확인 없이 다음으로 가지 않는다.**

| 단계 | 도구 | 사람 관문 |
|---|---|---|
| 0 조사 | `scripts/survey.py` | 「사람이 정할 것」 답 |
| 1 클라리티 | `scripts/clarity_project.py` | 로그인(처음·만료 시), 마스킹 엄격 한 번 |
| 2 설치 | `templates/next-app/` | 코드 검토 |
| 3 검증 | 대조 + `scripts/probe.js` | 없음 |
| 4 켜기 | 사이트 배포 방식대로 | 방침 공지 기간, 배포 승인 |
| 5 보고(선택) | `docs/report-and-fix.md` | 설계 승인 |

## 0. 조사

```bash
python3 $CC/scripts/survey.py . --site <이름> --mine <내 GitHub 계정·조직, 쉼표로>
```

- 저장소에 `CLAUDE.md`·`AGENTS.md`·인계 문서가 있으면 **먼저 읽는다**. 배포 방식·손님 말투·건드리면 안 되는 파일이 거기 있다.
- 「사람이 정할 것」을 사용자에게 한 번에 묻는다: 로그인 없이 여는 id 링크를 끌지, 방침 변경 공지 기간, CSS 보관을 붙일지.

## 1. 클라리티 프로젝트·열쇠

```bash
pip install playwright
python $CC/scripts/clarity_project.py launch      # 전용 크롬. 창이 뜬다는 것을 사용자에게 먼저 알린다
python $CC/scripts/clarity_project.py check       # 로그인 확인 + 프로젝트 목록
python $CC/scripts/clarity_project.py create --name "<이름>" --url <주소> --industry "<업계 글자 그대로>" --dry-run
python $CC/scripts/clarity_project.py create ...  # 같은 주소 프로젝트가 있으면 새로 안 만들고 ID 만 준다
python $CC/scripts/clarity_project.py token --project <ID> --site <이름> --verify   # 매일 보고를 할 때만
```

- 열쇠는 클립보드에서 읽어 **`~/.config/clarity-connect/clarity_<site>.tok`(600)** 에만 쓴다. 채팅·명령 인자·화면에 내지 않는다.
- `--verify` 는 조회 1회를 쓴다(하루 10회 한도).
- 로그인은 사람이 그 창에서 한다. 자동 입력하지 않는다.
- 마스킹 **엄격(Strict)** 은 클라리티 설정에서 사람이 한 번 고른다.

## 2. 설치 (가지에서)

`templates/next-app/` 세 파일을 사이트에 복사하고 `[바꿀 곳]` 만 고친다. 다른 스택은 **같은 약속**을 그 스택 모양으로 옮긴다.

반드시 넣을 것:
1. **설치**: 서버가 HTML 에 싣는 인라인 스크립트, 태그는 **head 끝에** 붙인다. 첫 script 앞에 끼우기(`insertBefore`)·JSX `<script async src>`·head 인라인 stub·useEffect 로 늦게 싣기는 React #418 이나 수집 0 을 냈다.
2. **끄는 주소**: 관리자 + 주소가 열쇠인 링크. 설치 코드 첫 줄에서 멈춘다. 켜진 화면에서 화면 안 이동으로 그 주소에 갈 수 있으면 `clarity("stop")`/`start` 도 건다.
3. **꼬리표**: 방문 번호로 identify, 매체·캠페인·소재는 `안전한꼬리표` 를 거쳐 set, 단계는 event. 번호·이름·연락처·클릭 식별자는 안 싣는다. 방문 번호가 없으면 먼저 만든다(세션 저장소에 무작위 번호).
4. **가림**: `<body data-clarity-mask="true">` + 개인정보 없는 광고 랜딩만 `data-clarity-unmask`. **화면마다 찾아 가리지 않는다**(입력란 하나를 빠뜨리기 쉽다).
5. **방침**: 방침 파일이 같은 환경변수를 보게 해 **ID 가 있을 때만** Microsoft 줄·화면 이용 행태가 나오게 한다.
6. **CSP** 가 있으면 `script-src www.clarity.ms *.clarity.ms`, `connect-src *.clarity.ms c.bing.com`.
7. **CSS 보관**(붙이기로 했으면): 배포마다 CSS 파일 이름이 바뀌면 옛 녹화가 스타일 없이 재생된다. 빌드 뒤 옛 CSS 를 공개 폴더에 일정 기간 남긴다.
8. 인계 문서가 있으면 절을 더한다. 작업이 끝나면 바로 커밋한다.

## 3. 검증

1. 대조 통과 → **규칙을 일부러 되돌려 빨간불 확인**(끄는 주소를 지우면 실패해야 한다) → 되돌림.
2. 타입 검사·빌드. 프레임워크가 만드는 타입 오류는 빌드 뒤 다시 본다.
3. **빌드본**으로 본다. dev 서버에서는 화면 맞춰 끼우기 오류가 안 난다.
   ```bash
   NEXT_PUBLIC_CLARITY_PROJECT_ID=test1 npm run build && NEXT_PUBLIC_CLARITY_PROJECT_ID=test1 PORT=3400 npm run start
   node $CC/scripts/probe.js <설정.json>      # 예: scripts/probe.example.json. playwright 필요
   ```
   클라리티 서버 요청과 같은 사이트 쓰기 요청은 도구가 막는다.
4. ID 를 빼고 다시 빌드해 설치 코드·방침 줄이 0 인지 본다.
5. 다른 모델이나 사람의 교차 검수. 지적은 **먼저 대조에 사례로 넣어 빨간불을 본 뒤** 고친다. 같은 갈래 지적이 세 번째로 이어지면 멈추고, 받아들일 위험은 근거와 함께 코드 머리말·인계 문서에 적는다.

## 4. 켜기

- **방침 변경 공지 기간**이 지나기 전에는 ID 를 넣지 않는다.
- 배포 방식은 저장소마다 다르다(0단계 판정). git push 로 배포되지 않는 곳이 있다.
- 운영 확인: 손님 화면에서 `clarity.ms/tag/<ID>` 와 collect 요청, 끄는 주소는 0, 녹화 하나를 열어 가림을 눈으로 본다.

## 5. 매일 행동 보고·고치기 (선택)

`docs/report-and-fix.md` 설계를 따른다. 사이트 관리자 화면에 들어가는 것이라 **화면 시안 승인 뒤** 만든다.

지시 A(보고) → 지시 B(고치기·배포) → 지시 C(녹화 읽고 제안) 순서다. 이미 붙인 사이트가 업그레이드를 요청하면 `UPGRADE.md` 에서 그 사이트에 없는 판만 반영한다.

## 기억할 함정

- 클라리티 내보내기는 **화면별 합계**만 준다. 한 사람 단위 신호는 사이트 자체 기록이 필요하다. 한 주소 안에서 단계가 바뀌는 사이트는 event 가 유일한 단계 구분이다.
- 한 쪽만 본 방문은 머문 시간이 0초로 찍힌다. 이탈 근거로 쓰지 않는다. 운영자·점검 도구 방문이 크게 섞일 수 있다.
- 자동 조작 브라우저는 사이트가 내부 방문으로 보고 기록을 안 보낼 수 있다(`navigator.webdriver`). probe.js 는 가린다.
- 주소 뒤 광고 값(utm·fbclid)은 화면 주소와 함께 클라리티로 간다. 지우면 유입 측정이 깨지므로 규칙은 "광고 링크 utm 에 개인정보를 적지 않는다".
- Vercel 미리보기는 로그인 벽이다. 200 인데 제목이 "Login – Vercel" 이면 실패다.
