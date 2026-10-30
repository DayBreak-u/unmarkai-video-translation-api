# 视频翻译 / AI 配音 API 接入示例（国内站）

[English](README.md) · [简体中文](README.zh-CN.md)

这是剪狐（UnMarkAI）视频翻译 API 的接入示例，代码是 Python 和 cURL。处理在剪狐的服务端完成，仓库里没有模型和处理引擎。

本文按国内站来写。国内站和海外站的路径、字段相同，区别在接口地址、密钥和计费币种。英文 README 写的是海外站。

- API 文档（功能说明）：https://unmarkai.cn/developers/docs/
- 获取 API 密钥（控制台）：https://unmarkai.cn/developers/?tab=keys
- OpenAPI 契约：https://unmarkai.cn/openapi-v1.yaml （server 选 `https://unmarkai.cn/api`，路径里已经带 `/v1`）

## 先说明几点

- REST 地址是 `https://unmarkai.cn/api/v1`。
- 控制台用手机号登录，在里面创建 `uma_live_*` 密钥。手机号登录的会话不能拿来调接口。
- 国内站和海外站的密钥、钱包是分开的，海外站的密钥在国内站用不了，反过来也一样。
- 按人民币计费，余额通过微信充值。
- 翻译只能走 REST。国内站的 MCP 目前只有去字幕工具，没有翻译。

## 处理流程

本地文件或 HTTPS 直链 → 上传完成 → 识别和翻译 → 配音和渲染 → 下载视频和 SRT。

一个任务只对应一种目标语言。仓库里没有附演示视频，先拿一段有权处理的短视频试一下。

## 快速开始

需要 Python 3.10+，在仓库根目录执行：

```bash
git clone https://github.com/DayBreak-u/unmarkai-video-translation-api.git
cd unmarkai-video-translation-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export UNMARKAI_API_BASE='https://unmarkai.cn/api/v1'
export UNMARKAI_API_KEY='uma_live_replace_with_your_key'
python examples/translate_video.py --file ./source.mp4 --target en
```

不设 `UNMARKAI_API_BASE` 时示例会请求海外站，所以国内站一定要先设好。结果保存在 `output/`。`.env.example` 只是模板，脚本不会自动读取，密钥放在服务端的环境变量里。

```bash
# HTTPS 视频直链，不支持平台的播放页
python examples/translate_video.py --url 'https://your-cdn.example/owned-video.mp4' --target en
# 继续查询已有任务，不会重新创建
python examples/translate_video.py --job-id job_REPLACE
# 用已经上传好的文件创建任务
python examples/translate_video.py --upload-id upl_REPLACE --target en --idempotency-key your-stable-request-id
```

脚本会打印 upload ID、job ID 和幂等键。重试创建请求时，upload ID、参数和幂等键都要和原来一样。重新跑 `--file` 会产生新的上传。本地轮询超时不会取消服务端的任务。

## 参数

- `--target en`：目标语言，新任务必填，一次一种。
- `--source auto`：源语言，默认自动识别。
- `--advanced`：用高级翻译，按高级价格计费。
- `--no-subtitles`：不烧录字幕，只保留配音。

OpenAPI 里还有音色、目标地区、背景音、参考文本、字幕样式和布局、输出分辨率等字段，示例脚本没有全部做成命令行参数，需要时直接按契约加到请求体里。可用音色先调 `GET /v1/voices` 查。

成功后会下载能拿到的结果：`translated.mp4`、`source.srt`、`translated.srt`，有的话还有音频和原始识别字幕。

## cURL

```bash
export UNMARKAI_API_BASE='https://unmarkai.cn/api/v1'
export UNMARKAI_API_KEY='uma_live_replace_with_your_key'
TARGET_LANGUAGE=en bash examples/quickstart.sh ./source.mp4
```

需要 Bash、cURL 和 jq。脚本只负责上传、建任务和查一次状态，后续轮询和下载用 Python 示例的 `--job-id`。请求流程和重试注意事项见 [docs/api.md](docs/api.md)。

## 原视频有硬字幕

翻译不会擦掉原视频里已有的硬字幕。需要的话先用去字幕 API 处理，把干净的视频下载下来，重新上传，再建翻译任务。这是两个任务，分别计费。去字幕的示例在 [unmarkai-video-text-removal-api](https://github.com/DayBreak-u/unmarkai-video-text-removal-api)。

## 价格

| 功能 | 元 / 分钟 |
|---|---|
| 普通翻译 | 2.40 |
| 高级翻译 | 4.80 |

这是标准价。每个视频按秒向上取整，最低按 15 秒计费。配音、字幕、音色这些选项不额外加价，只出字幕也按所选档位计费。任务开始前会按实际时长冻结费用，成功后结算，失败或允许的取消会释放。账户折扣和实际单价以 `GET /v1/balance` 返回的为准，金额币种是 CNY。

## 限制

- 单个视频最多 2 GiB、60 分钟，支持 MP4、MOV、AVI、MKV、WebM、MPEG，以服务端校验为准。
- 任务是异步的，可以轮询，也可以在控制台配置回调，示例用的是轮询。
- 下载链接会过期，拿到后尽快下载。还在保留期内的话，重新查询任务可以拿到新链接。
- 只处理你自己拥有、已获授权或明确允许编辑的视频。

## 开发

```bash
python -m unittest discover -s tests -v
bash -n examples/quickstart.sh
```

测试用的是模拟响应，不会上传视频，也不会扣费。示例代码和文档用 [MIT](LICENSE) 许可，托管服务按剪狐的服务条款使用。
