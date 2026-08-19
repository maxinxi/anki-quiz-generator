#!/usr/bin/env python3
"""
从 Anki 导出 txt 生成 .apkg（基于猪猪模板 V10）
================================================

用法：
    pip install genanki
    python gen_anki_from_txt.py 导出的题库.txt 输出.apkg

txt 格式：Anki 导出（#separator:tab + #html:true），
从 <div id="Question"> / <ul id="ol"> / <div id="showAnswer"> 提取数据。
"""

import html
import os
import random
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from anki_template_v10 import (
    create_model, build_options_html, build_judge_options_html,
    build_baoming_html, convert_answer, esc,
)
import genanki

DECK_ID = 1837002000
DECK_NAME = "安全督查+"


def parse_txt_options(opt_str):
    """解析选项字符串，返回 [(letter, text), ...]
    处理三种格式：
    1. *** 分隔：8***9***10***12
    2. *** 分隔但带前缀：A.xxx***B.xxx***C.xxx***D.xxx
    3. 单段但内含多个选项：1月底前 B.6月底前 C.9月底前 D.12月底前
    """
    if not opt_str or not str(opt_str).strip():
        return []
    text = str(opt_str).strip()
    parts = [p.strip() for p in text.split("***") if p.strip()]
    if len(parts) == 1:
        if re.search(r"[B-Z][\.、\s]", parts[0]):
            sub_parts = re.split(r"(?=[A-Z][\.、\s])", parts[0])
            parts = [p.strip() for p in sub_parts if p.strip()]
    result = []
    for i, part in enumerate(parts):
        m = re.match(r"^([A-Z])[\.、\-]\s*(.*)", part)
        if m:
            text_clean = m.group(2).strip()
        else:
            m2 = re.match(r"^([A-Z])\s+(.*)", part)
            text_clean = m2.group(2).strip() if m2 else part.strip()
        if text_clean:
            result.append((chr(65 + i), text_clean))
    return result


def extract_questions(txt_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    content_clean = content.replace('""', '"')
    questions = re.findall(r'id="Question"[^>]*>(.*?)</div>', content_clean, re.DOTALL)
    options_raw = re.findall(r'id="ol"[^>]*>(.*?)</ul>', content_clean, re.DOTALL)
    answers_raw = re.findall(r'id="showAnswer"[^>]*>([^<]*)</div>', content_clean, re.DOTALL)
    questions_front = questions[0::2]
    options_front = options_raw[0::2]
    answers_front = answers_raw[0::2]
    results = []
    for i in range(len(questions_front)):
        q = questions_front[i].strip()
        opts_raw = options_front[i].strip()
        ans = answers_front[i].strip()
        opts = parse_txt_options(opts_raw)
        results.append((q, opts, ans))
    return results


def main():
    txt_path = sys.argv[1] if len(sys.argv) > 1 else "安全督查+.txt"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output.apkg"
    questions = extract_questions(txt_path)
    print(f"提取到 {len(questions)} 道题")
    judge_count = single_count = multi_count = 0
    model = create_model()
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    for idx, (question, options, answer) in enumerate(questions):
        if not options:
            continue
        is_judge = (len(options) == 2
                    and options[0][1].strip().upper() in ("A", "正确", "对", "TRUE", "T")
                    and options[1][1].strip().upper() in ("B", "错误", "错", "FALSE", "F"))
        if len(options) == 2 and options[0][1] == "A" and options[1][1] == "B":
            is_judge = True
        ans_letters = convert_answer(answer)
        is_multi = len(ans_letters) > 1
        if is_judge:
            judge_count += 1
            opts_html = build_judge_options_html()
            updated_answer = ans_letters
        else:
            if is_multi:
                multi_count += 1
            else:
                single_count += 1
            opt_str = "; ".join(f"{letter}. {text}" for letter, text in options)
            opts_html, letter_map = build_options_html(opt_str, is_multi=is_multi)
            updated_answer = "".join(letter_map.get(c, c) for c in ans_letters)
        note = genanki.Note(
            model=model,
            fields=[esc(question), opts_html, updated_answer, "", build_baoming_html(False), "", "", "", ""],
            guid=genanki.guid_for("aqzl", question, answer),
        )
        deck.add_note(note)
    print(f"判断题:{judge_count} 单选:{single_count} 多选:{multi_count} 总计:{judge_count + single_count + multi_count}")
    genanki.Package(deck).write_to_file(output_path)
    print(f"生成完成: {output_path}")


if __name__ == "__main__":
    main()
