# 网页与 RSS

## 任意网页或 URL

无论页面是公开、静态、服务端渲染、动态渲染、原始文本或 Markdown，均只用：

```bash
bycli web read --url "URL" --stdout
```

这是 `web/read` 的唯一执行路径。不得以任何直接 HTTP、阅读代理、内置抓取器、
旧适配器或通用浏览器先试读或在失败后降级。byCLI 无法读到实质内容时，停止并说明
失败原因。

## RSS

RSS 不是通用网页读取。使用 `feedparser` 库解析 feed；解析失败时报告失败，不转为
其它网页读取路径。

```python
import feedparser

feed = feedparser.parse("FEED_URL")
for entry in feed.entries[:5]:
    print(entry.title, entry.link)
```
