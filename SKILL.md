---
name: anki-quiz-generator
description: 将题库文件（Excel / Anki 导出 txt / 结构化 JSON）生成为 .apkg Anki 卡片包。支持 V10 交互模板（猪猪模板升级版）、选项静态乱序或 JS 动态乱序、图片内嵌、保命题徽章。触发词：生成 Anki、做成 apkg、弄成卡片、帮我做题库；也适用于修复已生成的 apkg 问题。
---

# Anki 题库生成器 Skill（anki-quiz-generator）

> 将题库文件生成为可导入 Anki 的 `.apkg` 卡片包，模板为「猪猪模板升级版 V10」交互式答题卡。
> 触发：用户上传题库文件并说"生成 Anki""做成 apkg""弄成卡片""帮我做题库"。
> 也适用于修复已生成的 apkg 问题（选项未打乱、带 ABCD 前缀、缺少保命题标记、乱序后答案对不上）。

## 一、工作流概览

```
用户上传题库文件 → 判断数据源类型 → 选择生成脚本 → 生成 .apkg → 验证 → 交付
```

### 步骤 1：判断数据源类型

| 数据源 | 标志 | 脚本 | 可识别字段（按需） |
|---|---|---|---|
| Excel (.xlsx) | 表格结构，有列头 | `gen_anki_from_excel.py` | 题干、选项、答案（必备）；解析、技巧、保命题、判断题解析（有则识别，无则跳过） |
| Anki 导出文本 (.txt) | `#separator:tab` + `#html:true` 头 | `gen_anki_from_txt.py` | 题干、选项、答案（必备）；解析、技巧（有则识别，无则跳过） |
| 结构化 JSON | 对象数组，含 `options[].isCorrect` | `gen_anki_from_json.py` | 题干、选项、答案（必备）；解析、依据、题干图/选项图引用、题目编码（有则识别） |

### 步骤 2：安装依赖

```bash
pip install genanki openpyxl -q
```

### 步骤 3：运行生成脚本

```bash
# Excel 数据源（按题型拆 3 个 apkg，保命题置顶）
python3 gen_anki_from_excel.py 你的题库.xlsx

# Anki 导出 txt 数据源
python3 gen_anki_from_txt.py 你的题库.txt 输出.apkg

# JSON 数据源（支持图片、子卡组、动态乱序）
python3 gen_anki_from_json.py 题库.json --image-root http://图片服务地址/images/ --dynamic
#   --dynamic  启用 JS 每次显示随机乱序
#   --split    按题型拆分为多个 apkg（默认生成一个含子卡组的包）
#   --deck-prefix 题库  卡组名前缀
```

### 步骤 4：验证生成结果

```python
import zipfile, sqlite3, re
with zipfile.ZipFile('输出.apkg', 'r') as z:
    z.extractall('/tmp/check')
conn = sqlite3.connect('/tmp/check/collection.anki2')
rows = conn.execute("SELECT flds FROM notes LIMIT 5").fetchall()
for row in rows:
    f = row[0].split('\x1f')
    labels = re.findall(r'class="optionSpan">([^<]+)<', f[1])
    print(f'  选项: {labels}  答案: {f[2]}')
```

确认点：

* 单选/多选选项顺序与原始不同（已打乱）—— 静态乱序在生成时打乱写死；动态乱序模式抽查卡片内 li 是否带 `data-correct`、模板 qfmt 是否含洗牌 JS
* 答案字母与打乱后位置匹配（静态乱序用 letter_map 重标；动态乱序由 JS 按 `data-correct` 重算）
* 判断题选项为 `A. 正确 / B. 错误`（固定不打乱，li 带 `data-judge`）
* 非判断题选项无 ABCD 前缀
* 图片：apkg 内 media 文件数量 = 图片引用数量，`<img src>` 无缺失

## 二、V10 模板关键规则

| 规则 | 实现方式 |
|---|---|
| 选项去除 ABCD 前缀 | `build_options_html()` 内部正则剥离 |
| 静态乱序（默认） | 生成时 `shuffle` + letter_map 更新答案字母；可传 seed 固定种子 |
| 动态乱序（V10.1） | 卡片 JS 每次显示随机重排；见下方「动态乱序实现要点」 |
| 判断题不打乱 | `build_judge_options_html()` 固定 "A. 正确 / B. 错误"，li 带 `data-judge="1"` |
| 保命题徽章 | `{{IsBaoMing}}` 在 QFMT（问题面）渲染 |
| 答题技巧后置 | `{{HintHTML}}` 在 AFMT（答案面）渲染，不在 QFMT |
| 夜间模式 | CSS `@media (prefers-color-scheme: dark)` 适配 |
| 换卡检测 | QFMT 内 JS 检测 Question 文本变化重置选择状态 |
| 图片内嵌 | `<img>` 直接写入字段，apkg media 打包；图片自适应 CSS（max-width:100% + 圆角） |

### 动态乱序实现要点（V10.1）

目标：**每次出现题目都重新随机选项顺序**（不是生成时固定打乱）。

做法：
1. 生成时选项**保持原序**存储，每个 `<li>` 加 `data-correct="1/0"`（判断题加 `data-judge="1"`）
2. QFMT 注入洗牌 JS（`V10_QFMT_DYNAMIC`）：
   - 本题首次显示时 Fisher-Yates 随机生成顺序，存入 `window._v10Order[题干]`
   - 翻转答案面时 FrontSide 重渲染，应用**同一顺序** → 前后选项位置一致
   - 每次渲染按 `data-correct` 重算答案写入 `#showAnswer`，AFMT 无需改动
   - 判断题（`data-judge` 或 ≤2 选项）跳过洗牌
3. 使用 `create_model(dynamic=True)` 或 `gen_anki_from_json.py --dynamic`

关键坑：
* 不能用生成时静态乱序的答案字母配合动态洗牌 —— 必须由 JS 重算，否则翻面后答案标错
* 洗牌顺序必须持久化（window 变量按题干做 key），否则答案面重渲染后选项位置与问题面不一致
* 判断题必须标记 `data-judge`，避免被当成 2 选项题洗牌逻辑误伤

### V10 模板字段说明（9 字段）

| # | 字段名 | 内容 |
|---|---|---|
| 0 | Question | 题干 HTML（可含 `<img>` 题干图） |
| 1 | OptionsHTML | 预渲染选项 HTML（li 带 value/data-correct） |
| 2 | Answer | 正确答案字母（静态乱序时重标后的字母；动态乱序时由 JS 重算） |
| 3 | Remark | 纯文本解析（备用） |
| 4 | IsBaoMing | 保命题徽章 HTML（空或 🔴 保命题） |
| 5 | RemarkHTML | 格式化解析 HTML（可含 📖 依据） |
| 6 | WrongPointHTML | 判断题错误说法 HTML |
| 7 | RightPointHTML | 判断题正确说法 HTML |
| 8 | HintHTML | 答题技巧 HTML（答案面显示） |

## 三、图片处理（JSON 数据源）

* 题干图/选项图：从 `--image-root` 下载并以 `<img src="文件名">` 内嵌，media 随 apkg 打包，离线可看
* **水印剔除**：同题所有选项的图片引用完全相同时判定为水印/装饰图，跳过不嵌入
* 图片 CSS：`max-width:100%`、圆角、夜间模式降透明度
* 下载失败或非图片响应（Content-Type 无法识别、payload < 128B）自动跳过，不影响生成

## 四、常见问题排查

### 问题：选项仍带 ABCD 前缀

检查选项分隔符。Excel 中是分号或换行分隔；txt 中是 `***` 分隔。`parse_txt_options` 已处理 `***` 分隔和「单段多选项」特殊情况（如 `1月底前 B.6月底前 C.9月底前`）。

### 问题：选项未打乱（静态乱序模式）

`build_options_html` 当 `len(options) <= 2` 时判定为判断题不打乱。3+ 选项未打乱则检查是否误用 `shuffle=False`（动态乱序模式），或 `random.shuffle` 是否被覆盖。

### 问题：动态乱序后答案标错

动态乱序模式下答案字母必须由 JS 按 `data-correct` 重算（模板 `V10_QFMT_DYNAMIC`）。不要沿用静态乱序的 letter_map 答案，也不要省略洗牌顺序持久化（`window._v10Order`）。

### 问题：判断题选项被打乱

判断题 li 必须带 `data-judge="1"`（`build_judge_options_html` 已内置），洗牌 JS 检测到后跳过。

### 问题：答案字母与选项不匹配（静态乱序）

`letter_map` 格式为 `{原始字母: 新字母}`，需将原始答案中每个字母映射到新字母（多选多字母同理）。

### 问题：保命题标记丢失

Excel 中"保命题"标记在"备注"列（或 二级纲要/题目分类/题干 含关键词），而非"题干"列。

### 问题：txt 部分题目选项解析失败

`***` 分隔符失效时（如 `1月底前 B.6月底前`），`parse_txt_options` 用 `re.split(r'(?=[A-Z][\.、\s])')` 再分割。

### 问题：生成的 apkg 无法导入/提示数据库损坏

确认生成端 Anki 版本。本仓库脚本基于 genanki（现代 schema，Anki 2.1.x 均可导入）；若使用手写 collection.anki2 方案，请使用 ver=11 legacy schema（col 表存 models/decks JSON + notes/cards/revlog/graves 五表），现代 Anki 导入时会自动迁移。

### 问题：图片过大导致 apkg 体积膨胀

图片 max-width:100% 只影响显示不影响存储。可在下载环节压缩图片（如 Pillow 转 JPEG 质量 85），或仅保留题干图、剔除大尺寸选项图。

## 五、脚本清单

| 文件 | 说明 |
|---|---|
| `scripts/anki_template_v10.py` | V10 模板模块：CSS/QFMT/AFMT（含动态乱序版）、字段、选项/答案/保命题/解析构建函数、`create_model()` |
| `scripts/gen_anki_from_excel.py` | Excel 数据源 → 按题型拆 3 个 apkg，保命题置顶 |
| `scripts/gen_anki_from_txt.py` | Anki 导出 txt 数据源 → 单卡组 apkg |
| `scripts/gen_anki_from_json.py` | JSON 数据源 → 单 apkg（父卡组+子卡组）或拆分；支持图片下载、水印剔除、`--dynamic` 动态乱序 |

## 六、踩坑经验总结

1. **Anki 导出 txt 选项用 `***` 分隔**，但可能出现单段多选项（如"1月底前 B.6月底前"），需额外正则分割
2. **判断题选项文本就是"A""B"两个字母**（不是"正确/错误"文本），需特殊判断
3. **`{{HintHTML}}` 必须在 AFMT（答案面）而非 QFMT（问题面）**——用户要求答题时不出现技巧
4. **选项容器必须用 `<ul>` 而非 `<ol type="A">`**——ol 会自动按 li 顺序编 A/B/C/D 号，覆盖预渲染的打乱效果
5. **静态乱序必须同步更新答案字段**——shuffle 后按新位置重标 A/B/C/D，用 letter_map 更新答案（含多选多字母）
6. **动态乱序必须由 JS 重算答案并持久化顺序**——答案面重渲染 FrontSide 时顺序会还原，不持久化则前后不一致
7. **AFMT 模板 `{{FrontSide}}` 前禁用 JS 换卡检测脚本**——此时 QFMT 的 DOM 未渲染会导致误重置
8. **保命题判断检查"备注"列**——合并.xlsx 题库中"保命题"标记在"备注"列值为"保命题"
9. **判断题 li 加 `data-judge` 标记**——洗牌/答案逻辑据此跳过
10. **后续修 bug 只在原模板上定点修改 JS**——不要从零重写模板丢弃已有美化
