# Exa 搜索

Exa 是唯一启用的 MCP 搜索来源。通过 `mcporter` 调用
`exa.web_search_exa`：

```bash
mcporter call exa.web_search_exa query="query" numResults=5
```

若需要打开结果链接阅读正文，链接随后属于通用网页任务，必须使用：

```bash
bycli web read --url "URL" --stdout
```

Exa 不可用时报告搜索失败；不要用其它 MCP 读取器或通用网页机制替代。
