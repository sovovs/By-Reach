# Exa Search 配置指南

By-Reach 的搜索渠道使用 `mcporter` 调用 `exa.web_search_exa`。这是搜索渠道，
不是通用网页读取的替代品。

用户授权系统修改后：

```bash
by-reach install --env=auto --system
mcporter call exa.web_search_exa query="test" numResults=1
```

如果 Exa 不可用，报告搜索渠道失败。不要把搜索失败转换为另一种通用网页读取方式。
