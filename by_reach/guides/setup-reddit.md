# Reddit 配置指南

Reddit 首先使用 `rdt-cli`。首选命令失败、返回挑战页或无有效内容时，只允许一次
`bycli reddit search` 兜底；不要改走通用网页读取。

用户授权安装后：

```bash
by-reach install --env=auto --system --channels=reddit
by-reach doctor --json
```

认证与会话只由用户显式建立和授权。By-Reach 不会自动登录、扫描浏览器配置或注入
Cookie。若已授权的首选和 byCLI 路由均失败，请报告失败。
