# Feishu Doc Fetcher Skill

Feishu Doc Fetcher 是一个面向 AI 编程代理的 Skill，也可以作为独立 Python 脚本使用。它通过飞书开放平台 API 读取飞书 docx 文档，把正文、标题、列表、代码块、表格、图片和附件保存到本地 Markdown，方便 Claude Code、Codex 或人类继续阅读和处理。

## 功能概览

- 读取飞书 docx 文档元信息和完整 block 列表
- 转换文本段落、H1-H9 标题、无序列表、有序列表、引用、分割线和代码块
- 转换简单表格为 Markdown table
- 下载图片到 `images/{document_id}/`
- 下载附件到 `attachments/{document_id}/`
- 识别嵌入式表格和多维表格，并在 Markdown 中保留占位注释
- 递归抓取 wiki 子文档，递归深度可配置
- 自动管理 tenant access token，并对常见临时 HTTP 错误做重试

## 仓库结构

```text
feishu-doc-fetcher/
├── SKILL.md            # Agent Skill 入口，Claude Code 和 Codex 都会读取
├── feishu_fetch.py     # 实际抓取与 Markdown 转换脚本
├── agents/openai.yaml  # Codex 可选 UI 元数据
├── requirements.txt    # Python 依赖
├── LICENSE
└── README.md
```

## 适用场景

- 让 Claude Code 或 Codex 读取一篇飞书文档并总结、改写、拆任务
- 把飞书知识库页面导出为 Markdown，放进本地项目或知识库
- 批量保留文档里的图片、Excel、SQL 等附件
- 跟随 wiki 子节点，把一组关联 docx 文档导出到本地

## 前置条件

1. Python 3.9+
2. Python 依赖：

```bash
python3 -m pip install -r requirements.txt
```

3. 飞书开放平台应用凭证：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

4. 飞书应用权限：

- `docx:document:readonly`：读取文档内容
- `drive:drive:readonly`：下载图片和附件
- `wiki:wiki:readonly`：读取 wiki 子节点，可选

## 作为 Skill 安装

这个仓库根目录就是一个 Skill 目录，目录名需要保持为 `feishu-doc-fetcher`。

### Claude Code

安装为个人 Skill：

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/<your-name>/feishu-doc-fetcher.git ~/.claude/skills/feishu-doc-fetcher
```

或安装为项目 Skill：

```bash
mkdir -p .claude/skills
git clone https://github.com/<your-name>/feishu-doc-fetcher.git .claude/skills/feishu-doc-fetcher
```

### Codex

安装为个人 Skill：

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/<your-name>/feishu-doc-fetcher.git ~/.agents/skills/feishu-doc-fetcher
```

或安装为项目 Skill：

```bash
mkdir -p .agents/skills
git clone https://github.com/<your-name>/feishu-doc-fetcher.git .agents/skills/feishu-doc-fetcher
```

安装后可以对代理说：

```text
使用 feishu-doc-fetcher 读取这篇飞书文档：https://example.feishu.cn/docx/OdWid6eTHoo4pDxKBllcpef2nrb
```

如果代理没有自动触发，可以显式提到 `$feishu-doc-fetcher`。

## 直接运行脚本

从 URL 中取出 `/docx/` 后面的 document token，例如：

```text
https://example.feishu.cn/docx/OdWid6eTHoo4pDxKBllcpef2nrb
```

对应的 token 是：

```text
OdWid6eTHoo4pDxKBllcpef2nrb
```

使用环境变量运行：

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_DOC_ID="OdWid6eTHoo4pDxKBllcpef2nrb"
export FEISHU_OUTPUT_DIR="./feishu-output"
export FEISHU_MAX_DEPTH="3"

python3 feishu_fetch.py
```

也可以使用命令行参数：

```bash
python3 feishu_fetch.py <app_id> <app_secret> <doc_id> [output_dir] [max_depth]
```

参数说明：

| 参数 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `app_id` | `FEISHU_APP_ID` | 必填 | 飞书应用 ID |
| `app_secret` | `FEISHU_APP_SECRET` | 必填 | 飞书应用密钥 |
| `doc_id` | `FEISHU_DOC_ID` | 必填 | 飞书 docx 文档 token |
| `output_dir` | `FEISHU_OUTPUT_DIR` | `feishu-output/` | Markdown、图片和附件输出目录 |
| `max_depth` | `FEISHU_MAX_DEPTH` | `3` | wiki 子文档递归深度 |

## 输出结果

每篇文档会生成一个 Markdown 文件，并带有 YAML frontmatter：

```yaml
---
title: "文档标题"
document_id: "OdWid6eTHoo4pDxKBllcpef2nrb"
revision_id: "xxx"
fetched_at: "2026-04-27 15:00:00"
depth: 0
source_url: "https://open.feishu.cn/docx/OdWid6eTHoo4pDxKBllcpef2nrb"
---
```

图片和附件会保存在 Markdown 文件旁边：

```text
feishu-output/
├── 文档标题.md
├── images/
│   └── <document_id>/
│       └── <image_token>.png
└── attachments/
    └── <document_id>/
        └── <filename>
```

## 当前限制

- 只处理飞书 docx 文档 token；脚本不会自动解析完整 URL
- 嵌入式电子表格和多维表格目前只保留占位注释，不展开内部数据
- 表格转换面向简单矩形表格，复杂合并单元格可能需要人工校对
- wiki 递归目前只抓取 `obj_type == "docx"` 的子节点
- 下载私有文档需要飞书应用具备对应文档访问权限

## 安全提示

不要把 `FEISHU_APP_SECRET` 写进仓库、README、issue 或日志。建议通过环境变量、本地 secret manager 或 CI secret 注入。

## 参考

- Claude Code Skills: https://docs.claude.com/en/docs/claude-code/skills
- Codex Agent Skills: https://developers.openai.com/codex/skills

## License

MIT
