# 小红书配置指南

小红书的读取与搜索由 byCLI 执行。用户如需登录态页面，必须自行建立并明确授权可用的
byCLI 会话；By-Reach 不会自动登录、读取浏览器 Cookie、导出 Cookie 或注入凭据。

先检查能力：

```bash
by-reach doctor --json
bycli list -f json
```

当 `xiaohongshu/search` 能力可用时，按 byCLI 的命令帮助执行已授权的只读任务。若
能力缺失或读取失败，停止并报告，不要改用别的网页读取方式。
