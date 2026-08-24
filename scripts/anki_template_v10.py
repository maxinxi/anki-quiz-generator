#!/usr/bin/env python3
"""
猪猪模板升级版 (V10) — Anki 卡片模板模块
==========================================

功能清单
--------
✅ 选项预渲染 HTML（翻页刷新 bug 修复）
✅ 静态乱序：生成时打乱 + 按新位置重标 A/B/C/D + 答案字母同步更新
✅ 动态乱序（V10.1）：卡片 JS 每次显示随机重排选项，翻转前后顺序一致
✅ 判断题不打乱（A.正确 / B.错误），li 带 data-judge 标记
✅ 选项 li 带 data-correct 标记，答案可被 JS 重算
✅ 图片内嵌：题干图/选项图 <img> + 图片自适应 CSS（含夜间模式）
✅ 保命题红色徽章（IsBaoMing 字段）
✅ 换卡检测重置选择状态
✅ 选择后点击任意位置 → 显示答案；答案侧点击任意位置 → 简单 → 下一题
✅ 未选择答案提示 / 正确 banner / 错误 banner / 正确标绿 / 错误标红划线 / 未选淡化
✅ radio/checkbox 交互（单选/多选）、夜间模式适配

字段说明（9 字段）
------------------
| # | 字段名        | 内容                                   |
|---|--------------|----------------------------------------|
| 0 | Question     | 题干 HTML（可含 <img> 题干图）          |
| 1 | OptionsHTML  | 预渲染选项 HTML（li 带 value/data-correct）|
| 2 | Answer       | 正确答案字母（静态乱序时重标后的字母）    |
| 3 | Remark       | 纯文本解析（备用）                      |
| 4 | IsBaoMing    | 保命题徽章 HTML（空或 🔴 保命题）        |
| 5 | RemarkHTML   | 格式化解析 HTML                         |
| 6 | WrongPointHTML | 判断题错误说法 HTML（可选）            |
| 7 | RightPointHTML | 判断题正确说法 HTML（可选）            |
| 8 | HintHTML     | 答题技巧 HTML（答案面显示，可选）        |

用法示例
--------
    from anki_template_v10 import create_model, build_options_html, esc

    model = create_model(dynamic=True)   # dynamic=True 启用每次显示随机乱序
    opts_html, letter_map = build_options_html("A. 北京\\nB. 上海\\nC. 广州\\nD. 深圳")
    note = genanki.Note(model=model, fields=[esc(题干), opts_html, "D", "", "", "", "", "", ""])
"""

import html
import random
import re

V10_MODEL_ID = 1610001234
V10_MODEL_NAME = "猪猪模板升级版"

V10_MODEL_FIELDS = [
    {"name": "Question"},
    {"name": "OptionsHTML"},
    {"name": "Answer"},
    {"name": "Remark"},
    {"name": "IsBaoMing"},
    {"name": "RemarkHTML"},
    {"name": "WrongPointHTML"},
    {"name": "RightPointHTML"},
    {"name": "HintHTML"},
]

# ══════════════════════════════════════════════════════════════
# CSS（V10 原版 + 图片自适应 + 夜间模式）
# ══════════════════════════════════════════════════════════════
V10_CSS = r"""
.card{font-family:"Comic Sans MS","OpenDyslexic","Microsoft YaHei",Arial,sans-serif;font-size:18px;line-height:1.8;text-align:left;padding:20px;color:#1a1a2e;background:linear-gradient(135deg,#fefefe 0%,#f0f4ff 100%);max-width:680px;margin:0 auto;}
#Question{font-size:21px;font-weight:700;line-height:1.7;color:#16213e;margin-bottom:18px;padding:16px 20px;background:#fff;border-radius:14px;border:2px solid #e9ecef;box-shadow:0 2px 8px rgba(0,0,0,0.04);}
.badge{display:inline-block;background:linear-gradient(135deg,#ff6b6b,#ee5a24);color:white;padding:5px 16px;border-radius:20px;font-size:15px;font-weight:800;margin-bottom:12px;letter-spacing:1px;box-shadow:0 2px 6px rgba(255,107,107,0.4);}
#ol{list-style:none;padding:0;margin:12px 0;counter-reset:none;}
#ol li{display:flex;align-items:center;padding:14px 20px;margin:10px 0;border:3px solid #e0e0e0;border-radius:14px;background:#fff;font-size:18px;cursor:pointer;transition:all 0.15s ease;position:relative;box-shadow:0 1px 4px rgba(0,0,0,0.03);}
#ol li:hover{border-color:#4dabf7;background:#e7f5ff;box-shadow:0 3px 10px rgba(77,171,247,0.15);}
input.options{width:22px;height:22px;margin-right:12px;flex-shrink:0;cursor:pointer;accent-color:#339af0;}
.optionSpan{padding-left:4px;cursor:pointer;font-size:18px;line-height:1.5;}
input:checked+label{color:#339af0;font-weight:700;}
#ol li:has(input:checked){border-color:#339af0;background:#d0ebff;box-shadow:0 2px 10px rgba(51,154,240,0.2);}
#ol li.correct-answer{border-color:#2b8a3e!important;background:linear-gradient(135deg,#d3f9d8,#b2f2bb)!important;box-shadow:0 0 0 3px rgba(43,138,62,0.25),0 4px 14px rgba(43,138,62,0.2)!important;transform:scale(1.02);}
#ol li.correct-answer label{color:#2b8a3e!important;font-weight:800!important;font-size:20px!important;}
#ol li.correct-answer input{accent-color:#2b8a3e;}
#ol li.wrong-answer{border-color:#e03131!important;background:#ffe3e3!important;opacity:0.75;}
#ol li.wrong-answer label{color:#c92a2a!important;text-decoration:line-through;}
#ol li.wrong-answer input{accent-color:#e03131;}
#ol li.faded{opacity:0.3;border-color:#dee2e6;background:#f1f3f5;}
#ol li.faded label{color:#adb5bd;}
.result-banner{margin:18px 0;padding:16px 22px;border-radius:14px;font-weight:800;font-size:20px;text-align:center;letter-spacing:1px;}
.result-correct{background:linear-gradient(135deg,#d3f9d8,#b2f2bb);color:#2b8a3e;border:3px solid #2b8a3e;box-shadow:0 3px 12px rgba(43,138,62,0.2);}
.result-wrong{background:linear-gradient(135deg,#ffe3e3,#ffc9c9);color:#c92a2a;border:3px solid #e03131;box-shadow:0 3px 12px rgba(224,49,49,0.2);}
.remark-box{margin-top:14px;padding:14px 20px;border-radius:12px;background:linear-gradient(135deg,#fff9db,#fff3bf);border-left:5px solid #fcc419;font-size:16px;line-height:1.7;color:#5c4813;}
.remark-box strong{color:#e67700;}
.wrong-point{margin-top:16px;padding:18px 22px;border-radius:14px;background:linear-gradient(135deg,#ffe3e3,#ffc9c9);border:3px solid #e03131;font-size:17px;line-height:1.8;color:#c92a2a;}
.wrong-point .wp-title{font-weight:900;font-size:18px;color:#e03131;letter-spacing:1px;margin-bottom:8px;}
.wrong-point .wp-wrong{font-weight:700;font-size:19px;color:#c92a2a;background:rgba(255,255,255,0.5);padding:10px 14px;border-radius:10px;border:2px dashed #e03131;text-decoration:line-through;text-decoration-color:#e03131;text-underline-offset:4px;text-decoration-thickness:3px;margin-bottom:10px;}
.right-point{margin-top:14px;padding:18px 22px;border-radius:14px;background:linear-gradient(135deg,#d3f9d8,#b2f2bb);border:3px solid #2b8a3e;font-size:17px;line-height:1.8;color:#2b8a3e;}
.right-point .rp-title{font-weight:900;font-size:18px;color:#2b8a3e;letter-spacing:1px;margin-bottom:8px;}
.right-point .rp-correct{font-weight:700;font-size:19px;color:#2b8a3e;background:rgba(255,255,255,0.5);padding:10px 14px;border-radius:10px;border:2px solid #2b8a3e;}
.hint-text{margin-top:14px;font-size:13px;color:#adb5bd;text-align:center;font-style:italic;}
.hint-continue{margin-top:14px;padding:12px 20px;border-radius:12px;background:linear-gradient(135deg,#e7f5ff,#d0ebff);border:2px solid #339af0;font-size:16px;text-align:center;color:#1971c2;font-weight:700;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.6;}}
.disabled{display:none;}
/* 图片自适应（通用做法：max-width:100% + 圆角 + 夜间模式） */
.card img{max-width:100%;height:auto;border-radius:10px;}
#Question img{display:block;max-width:100%;max-height:420px;width:auto;height:auto;margin:12px auto 4px;border-radius:10px;}
.optionSpan img{display:block;max-width:100%;max-height:260px;width:auto;height:auto;margin:6px auto 2px;border-radius:8px;}
@media (prefers-color-scheme: dark) {
  .card{color:#e9ecef;background:linear-gradient(135deg,#1a1b1e,#2d2d2d);}
  #Question{background:#252525;border-color:#495057;color:#dee2e6;}
  #ol li{background:#2d2d2d;border-color:#495057;color:#dee2e6;}
  #ol li:hover{border-color:#4dabf7;background:#1a3a5c;}
  #ol li.correct-answer{background:linear-gradient(135deg,#1a3d2a,#2d5a3a)!important;border-color:#2b8a3e!important;}
  #ol li.correct-answer label{color:#69db7c!important;}
  #ol li.wrong-answer{background:#3d1a1a!important;border-color:#e03131!important;}
  #ol li.wrong-answer label{color:#ff8787!important;}
  #ol li.faded{background:#1e1e1e;border-color:#333;}
  #ol li.faded label{color:#495057;}
  .remark-box{background:#2d2508;border-left-color:#fcc419;color:#fcc419;}
  .wrong-point{background:linear-gradient(135deg,#3d1a1a,#5a2020);border-color:#e03131;color:#ff8787;}
  .right-point{background:linear-gradient(135deg,#1a3d2a,#2d5a3a);border-color:#2b8a3e;color:#69db7c;}
  .hint-continue{background:#1a3a5c;border-color:#339af0;color:#74c0fc;}
  .card img{opacity:0.92;}
}
"""

# ══════════════════════════════════════════════════════════════
# QFMT（静态乱序版）— 选完答案后点击任意位置显示答案
# ══════════════════════════════════════════════════════════════
V10_QFMT = r"""{{IsBaoMing}}
<div id="Question" style="font-family:Arial;font-size:15px;text-align:left;">{{Question}}</div>
<ul id="ol" style="font-family:Arial;font-size:15px;">{{OptionsHTML}}</ul>
<div id="showAnswer" class="disabled">{{Answer}}</div>
<div id="hintBefore" class="hint-text">👆 选择答案后，点击屏幕任意位置继续</div>
<div id="hintAfter" class="hint-continue" style="display:none;">👆 点击屏幕任意位置 → 显示答案</div>
<script>
(function(){
  // ★ 换卡检测：题目变了就重置选择状态
  var curQ = document.getElementById('Question').innerText;
  if(!window._v9LastQ || window._v9LastQ !== curQ){
    window._v9LastQ = curQ;
    window._v9Sel = null;
    window._v9SelArr = [];
  }
  if(!window._v9Ready){
    window._v9Ready = true;
    window.clickLi = function(el){ if(event.target === el) el.querySelector('input').click(); };
    window.onRadioChange = function(inp){
      var q = document.getElementById('Question').innerText;
      if(window._v9LastQ !== q){ window._v9LastQ = q; window._v9SelArr = []; }
      window._v9Sel = inp.value;
      _v10ShowHint();
    };
    window.onCheckChange = function(inp){
      var q = document.getElementById('Question').innerText;
      if(window._v9LastQ !== q){ window._v9LastQ = q; window._v9Sel = null; }
      window._v9SelArr = [];
      var allC = document.querySelectorAll('#ol input[type="checkbox"]:checked');
      for(var i=0;i<allC.length;i++){ window._v9SelArr.push(allC[i].value); }
      _v10ShowHint();
    };
    window._v10ShowHint = function(){
      var hb = document.getElementById('hintBefore');
      var ha = document.getElementById('hintAfter');
      if(hb) hb.style.display = 'none';
      if(ha) ha.style.display = 'block';
    };
    document.addEventListener('click', function(e){
      if(document.getElementById('resultBanner')) return;
      if(!window._v9Sel && (!window._v9SelArr || window._v9SelArr.length === 0)) return;
      if(e.target.closest){
        if(e.target.closest('#ol')) return;
      } else {
        var el = e.target;
        while(el){ if(el.id === 'ol') return; el = el.parentElement; }
      }
      e.stopPropagation();
      try{ if(typeof pycmd === 'function'){ pycmd('ans'); return; } }catch(ex){}
      try{ if(typeof showAnswer === 'function'){ showAnswer(); return; } }catch(ex){}
    }, true);
  }
})();
</script>"""

# ══════════════════════════════════════════════════════════════
# QFMT 动态乱序版（V10.2）— 每次出现题目都重新随机重排选项
#
# 原理：
#   * 选项 li 带 data-correct="1/0"（判断题带 data-judge="1"）
#   * 洗牌逻辑延迟到 setTimeout(0) 执行：
#       - 此时若 DOM 已有 #resultBanner → 本次渲染是【背面】
#         → 复用正面刚写入 window._v10Saved[题干] 的顺序，前后一致
#       - 若没有 resultBanner → 本次是【新一轮正面】→ 强制重新洗牌并覆盖缓存
#     ⇒ 每次出现该题选项顺序都不同（防背位置），且正反面顺序一致
#   * 判断题（data-judge 或 ≤2 选项）不打乱
# ══════════════════════════════════════════════════════════════
V10_QFMT_DYNAMIC = V10_QFMT.replace(
    "{{Answer}}</div>",
    "{{Answer}}</div>\n"
    "<script>\n"
    "(function(){\n"
    "  function v10Shuffle(){\n"
    "    var qDiv = document.getElementById('Question');\n"
    "    var ol = document.getElementById('ol');\n"
    "    if(!qDiv || !ol) return;\n"
    "    var curQ = qDiv.innerText.trim().slice(0,80);\n"
    "    var lis = Array.prototype.slice.call(ol.children);\n"
    "    var isJudge = !!ol.querySelector('li[data-judge]');\n"
    "    var inBack = !!document.getElementById('resultBanner');\n"
    "    var order = null;\n"
    "    if(inBack && !isJudge && lis.length > 2){\n"
    "      var sv = window._v10Saved && window._v10Saved[curQ];\n"
    "      if(sv){ order = sv; }\n"
    "    }\n"
    "    if(!order && lis.length > 2 && !isJudge){\n"
    "      order = [];\n"
    "      for(var i = 0; i < lis.length; i++){ order.push(i); }\n"
    "      for(var i = order.length - 1; i > 0; i--){\n"
    "        var j = Math.floor(Math.random() * (i + 1));\n"
    "        var t = order[i]; order[i] = order[j]; order[j] = t;\n"
    "      }\n"
    "      if(!window._v10Saved){ window._v10Saved = {}; }\n"
    "      window._v10Saved[curQ] = order;\n"
    "    }\n"
    "    if(order && lis.length > 2 && !isJudge){\n"
    "      for(var k = 0; k < order.length; k++){ ol.appendChild(lis[order[k]]); }\n"
    "    }\n"
    "    var items = Array.prototype.slice.call(ol.children);\n"
    "    var ans = '';\n"
    "    items.forEach(function(li, idx){\n"
    "      var letter = String.fromCharCode(65 + idx);\n"
    "      li.setAttribute('value', letter);\n"
    "      var inp = li.querySelector('input');\n"
    "      if(inp){ inp.value = letter; inp.id = letter; }\n"
    "      var lab = li.querySelector('label');\n"
    "      if(lab){ lab.setAttribute('for', letter); }\n"
    "      if(li.getAttribute('data-correct') === '1'){ ans += letter; }\n"
    "    });\n"
    "    var sa = document.getElementById('showAnswer');\n"
    "    if(sa && !isJudge && ans){ sa.innerText = ans; }\n"
    "  }\n"
    "  setTimeout(v10Shuffle, 0);\n"
    "})();\n"
    "</script>",
    1,
)

# ══════════════════════════════════════════════════════════════
# AFMT — 答案侧：点击任意位置 → 评为"简单" → 下一题
# ══════════════════════════════════════════════════════════════
V10_AFMT = r"""
{{FrontSide}}

<div id="resultBanner"></div>
{{RemarkHTML}}
{{WrongPointHTML}}
{{RightPointHTML}}
{{HintHTML}}
<div class="hint-continue">👆 点击屏幕任意位置 → 简单 → 下一题</div>

<script>
(function(){
  // ★ V10.2：判分延迟到洗牌之后执行（洗牌 setTimeout 0 → 判分 setTimeout 1）
  setTimeout(function(){
  var ansDiv = document.getElementById('showAnswer');
  var rawAnswer = ansDiv ? ansDiv.innerText.trim() : '';
  function parseAnswers(raw){
    if(!raw) return [];
    if(/^[A-Za-z]+$/.test(raw.replace(/\s+/g,''))){
      return raw.replace(/\s+/g,'').toUpperCase().split('');
    }
    var tokens = raw.replace(/，/g,',').split(/[,，\s]+/).filter(Boolean);
    var map={'正确':'A','对':'A','TRUE':'A','T':'A','错误':'B','错':'B','FALSE':'B','F':'B'};
    return tokens.map(function(t){return map[t.trim().toUpperCase()]||t.trim().toUpperCase()});
  }
  var answers = parseAnswers(rawAnswer);
  var selected = window._v9Sel || null;
  var selectedArr = window._v9SelArr || [];
  var lis = document.querySelectorAll('#ol li');
  lis.forEach(function(li){
    var input = li.querySelector('input');
    var val = li.getAttribute('value');
    if(input) input.disabled = true;
    li.style.cursor = 'default';
    li.onclick = null;
    var isCorrect = answers.indexOf(val) !== -1;
    var isSelected = (val === selected) || (selectedArr.indexOf(val) !== -1);
    if(isCorrect){ li.classList.add('correct-answer'); }
    else if(isSelected){ li.classList.add('wrong-answer'); }
    else { li.classList.add('faded'); }
  });
  var banner = document.getElementById('resultBanner');
  if(!banner) return;
  var hasSelection = selected || selectedArr.length > 0;
  var isCorrect = false;
  if(answers.length > 1){
    isCorrect = selectedArr.length === answers.length &&
                selectedArr.every(function(s){ return answers.indexOf(s) !== -1; });
  } else {
    isCorrect = selected && answers.indexOf(selected) !== -1;
  }
  if(!hasSelection){
    banner.innerHTML = '<div class="result-banner result-wrong">⚠️ 未选择答案，正确答案已标绿</div>';
  } else if(isCorrect){
    banner.innerHTML = '<div class="result-banner result-correct">✅ 回答正确！</div>';
  } else {
    banner.innerHTML = '<div class="result-banner result-wrong">❌ 回答错误，正确答案已标绿</div>';
  }
  }, 1);
  // 点击任意位置 → 评为"简单" → 下一题（延迟 400ms 防误触）
  if(!window._v10AfmtReady){
    window._v10AfmtReady = true;
    setTimeout(function(){
      document.addEventListener('click', function(e){
        if(!document.getElementById('resultBanner')) return;
        if(!window._v9Sel && (!window._v9SelArr || window._v9SelArr.length === 0)) return;
        e.stopPropagation();
        e.preventDefault();
        try{
          if(typeof ankiDroidJS !== 'undefined' && ankiDroidJS.api){ ankiDroidJS.api.answerCard(4); return; }
        }catch(ex){}
        try{
          if(typeof pycmd === 'function'){ pycmd('ease4'); return; }
        }catch(ex){}
      }, true);
    }, 400);
  }
})();
</script>"""


# ══════════════════════════════════════════════════════════════
# Python 辅助函数
# ══════════════════════════════════════════════════════════════

def esc(s):
    """HTML 转义"""
    return html.escape(str(s or ""), quote=True)


def parse_options(opt_str):
    """解析选项字符串，返回 [(letter, text), ...]
    支持格式：换行/分号分隔；前缀 A. / A、 / A- / A  均可。
    """
    if not opt_str or not str(opt_str).strip():
        return []
    text = str(opt_str).strip()
    lines = re.split(r"[;\n；]", text)
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([A-Z])[\.、\-\s]\s*(.*)", line)
        if m:
            result.append((m.group(1), m.group(2).strip()))
        else:
            idx = len(result)
            if idx < 26:
                result.append((chr(65 + idx), line))
    return result


def _li_html(letter, text, input_type, is_correct=None, is_judge=False, image_html=""):
    """构建单个选项 li。is_correct 为 True/False 时写 data-correct，判断题写 data-judge。"""
    extra = ""
    if is_judge:
        extra = ' data-judge="1"'
    elif is_correct is not None:
        extra = f' data-correct="{"1" if is_correct else "0"}"'
    onchange = "onRadioChange(this)" if input_type == "radio" else "onCheckChange(this)"
    safe = esc(text)
    # 选项文本剥离 ABCD 前缀（判断题保留 "A. 正确" 前缀）
    if not is_judge and re.match(r"^[A-Z][\.、\s]", safe):
        safe = safe[2:].strip()
    return (
        f'<li value="{letter}"{extra} onclick="clickLi(this)">'
        f'<input type="{input_type}" name="options" class="options" value="{letter}" id="{letter}" onchange="{onchange}">'
        f'<label for="{letter}" class="optionSpan">{safe}{image_html}</label>'
        f"</li>"
    )


def build_options_html(opt_str, is_multi=False, shuffle=True, seed=None):
    """预渲染选项 HTML，返回 (html, letter_map)。

    shuffle=True：静态乱序（生成时打乱 + 重标 + letter_map 供答案重映射）
    shuffle=False：保持原始顺序（配合 V10_QFMT_DYNAMIC 的 JS 动态乱序使用）
    seed：固定随机种子（可复现）；None 则每次随机。
    """
    options = parse_options(opt_str)
    if not options:
        return "", {}

    input_type = "checkbox" if is_multi else "radio"
    letter_map = {}

    if shuffle and len(options) > 2:
        rng = random.Random(seed) if seed is not None else random
        rng.shuffle(options)

    for i, (orig_letter, _text) in enumerate(options):
        letter_map[orig_letter] = chr(65 + i)

    # 计算正确答案字母（按当前顺序位置）
    correct_set = set()  # 调用方用 is_correct 标记时用不到；这里仅用于 letter_map 说明
    parts = []
    for i, (orig_letter, text) in enumerate(options):
        new_letter = chr(65 + i)
        parts.append(_li_html(new_letter, text, input_type))
    return "\n".join(parts), letter_map


def build_judge_options_html():
    """预渲染判断题选项（固定 A.正确 / B.错误，不打乱，li 带 data-judge）"""
    return (
        _li_html("A", "A. 正确", "radio", is_judge=True) + "\n"
        + _li_html("B", "B. 错误", "radio", is_judge=True)
    )


def build_remark_html(analysis):
    """构建解析 HTML"""
    if analysis and str(analysis).strip():
        return f'<div class="remark-box">💡 <strong>解析：</strong>{esc(analysis)}</div>'
    return ""


def build_baoming_html(is_bm):
    """构建保命题徽章 HTML"""
    return '<div class="badge">🔴 保命题</div>' if is_bm else ""


def build_wrong_point_html(stem, judge_analysis):
    """构建判断题错误说法 HTML"""
    if not judge_analysis or not str(judge_analysis).strip():
        return ""
    return (
        '<div class="wrong-point">\n'
        '<div class="wp-title">❌ 错误说法</div>\n'
        f'<div class="wp-wrong">{esc(stem)}</div>\n'
        "</div>"
    )


def build_right_point_html(judge_analysis):
    """构建判断题正确说法 HTML"""
    if not judge_analysis or not str(judge_analysis).strip():
        return ""
    return (
        '<div class="right-point">\n'
        '<div class="rp-title">✅ 正确说法</div>\n'
        f'<div class="rp-correct">{esc(judge_analysis)}</div>\n'
        "</div>"
    )


def convert_answer(answer_str):
    """中文答案转字母：正确/对/TRUE/T→A；错误/错/FALSE/F→B；其他→大写"""
    a = str(answer_str).strip()
    if a in ("正确", "对", "TRUE", "T"):
        return "A"
    if a in ("错误", "错", "FALSE", "F"):
        return "B"
    return a.upper()


def create_model(model_id=None, model_name=None, dynamic=False):
    """创建 genanki.Model 实例。

    dynamic=True：使用 V10_QFMT_DYNAMIC（JS 每次显示随机乱序，选项保持原序存储）
    dynamic=False：使用 V10_QFMT（静态乱序，生成时打乱并重标）
    """
    import genanki

    return genanki.Model(
        model_id or V10_MODEL_ID,
        model_name or V10_MODEL_NAME,
        fields=V10_MODEL_FIELDS,
        templates=[{
            "name": "Card 1",
            "qfmt": V10_QFMT_DYNAMIC if dynamic else V10_QFMT,
            "afmt": V10_AFMT,
        }],
        css=V10_CSS,
    )


if __name__ == "__main__":
    print(f"=== {V10_MODEL_NAME} V10 === 模型ID: {V10_MODEL_ID} 字段数: {len(V10_MODEL_FIELDS)}")
    html_str, lmap = build_options_html("A. 北京\nB. 上海\nC. 广州\nD. 深圳", shuffle=True, seed=42)
    print("静态乱序 letter_map:", lmap)
    html_str2, lmap2 = build_options_html("A. 北京\nB. 上海\nC. 广州\nD. 深圳", shuffle=False)
    print("原序（动态乱序用） letter_map:", lmap2)
    print("判断题:")
    print(build_judge_options_html())
