# V2EX 与 Xueqiu

使用封装在 By-Reach channel 中的结构化 API，先验证响应包含实质数据。API 请求失败、
响应为空或结构无效时，才允许各执行一次 byCLI 回退；不得自行发起网页 HTTP 请求。

```python
from by_reach.channels.v2ex import V2EXChannel
from by_reach.channels.xueqiu import XueqiuChannel

V2EXChannel().get_hot_topics(limit=10)
XueqiuChannel().get_stock_quote("AAPL")
```

```bash
bycli v2ex hot --stdout
bycli xueqiu search "AAPL" --stdout
```

行情可能延迟且不构成投资建议。若 Xueqiu 的结构化 API 或 byCLI 均不能取得内容，
报告失败；不要读取浏览器 Cookie 或尝试其它网页路径。
