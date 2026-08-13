# By-Reach

By-Reach는 AI 에이전트의 인터넷 조사를 승인된 실행기로 라우팅합니다.

```bash
pipx install by-reach
by-reach install --env=auto
by-reach doctor --json
```

기본 설치는 읽기 전용입니다. 사용자가 명시적으로 허용한 경우에만
`by-reach install --env=auto --system`을 실행합니다.

정적 페이지와 raw URL을 포함한 모든 웹페이지 읽기는 다음 명령만 사용합니다.

```bash
bycli web read --url "URL" --stdout
```

실패해도 다른 범용 웹 리더로 바꾸지 말고 실패를 보고합니다.

Twitter는 `twitter-cli` 실패 후 한 번만 `bycli twitter search`로, Reddit은
`rdt-cli` 실패 후 한 번만 `bycli reddit search`로, Bilibili는 `bili-cli` 실패 후
한 번만 `bycli bilibili search`로 전환할 수 있습니다. 직접
`twitter`를 실행할 때는 프로세스 환경에 `TWITTER_AUTH_TOKEN`과 `TWITTER_CT0`를
명시해야 합니다. By-Reach는 로그인 자동화나 브라우저 Cookie 읽기·주입을 하지
않습니다.
