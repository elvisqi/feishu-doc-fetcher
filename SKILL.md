---
name: feishu-doc-fetcher
description: Fetch, read, or download Feishu (飞书) docx content through the Feishu Open Platform API and convert it to local Markdown. Use when the user provides a Feishu document URL or document token and wants an AI agent to retrieve document text, headings, lists, code blocks, tables, images, attachments, or nested wiki child documents for Claude Code or Codex workflows.
---

# Feishu Document Fetcher

Use the bundled `feishu_fetch.py` script to fetch Feishu docx documents through the Feishu Open Platform API and save them as local Markdown with downloaded images and attachments.

## Workflow

1. Ask for or locate the required Feishu app credentials: `FEISHU_APP_ID` and `FEISHU_APP_SECRET`.
2. Extract the docx token from the shared URL, for example `https://example.feishu.cn/docx/OdWid6eTHoo4pDxKBllcpef2nrb` -> `OdWid6eTHoo4pDxKBllcpef2nrb`.
3. Run `feishu_fetch.py` from this skill directory or with an absolute path.
4. Read the generated Markdown file from the output directory before answering questions about the document.

## Prerequisites

The user must provide either a Feishu docx URL or a docx document token, plus Feishu app credentials.

Required API permissions on the Feishu app:

- `docx:document:readonly` — read document content
- `drive:drive:readonly` — download images & attachments
- `wiki:wiki:readonly` — follow wiki children (optional)

The Python runtime needs `requests` installed.

## Usage

### Via Environment Variables

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_DOC_ID="OdWid6eTHoo4pDxKBllcpef2nrb"
python3 feishu_fetch.py
```

### Via CLI Arguments

```bash
python3 feishu_fetch.py <app_id> <app_secret> <doc_id> [output_dir] [max_depth]
```

### Parameters

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| app_id | FEISHU_APP_ID | (required) | Feishu app ID |
| app_secret | FEISHU_APP_SECRET | (required) | Feishu app secret |
| doc_id | FEISHU_DOC_ID | (required) | Document ID (from URL path) |
| output_dir | FEISHU_OUTPUT_DIR | `feishu-output/` | Output directory for Markdown + assets |
| max_depth | FEISHU_MAX_DEPTH | `3` | Wiki child recursion depth |

## Script Location

`feishu_fetch.py` is bundled next to this `SKILL.md` file. If the current working directory is not the skill directory, run it with an absolute path.

## What It Fetches

| Content Type | Handling |
|--------------|----------|
| Text paragraphs | Markdown paragraphs |
| Headings (H1-H9) | `#` through `#########` |
| Bullet/ordered lists | `-` and `1.` with indent |
| Code blocks | ` ```lang ` fenced blocks |
| Blockquotes | `> ` prefix |
| Tables | Markdown tables with proper columns |
| Images | Downloaded to `images/{doc_id}/{token}.png` |
| File attachments | Downloaded to `attachments/{doc_id}/{name}` |
| Embedded sheets | Placeholder comment with token |
| Wiki children | Recursively fetched up to `max_depth` |

## Current Limits

- The script fetches Feishu docx documents by token; extract the token from URLs before running.
- Embedded sheets and boards are detected but not expanded into full sheet or bitable content.
- Table conversion assumes a simple rectangular table grid.
- Only nested wiki child nodes with `obj_type == "docx"` are recursively fetched.

## Output Format

Each document produces:

- One `.md` file with YAML frontmatter (`title`, `document_id`, `source_url`, etc.)
- `images/{doc_id}/` directory with downloaded PNGs
- `attachments/{doc_id}/` directory with downloaded files

## Notes

- The script auto-manages tenant access tokens with refresh
- Rate limiting (500ms between requests) reduces throttling risk
- HTTP retries handle transient network errors
- Already-visited documents are skipped to avoid infinite loops
