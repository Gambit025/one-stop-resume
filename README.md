# One-Stop Resume

[在线使用](https://one-stop-resume.onrender.com/) · 中文求职简历 PDF 排版工具

上传已有文字版 PDF，选择内置模板或上传自己的模板，生成、核对、逐页预览并下载新的 PDF。系统不会主动润色内容；AI 结构化仍可能产生差异，因此结果始终需要人工检查。

## 运行

Python 3.11；部署依赖已固定在 `requirements.txt`。生产使用仓库 Dockerfile / `render.yaml`，单 Gunicorn 进程、4 HTTP 线程、最多一个转换子进程。

```sh
pip install -r requirements.txt
python -m playwright install --with-deps --only-shell chromium
python download_fonts.py
export GROQ_API_KEY=your_key
python app.py
```

浏览器打开 `http://127.0.0.1:8080`。密钥只设为服务环境变量，不能写入提交。`GROQ_MODEL` 默认 `openai/gpt-oss-120b`。旧 Anthropic 兼容逻辑仅用于未配置 Groq 的本地兼容；生产应设置 Groq 密钥。

## 任务接口

- `POST /api/jobs`：multipart `resume`，以及 `template_id` 或 `template`；返回 202 与 `job_id`、`token`、`expires_at`。
- `GET /api/jobs/<id>`：真实阶段、任务状态、耗时、核对结果。
- `GET /api/preview/<id>/<page>`：最终 PDF 的逐页 PNG，页码从 1 开始。
- `GET /api/download/<id>`：下载 PDF。
- `DELETE /api/jobs/<id>`：取消任务并删除本地任务文件。
- `GET /health`：独立健康检查。

除提交、模板列表和健康检查外，任务接口必须携带 `X-Job-Token`。凭证仅存在当前服务内存与浏览器会话。不要把凭证放在 URL 中。旧同步生成接口已移除。

每份文件最多 10 MB、10 页、20,000 字符。拒绝损坏、加密和无可提取文字的 PDF。队列限制为一个运行、两个等待，超限返回 429；从接收起最多 120 秒，之后终止转换进程组。进度不依靠计时器模拟。

原始输入和中间 HTML 在成功后删除。结果一小时后失效，在五分钟清理周期或访问时删除；失败、取消、超时会删除任务目录。重启不恢复任务。结果和正文不进入公共缓存或应用日志。临时磁盘不是持久存储。

## 测试与维护

```sh
python -m unittest discover -s tests -v
node --check static/app.js
# 本机界面验收：真实 PDF 渲染、确定性 AI 替身，不调用外部 API
python -m tests.ui_server
# 显式线上验收：只会生成/上传虚构数据，调用免费额度并删除测试结果
python -m tests.live_smoke --fixtures short dense two_pages mixed
```

三轮交付证据及性能限制见 [docs/DELIVERY.md](docs/DELIVERY.md)。Render 免费实例会休眠；Groq 免费额度和模型可用性受平台限制。不要把单次测试当作稳定性能承诺。
