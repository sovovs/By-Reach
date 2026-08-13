# GitHub 与开发资料

GitHub 仅用 `gh` CLI；没有通用网页回退链。

```bash
gh search repos "query" --sort stars --limit 10
gh search code "query" --language python
gh repo view owner/repo
gh issue list -R owner/repo --state open
gh pr view 123 -R owner/repo
```

需要认证的命令必须由用户已有的 `gh` 登录态授权。不要在命令或日志中暴露令牌。
