# Groq 转录配置指南

小宇宙与音频转录使用 By-Reach 的 `transcribe` 命令。用户提供密钥后，通过隐藏输入
或标准输入保存，绝不把密钥放入命令行参数：

```bash
by-reach configure groq-key
by-reach transcribe "https://example.com/audio.mp3"
```

转录仅在用户授权向所选服务发送音频时执行。网页或视频页面的读取仍遵守各自的来源
路由；通用 URL 只能由 `bycli web read --url URL --stdout` 读取。
