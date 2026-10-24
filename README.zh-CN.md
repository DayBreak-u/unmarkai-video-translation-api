# UnmarkAI 视频翻译 / AI 配音 API

[English](README.md) · [简体中文](README.zh-CN.md)

通过 REST API 完成语音识别、翻译、可选的原文与译文审改、AI 配音和字幕输出。每个任务对应一种目标语言。

**[API 产品与文档](https://unmarkai.net/video-translation-api/) · [创建 API key](https://unmarkai.net/dashboard/api/keys) · [在线工具](https://unmarkai.net/video-translation-studio/)**

这是托管 API 的开源接入示例，提供 Python 与 cURL 代码；处理引擎和模型不在本仓库中。使用需要 API key 和可用 API 余额，API 美元钱包与网站积分独立。

## 处理流程

本地文件或直接 HTTPS 视频地址 → 上传就绪 → 识别与翻译 → 可选的两阶段人工审改 → 配音和渲染 → 下载视频与 SRT。

本仓库展示接入流程，暂未附带已验证的翻译演示视频。请用一段有权处理的短片验证实际效果。

## 快速开始

需要 Python 3.10+，在仓库根目录执行：

```bash
git clone https://github.com/DayBreak-u/unmarkai-video-translation-api.git
cd unmarkai-video-translation-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export UNMARKAI_API_KEY='uma_live_replace_with_your_key'
python examples/translate_video.py --file ./source.mp4 --target es
```

输出保存至 `output/`。`.env.example` 仅为模板，不会自动读取；请把 key 放在服务器环境变量中。

```bash
# 直接 HTTPS 视频地址，不接受平台观看页
python examples/translate_video.py --url 'https://your-cdn.example/owned-video.mp4' --target es
# 恢复已有任务，不重复创建
python examples/translate_video.py --job-id job_REPLACE
# 使用已经上传的文件创建任务
python examples/translate_video.py --upload-id upl_REPLACE --target es --idempotency-key your-stable-request-id
```

示例会输出 upload ID、job ID 和幂等键。创建请求重试须复用相同 upload ID、参数及幂等键；重新运行 `--file` 会生成新的上传。轮询超时不会取消服务端任务。

## 翻译参数与审改

- `--target es`：目标语言；新任务必填，一次一种语言。
- `--source auto`：自动识别源语言。
- `--advanced`：使用 Advanced 质量。
- `--manual-review`：分别暂停进行原文和译文审改。
- `--no-subtitles`：关闭字幕烧录，保留配音。

```bash
python examples/translate_video.py --file source.mp4 --target ja --manual-review
```

按 [两阶段审改指南](docs/review.md) 获取、编辑和确认文本。每阶段有独立版本及 72 小时期限，脚本不会自动批准审改。当前 OpenAPI 还包含音色、字幕样式、布局和分辨率等选项，请以实时契约为准。

成功后下载可用的视频、原文 SRT、译文 SRT 和可选音频等结果。

## cURL、文档与 AI Agent

- [可运行 cURL 示例](examples/quickstart.sh)：需要 Bash、cURL、jq。
- [API 流程和请求说明](docs/api.md)。
- [公开 OpenAPI 契约](https://unmarkai.net/openapi-v1.yaml)。
- [Agent Skills](https://github.com/DayBreak-u/unmarkai-skills) 和 [MCP 接入指南](https://unmarkai.net/video-text-removal-api/#api-agents-title)：当前覆盖去文字流程。

原视频已有硬字幕时，先调用去字幕 API，再把干净结果重新上传并创建翻译任务；这是两个分别计费的任务。Skill/MCP 是清理阶段的配套入口，不代表已有翻译 MCP 工具。

## 限制与费用

- 每个视频最多 2 GiB / 60 分钟，支持的 API 上传格式包括 MP4、MOV、AVI、MKV、WebM、MPEG；服务端校验为准。
- 基础费率：Standard $0.45/分钟，Advanced $1.125/分钟；最低计费时长与取整规则见实时文档。
- 账户实时价格及折扣以 `GET /v1/balance` 为准，详细规则见 API 页面；网站积分不能直接支付 API 任务。
- 结果下载地址会过期，请及时下载；结果仍在保留期内时可重新查询任务获取地址。
- 仅处理自有、已许可或明确获得编辑授权的视频，保留署名与必要声明。

## 相关资源

- [API documentation](https://unmarkai.net/dashboard/api/docs)
- [Create an API key](https://unmarkai.net/dashboard/api/keys) · [API console](https://unmarkai.net/dashboard/api/)
- [OpenAPI contract](https://unmarkai.net/openapi-v1.yaml)
- [Agent Skills](https://github.com/DayBreak-u/unmarkai-skills) · [Text-removal MCP guide](https://unmarkai.net/video-text-removal-api/#api-agents-title)
- [Video text removal API examples](https://github.com/DayBreak-u/unmarkai-video-text-removal-api)
- [Video translation API examples](https://github.com/DayBreak-u/unmarkai-video-translation-api)
- [Contact](https://unmarkai.net/contact/) · [Privacy](https://unmarkai.net/privacy/) · [Acceptable use](https://unmarkai.net/acceptable-use/)

## 开发与许可

```bash
python -m unittest discover -s tests -v
bash -n examples/quickstart.sh
```

测试使用模拟响应，不上传视频、不消费 API 额度。原始示例代码与文档使用 [MIT](LICENSE) 许可，演示媒体、品牌和托管服务按各自条款使用。
