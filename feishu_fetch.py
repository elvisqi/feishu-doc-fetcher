#!/usr/bin/env python3
"""
Feishu Open Platform API - Document Fetcher

Fetches Feishu documents via API and converts to Markdown.
Supports: text, headings, lists, code blocks, tables, images,
file attachments, embedded sheets/bitables, and wiki children.

Usage:
    python feishu_fetch.py <app_id> <app_secret> <doc_id> [output_dir] [max_depth]
    # Or set env vars: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_DOC_ID
"""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# Configuration (env vars or CLI args override defaults)
# ============================================================
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ROOT_DOCUMENT_ID = os.environ.get("FEISHU_DOC_ID", "")
OUTPUT_DIR = Path(os.environ.get("FEISHU_OUTPUT_DIR", Path(__file__).parent / "feishu-output"))
MAX_DEPTH = int(os.environ.get("FEISHU_MAX_DEPTH", "3"))

FEISHU_HOST = "https://open.feishu.cn"
TOKEN_URL = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
DOCX_BASE = f"{FEISHU_HOST}/open-apis/docx/v1"
DRIVE_BASE = f"{FEISHU_HOST}/open-apis/drive/v1"
WIKI_BASE = f"{FEISHU_HOST}/open-apis/wiki/v2"

# ============================================================
# Token Management
# ============================================================
class TokenManager:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self.expire_time = 0

    def get_token(self):
        if self.token and time.time() < self.expire_time - 300:
            return self.token
        resp = requests.post(TOKEN_URL, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        })
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Failed to get token: {data}")
        self.token = data["tenant_access_token"]
        self.expire_time = time.time() + data.get("expire", 7200)
        print(f"[auth] Got new tenant_access_token")
        return self.token


# ============================================================
# Text Extraction
# ============================================================
def extract_text_from_block(block):
    text_container = None
    for key in block:
        if key in ("text", "heading1", "heading2", "heading3", "heading4",
                    "heading5", "heading6", "heading7", "heading8", "heading9",
                    "bullet", "ordered", "code", "quote", "callout"):
            text_container = block[key]
            break
    if not text_container:
        return ""
    elements = text_container.get("elements", [])
    parts = []
    for elem in elements:
        if "text_run" in elem:
            run = elem["text_run"]
            content = run.get("content", "")
            style = run.get("text_element_style", {})
            if style.get("bold"):
                content = f"**{content}**"
            if style.get("italic"):
                content = f"*{content}*"
            if style.get("inline_code"):
                content = f"`{content}`"
            if style.get("strikethrough"):
                content = f"~~{content}~~"
            if style.get("link"):
                link_url = style["link"].get("url", "")
                if link_url:
                    content = f"[{content}]({link_url})"
            parts.append(content)
        elif "mention_doc" in elem:
            m = elem["mention_doc"]
            parts.append(f"[{m.get('title', 'linked doc')}](feishu://doc/{m.get('obj_token', '')})")
        elif "mention_user" in elem:
            parts.append(elem["mention_user"].get("name", "@user"))
        elif "equation" in elem:
            parts.append(f"${elem['equation'].get('content', '')}$")
    return "".join(parts)


def block_to_markdown(block):
    bt = block.get("block_type")
    text = extract_text_from_block(block)
    lines = []
    if bt == 1:
        pass  # page root
    elif bt == 2:
        if text.strip():
            lines.append(f"{text}\n")
    elif bt in (3, 4, 5, 6, 7, 8, 9, 10, 11):
        level = bt - 2
        lines.append(f"\n{'#' * level} {text}\n")
    elif bt == 12:
        indent = block.get("bullet", {}).get("style", {}).get("indent_level", 0)
        lines.append(f"{'  ' * indent}- {text}\n")
    elif bt == 13:
        indent = block.get("ordered", {}).get("style", {}).get("indent_level", 0)
        lines.append(f"{'  ' * indent}1. {text}\n")
    elif bt == 14:
        lang = block.get("code", {}).get("style", {}).get("language", "")
        lines.append(f"\n```{lang}\n{text}\n```\n")
    elif bt == 15:
        lines.append(f"\n> {text}\n")
    elif bt == 17:
        lines.append("\n---\n")
    elif bt == 27:
        token = block.get("image", {}).get("token", "")
        lines.append(f"\n![image:{token}]()\n")
    elif bt == 23:
        f = block.get("file", {})
        lines.append(f"\n📎 **[{f.get('name', 'file')}](file:{f.get('token', '')})**\n")
    elif bt == 30:
        lines.append(f"\n<!-- EMBEDDED SHEET: {block.get('sheet', {}).get('token', '')} -->\n")
    elif bt == 31:
        lines.append("\n<!-- TABLE_START -->\n")
    elif bt == 32:
        pass  # table cell
    elif bt == 33:
        pass  # view
    elif bt == 43:
        lines.append(f"\n<!-- EMBEDDED BOARD: {block.get('board', {}).get('token', '')} -->\n")
    else:
        lines.append(f"\n<!-- unknown_type_{bt} -->\n")
        if text.strip():
            lines.append(f"{text}\n")
    return lines


# ============================================================
# Feishu API Client
# ============================================================
class FeishuClient:
    def __init__(self, token_manager):
        self.tm = token_manager
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        self.session.mount("https://", adapter)

    def _headers(self):
        return {"Authorization": f"Bearer {self.tm.get_token()}"}

    def _get(self, url, params=None):
        time.sleep(0.5)
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            print(f"  [api warn] code={data.get('code')} msg={data.get('msg')}")
        return data

    def get_document_meta(self, document_id):
        return self._get(f"{DOCX_BASE}/documents/{document_id}")

    def get_all_blocks(self, document_id):
        all_blocks = []
        page_token = None
        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            data = self._get(f"{DOCX_BASE}/documents/{document_id}/blocks", params)
            items = data.get("data", {}).get("items", [])
            all_blocks.extend(items)
            page_token = data.get("data", {}).get("has_more") and data["data"].get("page_token")
            if not page_token:
                break
            time.sleep(0.15)
        return all_blocks

    def download_image(self, image_token, output_path):
        url = f"{DRIVE_BASE}/medias/{image_token}/download"
        resp = self.session.get(url, headers=self._headers(), stream=True, timeout=60)
        if resp.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
        return None

    def download_file(self, file_token, output_path):
        url = f"{DRIVE_BASE}/medias/{file_token}/download"
        resp = self.session.get(url, headers=self._headers(), stream=True, timeout=60)
        if resp.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
        return None

    def get_wiki_node(self, obj_type, obj_token):
        return self._get(f"{WIKI_BASE}/spaces/get_node",
                         params={"obj_type": obj_type, "obj_token": obj_token})

    def get_wiki_children(self, space_id, node_token):
        return self._get(f"{WIKI_BASE}/spaces/{space_id}/nodes/{node_token}/children")


# ============================================================
# Document Fetcher
# ============================================================
class DocumentFetcher:
    def __init__(self, client, output_dir, max_depth):
        self.client = client
        self.output_dir = Path(output_dir)
        self.max_depth = max_depth
        self.visited_docs = set()
        self.stats = {
            "docs_fetched": 0, "blocks_processed": 0,
            "images_found": 0, "files_found": 0,
            "sheets_found": 0, "bitables_found": 0,
            "tables_found": 0, "child_docs_found": 0, "errors": 0,
        }

    def fetch_all(self, document_id, depth=0, parent_path=""):
        indent = "  " * depth
        label = document_id[:20] + "..." if len(document_id) > 20 else document_id

        if document_id in self.visited_docs:
            print(f"{indent}[skip] Already visited: {label}")
            return None
        if depth > self.max_depth:
            print(f"{indent}[skip] Max depth reached: {label}")
            return None

        self.visited_docs.add(document_id)

        print(f"{indent}[fetch] Document: {label} (depth={depth})")
        try:
            meta = self.client.get_document_meta(document_id)
        except Exception as e:
            print(f"{indent}[error] Meta failed: {e}")
            self.stats["errors"] += 1
            return None

        doc_info = meta.get("data", {}).get("document", {})
        title = doc_info.get("title", "Untitled")
        revision_id = doc_info.get("revision_id", "")

        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100] or f"doc_{document_id}"
        doc_path = self.output_dir / parent_path / f"{safe_title}.md" if parent_path \
            else self.output_dir / f"{safe_title}.md"

        print(f"{indent}[blocks] {title[:50]}")
        blocks = self.client.get_all_blocks(document_id)
        self.stats["docs_fetched"] += 1
        self.stats["blocks_processed"] += len(blocks)
        print(f"{indent}  -> {len(blocks)} blocks")

        block_map = {b["block_id"]: b for b in blocks}

        # Collect table descendant IDs to skip
        table_descendants = set()
        for b in blocks:
            if b.get("block_type") == 31:
                self._collect_descendants(b["block_id"], block_map, table_descendants)

        markdown_parts = []
        image_tokens = []
        file_tokens = []
        table_blocks = []

        for block in blocks:
            bt = block.get("block_type")
            bid = block.get("block_id", "")

            if bt == 31:
                table_blocks.append((block, block.get("children", [])))
                self.stats["tables_found"] += 1
                markdown_parts.append("\n<!-- TABLE_START -->\n")
                continue
            if bid in table_descendants:
                continue

            if bt == 27:
                t = block.get("image", {}).get("token", "")
                if t:
                    image_tokens.append(t)
                    self.stats["images_found"] += 1
            elif bt == 23:
                f = block.get("file", {})
                t = f.get("token", "")
                if t:
                    file_tokens.append((t, f.get("name", "file")))
                    self.stats["files_found"] += 1
            elif bt == 30:
                t = block.get("sheet", {}).get("token", "")
                if t:
                    self.stats["sheets_found"] += 1
            elif bt == 43:
                self.stats["bitables_found"] += 1

            markdown_parts.extend(block_to_markdown(block))

        # Process tables
        full_md = "\n".join(markdown_parts)
        for table_block, cell_ids in table_blocks:
            table_md = self._process_table(table_block, cell_ids, block_map)
            full_md = full_md.replace("<!-- TABLE_START -->", table_md, 1)

        # Download images
        if image_tokens:
            img_dir = doc_path.parent / "images" / document_id
            img_dir.mkdir(parents=True, exist_ok=True)
            for t in image_tokens:
                try:
                    p = img_dir / f"{t}.png"
                    r = self.client.download_image(t, p)
                    if r:
                        full_md = full_md.replace(
                            f"![image:{t}]()", f"![image](images/{document_id}/{t}.png)")
                        print(f"{indent}  [img] {t}")
                    else:
                        self.stats["errors"] += 1
                except Exception as e:
                    print(f"{indent}  [img error] {t}: {e}")
                    self.stats["errors"] += 1

        # Download files
        if file_tokens:
            file_dir = doc_path.parent / "attachments" / document_id
            file_dir.mkdir(parents=True, exist_ok=True)
            for ftoken, fname in file_tokens:
                try:
                    fpath = file_dir / fname
                    r = self.client.download_file(ftoken, fpath)
                    if r:
                        full_md = full_md.replace(
                            f"(file:{ftoken})", f"(attachments/{document_id}/{fname})")
                        print(f"{indent}  [file] {fname} ({os.path.getsize(fpath)} bytes)")
                    else:
                        self.stats["errors"] += 1
                except Exception as e:
                    print(f"{indent}  [file error] {ftoken}: {e}")
                    self.stats["errors"] += 1

        # Write
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        feishu_url = f"https://open.feishu.cn/docx/{document_id}"
        frontmatter = f"""---
title: "{title}"
document_id: "{document_id}"
revision_id: "{revision_id}"
fetched_at: "{time.strftime('%Y-%m-%d %H:%M:%S')}"
depth: {depth}
source_url: "{feishu_url}"
---

"""
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + full_md)
        print(f"{indent}[saved] {doc_path}")

        # Wiki children
        if depth < self.max_depth:
            self._fetch_wiki_children(document_id, depth + 1, parent_path)

        return doc_path

    def _fetch_wiki_children(self, doc_id, depth, parent_path):
        indent = "  " * depth
        try:
            node = self.client.get_wiki_node("docx", doc_id)
            if node.get("code") != 0:
                return
            info = node.get("data", {}).get("node", {})
            space_id = info.get("space_id", "")
            node_token = info.get("node_token", "")
            if not space_id or not node_token:
                return

            children = self.client.get_wiki_children(space_id, node_token)
            if children.get("code") != 0:
                return

            items = children.get("data", {}).get("items", [])
            if not items:
                return

            print(f"{indent}[wiki] {len(items)} children")
            for item in items:
                ct = item.get("node_token", "")
                if ct:
                    print(f"{indent}  [child] {item.get('title', '?')} ({item.get('obj_type', '?')})")
                    self.stats["child_docs_found"] += 1
                    if item.get("obj_type") == "docx":
                        self.fetch_all(ct, depth,
                                       f"{parent_path}/{doc_id}" if parent_path else doc_id)
        except Exception:
            pass

    def _collect_descendants(self, block_id, block_map, visited):
        if block_id in visited:
            return
        visited.add(block_id)
        b = block_map.get(block_id)
        if b:
            for c in b.get("children", []):
                self._collect_descendants(c, block_map, visited)

    def _process_table(self, table_block, cell_ids, block_map):
        prop = table_block.get("table", {}).get("property", {})
        cols = prop.get("column_size", 0)
        rows = prop.get("row_size", 0)
        if cols == 0 or not cell_ids:
            return "\n<!-- TABLE: no data -->\n"

        texts = []
        for cid in cell_ids:
            c = block_map.get(cid)
            texts.append(extract_text_from_block(c).strip() if c else "")

        grid = [["" for _ in range(cols)] for _ in range(rows)]
        for i, t in enumerate(texts):
            r, c = i // cols, i % cols
            if r < rows and c < cols:
                grid[r][c] = t

        lines = [""]
        lines.append("| " + " | ".join(
            h.strip() if h.strip() else " " for h in grid[0]) + " |")
        lines.append("| " + " | ".join(["---"] * cols) + " |")
        for row in grid[1:]:
            lines.append("| " + " | ".join(
                c.strip().replace("\n", "<br>") if c.strip() else " " for c in row) + " |")
        lines.append("")
        return "\n".join(lines)


# ============================================================
# Main
# ============================================================
def main():
    # CLI args override env vars
    args = sys.argv[1:]
    app_id = args[0] if len(args) > 0 else APP_ID
    app_secret = args[1] if len(args) > 1 else APP_SECRET
    doc_id = args[2] if len(args) > 2 else ROOT_DOCUMENT_ID
    out_dir = args[3] if len(args) > 3 else OUTPUT_DIR
    max_depth = int(args[4]) if len(args) > 4 else MAX_DEPTH

    if not app_id or not app_secret or not doc_id:
        print("Usage: python feishu_fetch.py <app_id> <app_secret> <doc_id> [output_dir] [max_depth]")
        print("Or set env vars: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_DOC_ID")
        print()
        print("Required API permissions:")
        print("  docx:document:readonly  - read document content")
        print("  drive:drive:readonly    - download images & attachments")
        print("  wiki:wiki:readonly      - follow wiki children (optional)")
        sys.exit(1)

    print("=" * 60)
    print(f"Feishu Document Fetcher")
    print(f"  Doc: {doc_id}")
    print(f"  Max depth: {max_depth}")
    print("=" * 60)

    tm = TokenManager(app_id, app_secret)
    client = FeishuClient(tm)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    fetcher = DocumentFetcher(client, out_dir, max_depth)
    start = time.time()
    fetcher.fetch_all(doc_id)

    print("\n" + "=" * 60)
    print("Complete")
    print("=" * 60)
    for k, v in fetcher.stats.items():
        print(f"  {k:20s}: {v}")
    print(f"  {'time (s)':20s}: {time.time() - start:.1f}")
    print(f"  {'output dir':20s}: {Path(out_dir)}")


if __name__ == "__main__":
    main()
