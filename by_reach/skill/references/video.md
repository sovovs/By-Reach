# 视频与播客

## YouTube

先用 `yt-dlp` 取得视频信息或字幕。首次执行失败、输出为空或无效时，允许一次
byCLI 回退；回退失败即停止。

```bash
yt-dlp --write-sub --write-auto-sub --skip-download -o "/tmp/%(id)s" "URL"
bycli youtube search "URL" --stdout
```

只有用户明确要求且已配置转写提供方时，才能使用 `by-reach transcribe "URL"`。

## Bilibili

先用 `bili-cli`；失败或没有实质内容后只可回退一次：

```bash
bili video BVxxx
bycli bilibili search "BVxxx" --stdout
```

## Xiaoyuzhou

使用 By-Reach 的转写流程处理用户明确提供的公开音频地址。不要把播客页面当作通用
网页而换用另一个读取器。
