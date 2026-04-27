---
name: feishu-doc-fetcher
description: Use when the user wants to fetch, read, or download content from a Feishu (飞书) document via the Open Platform API. Supports text, headings, lists, code blocks, tables, images, file attachments (Excel, SQL), and nested wiki documents up to a configurable depth.
---

# Feishu Document Fetcher

Fetches complete Feishu document content via the Open Platform API and converts it to local Markdown with downloaded images and attachments.

## When to Use

- User shares a Feishu docx URL and wants its contents read/downloaded
- User wants to extract tables, images, or attachments from a Feishu document
- User needs to follow embedded/nested Feishu documents (wiki children)

## Prerequisites

The user must provide:
1. **Feishu document URL** (e.g., `https://baitedafeishu.feishu.cn/docx/OdWid6eTHoo4pDxKBllcpef2nrb`)
2. **APP_ID** and **APP_SECRET** for the Feishu app (or have them set as env vars)

Required API permissions on the Feishu app:
- `docx:document:readonly` — read document content
- `drive:drive:readonly` — download images & attachments
- `wiki:wiki:readonly` — follow wiki children (optional)

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

`feishu_fetch.py` is located at:
- `.wiki-tmp/feishu_fetch.py` (project-local copy)

If the script is not found in the current project, check the user's typical location or re-create it from this skill's reference.

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

## Output Format

Each document produces:
- One `.md` file with YAML frontmatter (`title`, `document_id`, `source_url`, etc.)
- `images/{doc_id}/` directory with downloaded PNGs
- `attachments/{doc_id}/` directory with downloaded files

## Notes

- The script auto-manages tenant access tokens with refresh
- Rate limiting (500ms between requests) prevents throttling
- HTTP retries handle transient network errors
- Already-visited documents are skipped to avoid infinite loops
