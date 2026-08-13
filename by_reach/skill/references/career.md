# LinkedIn 与招聘

LinkedIn 是 byCLI-only 平台：

```bash
bycli linkedin search "software engineer" --stdout
```

只进行用户授权的只读检索。没有现成且明确授权的会话时停止；不得自动登录、读取或
注入浏览器 Cookie，也不得改走其它网页工具。
