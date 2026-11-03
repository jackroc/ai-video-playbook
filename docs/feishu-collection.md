# 飞书群分享自动收录

把公开的 X 帖子或 TikTok 视频链接发到配置好的收录群。服务会规范化链接、去重、尝试读取平台公开嵌入信息，并将案例保存到 [自动收录目录](../references/community/README.md)。GitHub 写入成功后，群里会收到案例链接。

初版根据公开正文中的关键词分类。明确标注为 `Prompt:` 或 `提示词：` 的段落会单独列出。平台不返回正文、短链打不开或提示词不在正文时，案例仍会收录并标注待补。当前不分析视频画面、评论区或截图，不下载或转载视频。此类案例都是外部分享，尚未自行复现。

## 配置

1. 在飞书开发者后台启用应用机器人并订阅 `im.message.receive_v1`，将应用机器人加入专用收录群。直接发链接需要应用具备接收群消息权限；若只有 @ 事件权限，需要 @ 应用机器人。
2. 用 `.env.example` 创建本地 `.env`，填写专用群的 `FEISHU_CHAT_ID` 和群自定义机器人 `FEISHU_WEBHOOK_URL`。两个机器人分别接收消息和发送回执。`.env` 及 `.local/` 会被 Git 忽略。
3. 确认 `lark-cli` 的 bot 身份可用，且本机 GitHub SSH 凭证可以写入 `jackroc/ai-video-playbook`。设置本检出的 Git 提交身份。脚本使用独立的 `.local/collection-repo` 检出写入，避免触碰日常工作的文件。
4. 先用 `python3 scripts/collect_feishu.py preview --url '<公开帖子链接>'` 检查生成内容；预览不会写仓库或通知群。运行 `python3 scripts/collect_feishu.py run` 启动接收与入库。服务需在可联网并可访问飞书 CLI 凭证的常在线机器运行。

## 状态与排查

- `.local/receiver-ready` 存在表示 CLI 已就绪，实际收到群消息还取决于应用权限和群成员关系。
- `.local/queue.sqlite3` 保留待处理任务、已收录结果和待发送回执。消息重推或重复发送同一原帖不会新建重复案例。
- GitHub 写入失败会有限重试，原链接仍在本机队列中。已写入 GitHub 但通知暂时失败时，程序会重试通知。
- 群内只发布收录结果；入库只使用链接指向的公开资料，不提交群消息正文、成员身份、群 ID 或访问凭证。
