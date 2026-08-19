# anki-quiz-generator

将题库文件（Excel / Anki 导出 txt / 结构化 JSON）生成为可导入 Anki 的 `.apkg` 卡片包。卡片模板为「猪猪模板升级版 V10」交互式答题卡：点选选项 → 点任意处显示答案 → 自动判对错、高亮正确答案 → 点击进入下一题。

## ✨ 特性

- **三种数据源**：Excel（.xlsx）、Anki 导出文本（.txt）、结构化 JSON（支持图片引用）
- **两种乱序模式**
  - 静态乱序（默认）：生成时打乱选项 + 答案字母同步重标（可固定 seed 复现）
  - 动态乱序（`--dynamic`）：卡片 JS 每次显示随机重排选项，翻面顺序一致
- **判断题固定** `A. 正确 / B. 错误`，不打乱
- **图片内嵌**：题干图/选项图自动下载打包（离线可看），水印类图片自动剔除，图片自适应 CSS（含夜间模式）
- **保命题徽章**：Excel 备注列含"保命题"等关键词自动标记 🔴
- **解析/依据/答题技巧**：答案面展示，支持判断题"错误说法/正确说法"
- 夜间模式、换卡检测、点击任意处翻面/下一题，兼容 Anki Desktop 与 AnkiDroid

## 📦 安装

```bash
pip install genanki openpyxl
```

## 🚀 快速开始

### 从 Excel 生成（自动按题型拆 3 个 apkg）

```bash
python scripts/gen_anki_from_excel.py 你的题库.xlsx
```

Excel 列名要求：`题型`（单选题/多选题/判断题）、`题干`、`选项`（换行分隔 A.xxx\nB.xxx）、`答案`（D 或 ABD 或 正确）；可选：`题目依据`（解析）、`备注`（含"保命题"则标记）、`判断题解析`。

### 从 Anki 导出 txt 生成

```bash
python scripts/gen_anki_from_txt.py 导出的题库.txt 输出.apkg
```

### 从 JSON 生成（支持图片 + 子卡组 + 动态乱序）

```bash
python scripts/gen_anki_from_json.py 题库.json --image-root http://图片服务/images/ --dynamic
```

JSON 格式：

```json
[
  {
    "title": "题干文本",
    "type": "单选题",
    "questionCode": "题目编码（可选）",
    "questionImagePath": "题干图片引用（可选）",
    "options": [
      {"text": "选项A", "isCorrect": false, "imagePath": "引用（可选）"},
      {"text": "选项B", "isCorrect": true}
    ],
    "answer": "B",
    "analysis": "解析（可选）",
    "references": ["依据（可选）"]
  }
]
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--dynamic` | 启用 JS 每次显示随机乱序 |
| `--split` | 按题型拆分多个 apkg（默认单包含子卡组） |
| `--deck-prefix 题库` | 卡组名前缀 |
| `--image-root URL` | 图片服务地址 |
| `--cache-dir 目录` | 图片本地缓存目录 |

## 📁 目录结构

```
anki-quiz-generator/
├── README.md
├── SKILL.md                    # 技能说明（供 AI Agent 使用）
└── scripts/
    ├── anki_template_v10.py    # V10 模板模块（CSS/QFMT/AFMT/构建函数）
    ├── gen_anki_from_excel.py  # Excel 数据源
    ├── gen_anki_from_txt.py    # Anki 导出 txt 数据源
    └── gen_anki_from_json.py   # JSON 数据源（图片/子卡组/动态乱序）
```

## 📝 卡片模板说明（V10，9 字段）

| 字段 | 内容 |
|---|---|
| Question | 题干 HTML（可含图） |
| OptionsHTML | 预渲染选项 HTML（li 带 value/data-correct） |
| Answer | 正确答案字母 |
| Remark | 纯文本解析 |
| IsBaoMing | 保命题徽章 |
| RemarkHTML | 格式化解析（可含依据） |
| WrongPointHTML / RightPointHTML | 判断题 错误/正确 说法 |
| HintHTML | 答题技巧（答案面） |

两种乱序的选择：

- 默认**静态乱序**：选项顺序生成时打乱并写死，所有设备/重装后顺序一致
- `--dynamic` **动态乱序**：每次出现题目由 JS 重新随机，翻面顺序保持一致（判断题除外）

## 🔍 验证

```python
import zipfile, sqlite3
with zipfile.ZipFile('输出.apkg') as z:
    z.extractall('/tmp/check')
conn = sqlite3.connect('/tmp/check/collection.anki2')
print(conn.execute("SELECT count(*) FROM notes").fetchone())
```

## 📄 License

MIT（添加你自己的版权信息后发布）。
