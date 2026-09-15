<!-- style-guard:off 설계 지시문 -->
# 매일 행동 보고와 「고치기」 (선택 단계)

녹화를 켠 뒤, 하루 몇 번 방문자 행동을 AI 로 분석해 **관리자 화면에 개선 과제**를 띄우고,
과제마다 **[고치기]** 를 누르면 AI 가 코드를 고쳐 미리보기를 올리고, 사람이 **[배포]** 를 누를 때만 운영에 나가게 하는 설계입니다.
사이트 서버만으로 돌도록 **Vercel 예약 실행 + GitHub Actions** 로 적었습니다. 다른 호스팅이면 같은 약속을 그 도구로 옮깁니다.

아래 두 지시는 AI 코딩 도구에 **하나씩** 붙여 넣는 문장입니다. `<…>` 는 사이트에 맞게 바꿉니다.
관리자 화면이 바뀌므로 **먼저 시안을 보여 주고 승인받은 뒤** 만들게 하세요.

## 먼저 사람이 할 일

- 클라리티 설정 › 데이터 내보내기 › API 토큰(1단계 `clarity_project.py token` 으로도 받음).
- 서버 환경변수: `CLARITY_API_TOKEN`, `CRON_SECRET`, `BEHAVIOR_WORKER_TOKEN`, `GITHUB_DISPATCH_TOKEN`, AI 열쇠(예: `ANTHROPIC_API_KEY`).
- GitHub 저장소 Secrets: AI 열쇠, 배포 열쇠(예: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_AUTOMATION_BYPASS_SECRET`), `BEHAVIOR_WORKER_TOKEN`, `APP_BASE_URL`.
- 개인정보처리방침: 방문 기록을 AI 로 분석하면 그 AI 회사로 가는 항목이 늘어납니다. 공지 기간을 정합니다.
- 비용: AI 호출(보고 하루 몇 번, 고치기 한 번마다), GitHub Actions 사용 시간.

## 지시 A. 매일 행동 보고 + 관리자 화면

```
하루 세 번 방문자 행동을 분석해 관리자 <유입·분석 화면 경로> 에 보고와 개선 과제를 띄운다.
관리자 디자인은 바꾸지 않는다. 지금 관리자 화면의 카드·표 부품만 쓴다. 먼저 시안을 보여 주고 승인받아라.

1. 받아오기: 예약 실행(예: vercel.json crons) 하루 세 번 → /api/cron/behavior-report. CRON_SECRET 없으면 401.
2. 클라리티: GET https://www.clarity.ms/export-data/api/v1/project-live-insights
   ?numOfDays=1&dimension1=..&dimension2=..  머리글 Authorization: Bearer CLARITY_API_TOKEN
   세 번만 부른다: (Channel, URL) / (Source, Medium, Campaign) / (Device, URL).
   하루 10번 한도라 받은 원본을 DB 에 저장하고, 같은 날 다시 만들 때는 저장본을 쓴다.
   한 주소 안에서 단계가 바뀌는 화면은 클라리티로는 단계가 안 나뉜다.
3. 사이트 자체 기록: 최근 24시간 방문을 방문 번호로 묶고 단계 흐름을 만든다.
   운영자·로봇·점검 도구 방문은 빼고 뺀 수만 센다. 머문 시간 0초는 이탈 근거로 쓰지 않는다.
4. 분석: AI 에 위 둘을 넣고 JSON 을 받는다.
   { 요약, 채널별[{채널, 방문, 1분이상, 주요 전환, 판정: 양질|이탈|보류}],
     문제화면[{화면, 현상, 횟수}], 개선과제[{순위, 과제, 근거}] 최대 6, 주요방문 최대 3 }
   방문이 1~2회뿐인 채널은 보류. AI 에게 이름·연락처·사업자번호·방문 번호 원문을 주지 않는다(방문은 V1, V2 로 바꿔 넣는다).
5. 표: behavior_reports(보고일 유일, 클라리티 원본, 결과), behavior_tasks(보고id, 순위, 과제, 근거,
   상태 CHECK 대기|반영함|안함). DB 쓰기는 오류를 반드시 검사한다.
6. 다음 보고는 어제 과제 상태를 읽는다. 반영함은 같은 현상이 또 보일 때만 다시 올리고, 안함은 뺀다.
7. 화면: 요약 한 줄, 행동 숫자(녹화된 방문·머문 시간·스크롤·반응 없는 클릭·연달아 누름·바로 뒤로),
   캠페인별·기기별 표, 문제 화면 표, 개선 과제 표(상태 고르기). 빨강은 제일 나쁜 숫자 하나에만.
8. 확인: 예약 경로를 손으로 한 번 불러 보고가 쌓이는지, 화면에 뜨는지, 상태가 새로고침 뒤에도 남는지 브라우저로 본다.
```

## 지시 B. 과제 「고치기」와 「배포」

```
개선 과제 줄마다 [고치기] 를 단다. 누르면 GitHub Actions 가 AI 로 코드를 고쳐 미리보기를 띄우고,
사람이 미리보기를 보고 [배포] 를 눌렀을 때만 운영에 나간다. 관리자 디자인은 바꾸지 않는다.

1. 표 behavior_fix_jobs: 과제id, 상태 CHECK
   queued|fixing|verifying|preview_ready|deploy_requested|deploying|deployed|needs_human|failed,
   가지, 미리보기주소, 커밋, 한줄사유, 시각.
   진행 중(queued~verifying, deploy_requested, deploying)은 과제당 하나만. 45분 넘게 붙잡힌 작업은 failed.
   preview_ready 는 진행 중으로 치지 않는다(아니면 [다시]가 영영 막힌다).
2. 창구: 관리자용(고치기·다시·배포·목록), 작업자용(상태 올리기, BEHAVIOR_WORKER_TOKEN 머리글).
   상태는 정해진 순서로만 바뀐다. 배포는 같은 과제의 가장 새 작업만, 가지·커밋·미리보기주소가 있어야.
3. [고치기] → 서버가 GitHub workflow_dispatch 로 .github/workflows/behavior-fix.yml 실행(입력: 작업id).
4. behavior-fix.yml:
   - 가지 fix/behavior-<작업id 앞 8자> 를 main 에서 만든다
   - AI 코딩 에이전트(예: anthropics/claude-code-action, 최신 문서를 확인해서)로 과제를 고친다
   - 고쳐도 되는 곳: <손님 화면 폴더와 css>
   - 건드리면 멈출 곳: <계산·판정 로직, 개인정보처리방침, 서버 창구, DB, 결제·메시지 발송, 관리자 화면>
     → 바뀌었으면 needs_human 으로 올리고 끝
   - 타입 검사 오류 수가 main 보다 늘지 않았나 → 빌드 → 저장소의 검사 명령
   - 커밋·가지 push → 미리보기 배포(운영 아님)
   - 미리보기가 로그인 벽이면 우회 머리글로 연다. 200 이어도 로그인 화면 제목이면 실패로 본다
   - 브라우저로 미리보기를 열어 콘솔 오류 0 이면 preview_ready + 주소. 아니면 failed + 이유
5. [배포] → behavior-deploy.yml:
   - 가지에 origin/main 을 합친다. 충돌이면 needs_human
   - main 에 아직 운영에 안 나간 다른 커밋이 있으면 그 목록을 한줄사유에 적고 멈춘다(같이 딸려 나간다)
   - 빌드 → 운영 배포 → 배포 완료 확인
   - main 에 합쳐 push. 거절되면 다시 받아 합치고 올린다
   - deployed, 과제 상태 반영함
6. 화면: 과제 줄에 [고치기] / 진행 상태+한 줄(15초마다 갱신) / [미리보기] [배포] [다시(한 줄 지시)] / 확인 필요·실패 이유.
7. 확인: 문구 한 줄짜리 시험 과제로 한 바퀴. 고치기 → preview_ready → 미리보기에 바뀐 글자, 운영은 그대로.
   배포는 사람이 직접 누른다. 시험이 끝나면 작업·과제·가지를 지운다.
```

## 주의

- 「고치기」는 AI 가 운영 코드를 고치는 기능입니다. 배포는 반드시 사람이 미리보기를 보고 누릅니다.
- 돈·판정·권한이 걸린 코드는 작업자가 못 건드리게 막으세요. 조용히 바뀌면 손님에게 틀린 결과가 나갑니다.
