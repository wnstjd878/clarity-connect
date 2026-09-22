<!-- style-guard:off 설치 안내 문서 -->
# clarity-connect

사이트에 **Microsoft Clarity 녹화**를 안전하게 붙이는 AI 코딩 도구용 스킬과 도구 모음입니다.
운영 사이트 세 곳에 손으로 붙이며 겪은 일을 순서와 검사로 옮겼습니다.

붙이고 나면 이렇게 됩니다.
- 손님 화면에서 녹화가 켜지고, 방문 번호·광고 매체·단계가 녹화에 꼬리표로 붙습니다.
- 녹화 속 글자는 기본으로 전부 가려집니다. 개인정보가 없는 광고 랜딩만 풀립니다.
- 관리자 화면과 로그인 없이 여는 공유 링크에서는 녹화가 켜지지 않습니다.
- 개인정보처리방침의 Microsoft 줄은 클라리티를 켰을 때만 나옵니다.
- 빌드본을 실제 브라우저로 열어 켜짐·꺼짐·가림·화면 오류를 확인한 뒤에 켭니다.

## 넣는 법

사이트 저장소 뿌리에서 한 줄입니다.

```bash
git clone https://github.com/wnstjd878/clarity-connect .claude/skills/clarity-connect
```

그다음 AI 코딩 도구에 이렇게 말합니다.

```
클라리티 붙여줘. .claude/skills/clarity-connect/SKILL.md 순서대로 하고, 단계마다 멈춰서 확인받아.
```

- **Claude Code** 는 `.claude/skills/` 를 스스로 읽습니다.
- **코덱스** 등 다른 도구는 위 문장처럼 `SKILL.md` 를 먼저 읽으라고 말하거나, `AGENTS.md` 에 그 한 줄을 넣습니다.
- 이 폴더를 저장소에 커밋하지 않으려면 `.gitignore` 에 `.claude/skills/clarity-connect/` 를 넣습니다.

## 들어 있는 것

| 경로 | 무엇 |
|---|---|
| `SKILL.md` | 순서와 관문. AI 도구가 따르는 원본 |
| `scripts/survey.py` | 0단계. 저장소를 읽어 끌 주소·로그인 없이 여는 id 링크·방침·CSP·배포 방식·남의 저장소 여부 판정 (Python 3.9+, 표준 라이브러리) |
| `scripts/clarity_project.py` | 1단계. 전용 크롬으로 클라리티 프로젝트 만들기·내보내기 열쇠 받기. 열쇠는 권한 600 파일에만 (playwright) |
| `templates/next-app/` | 2단계. Next.js App Router 용 설치 코드·꼬리표·대조 틀 |
| `scripts/probe.js` | 3단계. 빌드본을 브라우저로 열어 확인. 설정 예 `probe.example.json` (Node + playwright) |
| `docs/report-and-fix.md` | 5단계(선택). 매일 행동 보고와 「고치기」 자동 수정 설계 (Vercel 예약 실행 + GitHub Actions) |
| `scripts/clarity_recordings.py` | 5단계 지시 C 참고 구현. 녹화 목록 받아오기·사건 한 줄 요약·방문 기록과 짝짓기 (표준 라이브러리) |
| `UPGRADE.md` | 판마다 바뀐 것. 이미 붙인 사이트는 여기서 자기 판 이후만 반영 |

## 사람이 해야 하는 것

1. 클라리티 로그인(전용 크롬에서 처음 한 번, 풀리면 다시).
2. 클라리티 설정에서 마스킹을 **엄격(Strict)** 으로.
3. 개인정보처리방침 변경 공지(보통 시행 7일 전). 공지 기간이 지나기 전에 ID 를 넣지 않습니다.
4. 배포 승인.
5. 켠 뒤 녹화 하나를 열어 가림을 눈으로 확인.

열쇠(API 토큰 등)는 채팅에 붙이지 말고 서버 환경변수 설정 화면이나 파일에 직접 넣으세요.
