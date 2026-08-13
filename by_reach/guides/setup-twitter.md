# Twitter/X 配置指南

Twitter 的首选来源执行器是 `twitter-cli`；只有它失败、内容为空或无效时，才可
一次性使用 `bycli twitter search`。不要改用通用网页读取。

## 安装与诊断

```bash
by-reach install --env=auto --system --channels=twitter
by-reach doctor --json
```

## 凭据边界

用户可通过 Cookie-Editor 的 **Export → Header String** 导出后运行：

```bash
by-reach configure twitter-cookies
```

该命令使用隐藏输入，默认只写 `~/.by-reach/config.yaml`。`doctor` 不会执行
`twitter status`，不会修改当前 Shell。默认不会自动删除任何外部凭据文件；仅当
用户明确同意并传入 `--sync-legacy-twitter` 时，才会额外写入
`~/.config/xfetch/session.json` 与 `~/.config/bird/credentials.env`。

直接调用上游 `twitter` 时，必须在该进程环境中显式设置：

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
twitter search "query" -n 10
```

By-Reach 不会自动登录、读取浏览器 Cookie 或修改当前 Shell。
