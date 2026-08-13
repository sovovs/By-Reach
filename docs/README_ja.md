# By-Reach

By-Reach は、AI エージェントのインターネット調査を承認済みの実行器へ
ルーティングします。

```bash
pipx install by-reach
by-reach install --env=auto
by-reach doctor --json
```

通常のインストールは読み取り専用です。ユーザーの明示的な許可がある場合だけ
`by-reach install --env=auto --system` を実行してください。

すべての Web ページ、静的ページ、raw URL の読み取りは次だけです。

```bash
bycli web read --url "URL" --stdout
```

失敗した場合に別の汎用 Web リーダーへ切り替えてはいけません。失敗を報告します。

Twitter は `twitter-cli` の後に一度だけ `bycli twitter search` へ、Reddit は
`rdt-cli` の後に一度だけ `bycli reddit search` へ、Bilibili は `bili-cli` の後に
一度だけ `bycli bilibili search` へフォールバックできます。直接
`twitter` を使う場合は、プロセス環境に `TWITTER_AUTH_TOKEN` と `TWITTER_CT0`
を明示的に設定します。By-Reach はログインやブラウザー Cookie の読み取り・注入を
行いません。
