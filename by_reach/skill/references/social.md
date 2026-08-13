# 社交媒体与社区

先执行 `by-reach doctor --json` 了解可用性。它不替代对具体目标的内容验证。

## 有专用 CLI 的平台

每次请求只允许一次首选 CLI；失败、空结果、挑战页或无效包装时，才允许一次 byCLI
回退。第二次失败后停止，不得改用其它网页路径。

| 平台 | 首选 | 唯一回退 |
| --- | --- | --- |
| Twitter / X | `twitter-cli` | `bycli twitter search` |
| Reddit | `rdt-cli` | `bycli reddit search` |
| Bilibili | `bili-cli` | `bycli bilibili search` |

```bash
# Twitter/X
twitter search "query" -n 10
bycli twitter search "query" --stdout

# Reddit
rdt search "query" --limit 10
bycli reddit search "query" --stdout

# Bilibili
bili search "query" --type video -n 5
bycli bilibili search "query" --stdout
```

Twitter 和 Reddit 若需要凭据，只能使用用户明确提供的、为该工具配置的凭据；不得
自动登录、读取浏览器 Cookie 或把凭据注入命令输出。Bilibili 不把 YouTube 工具当作
替代来源。

## byCLI-only 平台

Facebook、Instagram、LinkedIn 与 XiaoHongShu 从第一步就是 byCLI，不存在第二个
网页后端：

```bash
bycli facebook search "query" --stdout
bycli instagram search "query" --stdout
bycli linkedin search "query" --stdout
bycli xiaohongshu search "query" --stdout
```

只执行用户授权的只读操作。没有可用且已授权的会话时，停止并说明需要用户自行建立
会话；不要代替用户登录，也不要导入、读取或注入 Cookie。
