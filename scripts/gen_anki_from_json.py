#!/usr/bin/env python3
"""
从结构化 JSON 题库生成 Anki .apkg（基于猪猪模板 V10）
======================================================

用法：
    pip install genanki
    python gen_anki_from_json.py 题库.json [输出.apkg] [--image-root URL] [--dynamic] [--split]

JSON 格式（数组，每项一个题目）：
    [
      {
        "title": "题干文本",
        "type": "单选题" | "多选题" | "判断题",      # 或 typeCode: "1004"/"1005"/"1006"
        "questionCode": "题目编码（可选，用于稳定种子/guid）",
        "questionImagePath": "题干图片引用（可选）",
        "options": [
          {"text": "选项文本", "isCorrect": true/false, "imagePath": "选项图片引用（可选）"}
        ],
        "answer": "D.专人;",           # 备用；优先用 options[].isCorrect
        "analysis": "解析文本（可选）",
        "references": ["依据1", "依据2"]   # 可选
      }
    ]

特性：
    * 单选/多选：默认静态乱序（--dynamic 切换为 JS 每次显示乱序）
    * 判断题：固定 A.正确 / B.错误，不打乱
    * 图片：题干图/选项图自动下载并内嵌；同题选项引用全部相同时判定为水印图并跳过
    * 默认生成一个 apkg（父卡组 + 单选题/多选题/判断题子卡组）；--split 则按题型拆成 3 个文件
"""

import argparse
import hashlib
import html
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import genanki
from anki_template_v10 import (
    create_model, esc, build_remark_html, build_baoming_html,
    build_wrong_point_html, build_right_point_html, convert_answer,
)

MODEL_ID = 1610001234
DECK_ID_BASE = 1610002000
DEFAULT_IMAGE_ROOT = "http://127.0.0.1:8787/images/"  # 按需改为实际图片服务地址

TYPE_MAP = {"1004": "单选题", "1005": "多选题", "1006": "判断题"}


def qtype(q):
    t = q.get("type") or TYPE_MAP.get(str(q.get("typeCode", "")), "")
    return t if t in ("单选题", "多选题", "判断题") else "单选题"


# ── 图片下载 ──────────────────────────────────────────────

def image_ext(content_type, payload):
    ct = (content_type or "").split(";", 1)[0].lower()
    table = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
             "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp"}
    if ct in table:
        return table[ct]
    if payload.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    return None


def fetch_image(root, ref):
    if not ref or not str(ref).strip():
        return None
    url = root.rstrip("/") + "/" + urllib.parse.quote(str(ref).strip(), safe="")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AnkiQuizGenerator/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()
        ext = image_ext(resp.headers.get("Content-Type", ""), payload)
        if ext is None or len(payload) < 128:
            return None
        fname = "img_" + hashlib.sha1(str(ref).encode("utf-8")).hexdigest()[:20] + "." + ext
        return (str(ref), fname, payload)
    except Exception:
        return None


def download_images(refs, root, cache_dir):
    """并发下载图片引用并落盘；返回 {ref: (fname, 磁盘路径)}。"""
    import tempfile
    os.makedirs(cache_dir, exist_ok=True) if cache_dir else None
    work_dir = cache_dir or tempfile.mkdtemp(prefix="anki_media_")
    result = {}
    todo = list(refs)
    done = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_image, root, ref): ref for ref in todo}
        for fut in as_completed(futures):
            done += 1
            got = fut.result()
            if got:
                ref, fname, payload = got
                path = os.path.join(work_dir, fname)
                with open(path, "wb") as f:
                    f.write(payload)
                result[ref] = (fname, path)
            if done % 100 == 0 or done == len(todo):
                print(f"  图片 {done}/{len(todo)}，有效 {len(result)}")
    return result


# ── 题目构建 ──────────────────────────────────────────────

def collect_refs(questions):
    """收集需下载的引用：题干图总是需要；选项图仅当同题选项引用不完全相同时（剔除水印）。"""
    refs = set()
    for q in questions:
        stem = str(q.get("questionImagePath") or "").strip()
        if stem:
            refs.add(stem)
        opt_refs = [str(o.get("imagePath") or "").strip() for o in (q.get("options") or [])]
        real = [r for r in opt_refs if r]
        if real and len(set(real)) > 1:
            refs.update(real)
    return refs


def build_note(model, q, media, dynamic):
    """构建 genanki.Note。media: {ref: (fname, payload)}。"""
    is_judge = qtype(q) == "判断题"
    fields = ["", "", "", "", "", "", "", "", ""]  # 9 字段

    # 题干 + 题干图
    stem_img = ""
    stem_ref = str(q.get("questionImagePath") or "").strip()
    if stem_ref and stem_ref in media:
        stem_img = f'<img src="{media[stem_ref][0]}" alt="题干图">'
    fields[0] = esc(q.get("title")) + stem_img

    # 选项
    if is_judge:
        from anki_template_v10 import build_judge_options_html
        fields[1] = build_judge_options_html()
        raw = str(q.get("answer") or "").upper()
        fields[2] = "A" if (raw.startswith("A") or "正确" in raw) else "B"
        for o in (q.get("options") or []):
            if o.get("isCorrect") and "正确" in str(o.get("text") or ""):
                fields[2] = "A"
            elif o.get("isCorrect"):
                fields[2] = "B"
    else:
        options = list(q.get("options") or [])
        opt_refs = [str(o.get("imagePath") or "").strip() for o in options]
        real_refs = [r for r in opt_refs if r]
        show_opt_img = bool(real_refs) and len(set(real_refs)) > 1

        if dynamic:
            # 动态乱序：选项保持原序存储，JS 每次显示随机重排
            order = list(options)
            letters = [chr(65 + i) for i in range(len(order))]
            answer = "".join(chr(65 + i) for i, o in enumerate(order) if o.get("isCorrect"))
        else:
            # 静态乱序：生成时打乱 + 重标
            seed = int(hashlib.sha1(str(q.get("questionCode") or q.get("title")).encode("utf-8")).hexdigest()[:8], 16)
            rng = random.Random(seed)
            orig = [str(o.get("text") or "").strip() for o in options]
            for _ in range(50):
                rng.shuffle(options)
                if [str(o.get("text") or "").strip() for o in options] != orig:
                    break
            letters = [chr(65 + i) for i in range(len(options))]
            answer = "".join(chr(65 + i) for i, o in enumerate(options) if o.get("isCorrect"))
            if not answer:
                raw = str(q.get("answer") or "").upper()
                answer = "".join(sorted(set(c for c in raw if "A" <= c <= "Z")))

        input_type = "checkbox" if qtype(q) == "多选题" else "radio"
        parts = []
        for i, o in enumerate(options):
            letter = letters[i]
            correct_flag = "1" if o.get("isCorrect") else "0"
            ref = str(o.get("imagePath") or "").strip()
            opt_img = ""
            if show_opt_img and ref and ref in media:
                opt_img = f'<img src="{media[ref][0]}" alt="选项图">'
            onchange = "onCheckChange(this)" if input_type == "checkbox" else "onRadioChange(this)"
            parts.append(
                f'<li value="{letter}" data-correct="{correct_flag}" onclick="clickLi(this)">'
                f'<input type="{input_type}" name="options" class="options" value="{letter}" id="{letter}" onchange="{onchange}">'
                f'<label for="{letter}" class="optionSpan">{esc(o.get("text"))}{opt_img}</label></li>'
            )
        fields[1] = "\n".join(parts)
        fields[2] = answer

    # 解析 / 依据
    analysis = str(q.get("analysis") or "").strip()
    fields[3] = analysis
    refs_html = ""
    references = [str(r).strip() for r in (q.get("references") or []) if str(r).strip()]
    remark_parts = []
    if analysis:
        remark_parts.append(build_remark_html(analysis))
    if references:
        remark_parts.append(f'<div class="remark-box">📖 <strong>依据：</strong>{"<br>".join(esc(r) for r in references)}</div>')
    fields[5] = "\n".join(remark_parts)

    # 判断题 错误/正确说法
    if is_judge:
        judge_analysis = analysis
        fields[6] = build_wrong_point_html(q.get("title"), judge_analysis)
        fields[7] = build_right_point_html(judge_analysis)

    note = genanki.Note(
        model=model,
        fields=fields,
        guid=genanki.guid_for("aqz", q.get("questionCode") or q.get("title"), fields[2]),
    )
    return note


# ── 主流程 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JSON 题库 → Anki .apkg")
    parser.add_argument("source", help="题库 JSON 文件")
    parser.add_argument("output", nargs="?", default="output.apkg", help="输出 .apkg")
    parser.add_argument("--image-root", default=DEFAULT_IMAGE_ROOT, help="图片服务地址")
    parser.add_argument("--dynamic", action="store_true", help="启用 JS 每次显示动态乱序")
    parser.add_argument("--split", action="store_true", help="按题型拆分为多个 apkg")
    parser.add_argument("--deck-prefix", default="题库", help="卡组名前缀")
    parser.add_argument("--cache-dir", default=None, help="图片缓存目录")
    args = parser.parse_args()

    questions = json.load(open(args.source, encoding="utf-8-sig"))
    print(f"题库：{len(questions)} 题")

    refs = collect_refs(questions)
    if refs:
        print(f"下载图片引用 {len(refs)} 个…")
        media = download_images(refs, args.image_root, args.cache_dir)
        print(f"图片有效 {len(media)} 张")
    else:
        media = {}

    model = create_model(dynamic=args.dynamic)
    by_type = {}
    for q in questions:
        by_type.setdefault(qtype(q), []).append(q)

    if args.split:
        deck_ids = {"单选题": 1, "多选题": 2, "判断题": 3}
        for t, qs in by_type.items():
            if not qs:
                continue
            deck = genanki.Deck(DECK_ID_BASE + deck_ids[t], f"{args.deck_prefix}-{t}")
            for q in qs:
                deck.add_note(build_note(model, q, media, args.dynamic))
            pkg = genanki.Package(deck)
            if media:
                pkg.media_files = [p for _, p in media.values()]
            path = f"{args.deck_prefix}-{t}.apkg"
            pkg.write_to_file(path)
            print(f"✅ {path}: {len(qs)} 题")
    else:
        # 单 apkg 多卡组：卡组名用 "父::子"，Anki 导入时自动建立层级
        sub_decks = []
        for t, qs in by_type.items():
            if not qs:
                continue
            sub = genanki.Deck(DECK_ID_BASE + {"单选题": 1, "多选题": 2, "判断题": 3}[t], f"{args.deck_prefix}::{t}")
            for q in qs:
                sub.add_note(build_note(model, q, media, args.dynamic))
            sub_decks.append(sub)
        pkg = genanki.Package(sub_decks)
        if media:
            pkg.media_files = [p for _, p in media.values()]
        out = args.output if args.output != "output.apkg" else f"{args.deck_prefix}.apkg"
        pkg.write_to_file(out)
        print(f"✅ {out}: {len(questions)} 题（{', '.join(f'{t} {len(qs)}' for t, qs in by_type.items())}）")


if __name__ == "__main__":
    main()
