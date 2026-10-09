#!/usr/bin/env python3
"""生成 Rime 的「中文候选 → 英文释义」Lua 词表（纯离线：无网络、无外部进程、无 AI）。

用法（在 Rime 目录下，输入文件见 scripts/fetch-sources.sh）：
    python3 lua/zh_en_gloss_gen.py --cedict cedict.txt --ecdict ecdict.csv

数据源：
    1. CC-CEDICT（https://cc-cedict.org），CC BY-SA 4.0 —— 主词表
    2. ECDICT（https://github.com/skywind3000/ECDICT），MIT —— 只用来补 CEDICT 没有的词
词库基准：rime_ice.dict.yaml 的 import_tables（只给输入法真能打出来的词配释义）。
"""
import argparse
import collections
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))      # <Rime>/lua
RIME_DIR = os.path.dirname(HERE)                       # <Rime>

ap = argparse.ArgumentParser(description='生成 zh_en_gloss.lua')
ap.add_argument('--cedict', default=os.path.join(RIME_DIR, 'cedict.txt'),
                help='CC-CEDICT 纯文本（cedict_1_0_ts_utf-8_mdbg.txt）')
ap.add_argument('--max', type=int, default=0, help='词条上限，0 = 全量')
ap.add_argument('--gloss-limit', type=int, default=72, help='单条释义的字符上限')
ap.add_argument('--out', default=os.path.join(HERE, 'zh_en_gloss.lua'))
ap.add_argument('--overrides', default=os.path.join(HERE, 'zh_en_gloss_overrides.json'))
ap.add_argument('--ecdict', default='',
                help='ECDICT 的 ecdict.csv（MIT），仅用于补齐 CEDICT 没有的词；留空则不启用')
ap.add_argument('--ecdict-common', type=int, default=30000,
                help='单个英文词允许的最差词频排名（越小越严；短语不受此限）')
args = ap.parse_args()

OVERRIDES = json.load(open(args.overrides, encoding='utf-8')) \
    if os.path.exists(args.overrides) else {}

SKIP = re.compile(r'^(CL:|variant of|old variant|erhua variant|see |used in|abbr\. for|'
                  r'Taiwan pr\.|Japanese variant|Korean variant|also written|surname |'
                  r'Classifier|classifier|measure word|onom|punc)', re.I)

# 「see 廣州市|广州市[Guang3 zhou1 Shi4]」这类纯交叉引用
REF_CLAUSE = re.compile(r'see\s+\S*?\[[^\]]*\]', re.I)
REF_TARGET = re.compile(r'see\s+([^\[\]\s]+)\[', re.I)
# 「词[拼音]」注记（含被引用词的繁体/拼音写法）
BRACKET_REF = re.compile(r'\S*?\[[^\]]*\]')


def basis_dicts():
    """从 rime_ice.dict.yaml 的 import_tables 推导实际挂载的词库，保证与输入法一致"""
    schema = os.path.join(RIME_DIR, 'rime_ice.dict.yaml')
    files = [schema]
    if os.path.exists(schema):
        for line in open(schema, encoding='utf-8'):
            m = re.match(r'^\s*-\s*([A-Za-z0-9_/]+)\s*(?:#.*)?$', line)
            if not m or not m.group(1).startswith('cn_dicts/'):
                continue
            cand = os.path.join(RIME_DIR, m.group(1) + '.dict.yaml')
            if os.path.exists(cand) and cand not in files:
                files.append(cand)
    return files


def clean(text):
    text = BRACKET_REF.sub(' ', text)          # 去掉「词[拼音]」注记
    text = text.replace('[', ' ').replace(']', ' ').replace('|', '/')
    return re.sub(r'\s+', ' ', text).strip(' ;,.')


def senses_of(defs):
    """拆义项：丢掉括号注记、see 交叉引用，按 / ; 切分"""
    defs = REF_CLAUSE.sub(' ', defs)
    out = []
    for seg in defs.split('/'):
        seg = re.sub(r'\([^)]*\)', ' ', seg)
        for part in re.split(r'[;/]', seg):
            part = clean(part)
            if part and not SKIP.match(part):
                out.append(part)
    return out


def clause_trim(text, limit):
    """长释义按逗号/分号边界裁剪，最多 3 段"""
    parts = [clean(p) for p in re.split(r'[,;]', text)]
    parts = [p for p in parts if p]
    if not parts:
        return None
    chosen, total = [], 0
    for part in parts:
        if chosen and (total + len(part) + 2 > limit or len(chosen) >= 3):
            break
        chosen.append(part)
        total += len(part) + 2
    result = ', '.join(chosen)
    if len(result) > limit:
        result = result[:limit - 1].rstrip(' ,;') + '…'
    return result


def make_gloss(defs, limit):
    senses = senses_of(defs)
    if not senses:
        return None
    short = [s for s in senses if len(s) <= 32]
    if short:
        chosen, total = [], 0
        for s in short:
            if chosen and (total + len(s) + 2 > min(limit, 60) or len(chosen) >= 3):
                break
            chosen.append(s)
            total += len(s) + 2
        return '; '.join(chosen)
    return clause_trim(senses[0], limit)


EC_POS = re.compile(r'^(n|v|vt|vi|adj|adv|prep|conj|pron|num|art|int|aux|abbr|pl|a|ad)\.', re.I)
EC_TAG = re.compile(r'^\[[^\]]*\]')
EC_PAREN = re.compile(r'\([^)]*\)')
EC_CJK = re.compile(r'^[\u3400-\u4dbf\u4e00-\u9fff]{1,8}$')
EC_HEAD = re.compile(r"^[A-Za-z][A-Za-z'\- ]*$")


def build_ecdict(path, common_cap):
    """ECDICT 是英→汉词典，这里反向映射成 汉→英，只用来补 CEDICT 的空缺。

    质量闸门：英文词按词频排名（bnc/frq，越小越常用）排序，单词不超过 common_cap，
    多词短语不受排名限制（多为技术术语，如 barium enema）；去掉缩写与单字母。
    """
    rev = collections.defaultdict(list)
    seen = collections.defaultdict(set)
    heads = set()
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) < 10:
                continue
            word, trans = row[0].strip(), row[3]
            if not word or not trans or not EC_HEAD.fullmatch(word):
                continue
            heads.add(word.lower())
            try:
                frq = int(row[9]) or 10 ** 9
            except ValueError:
                frq = 10 ** 9
            try:
                bnc = int(row[8]) or 10 ** 9
            except ValueError:
                bnc = 10 ** 9
            rank = min(frq, bnc)
            for line in trans.split('\n'):
                line = EC_POS.sub('', EC_TAG.sub('', line.strip()))
                for term in re.split(r'[；;，,]', line):
                    term = EC_PAREN.sub('', term).strip().strip('·．.、：: ')
                    if not EC_CJK.fullmatch(term) or word.lower() in seen[term]:
                        continue
                    seen[term].add(word.lower())
                    rev[term].append((rank, word))

    def lemma(w):
        lw = w.lower()
        if lw in heads:
            return w
        for suf in ('ies', 'es', 's'):
            if lw.endswith(suf):
                base = lw[:-len(suf)] + ('y' if suf == 'ies' else '')
                if base in heads:
                    return base
        return w

    out = {}
    for term, lst in rev.items():
        picked = {}
        for rank, w in lst:
            w2 = lemma(w)
            if w2.lower() not in picked or rank < picked[w2.lower()][0]:
                picked[w2.lower()] = (rank, w2)
        words = []
        for rank, w in sorted(picked.values(), key=lambda x: (x[0], len(x[1]))):
            if rank > (10 ** 9 if ' ' in w else common_cap):
                continue
            if '.' in w or len(w) < 2:
                continue
            words.append(w)
            if len(words) >= 3:
                break
        if words:
            out[term] = '; '.join(words)
    return out


PAT = re.compile(r'^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+/(.*)/\s*$')

by_key = {}
for line in open(args.cedict, encoding='utf-8'):
    if line.startswith('#'):
        continue
    m = PAT.match(line.rstrip('\n'))
    if not m:
        continue
    trad, simp, defs = m.group(1), m.group(2), m.group(4)
    for key in (simp, trad):
        by_key.setdefault(key, []).append(defs)

cache = {}


def resolve(key, seen=frozenset()):
    """取释义；若该词条只有交叉引用（see X[…]）则递归取被引用词的释义"""
    if key in cache:
        return cache[key]
    if key in seen:
        return None
    for defs in by_key.get(key, ()):
        gloss = make_gloss(defs, args.gloss_limit)
        if not gloss:
            deeper = seen | {key}
            for m in REF_TARGET.finditer(defs):
                gloss = resolve(m.group(1).split('|')[-1], deeper)
                if gloss:
                    break
        if gloss:
            cache[key] = gloss
            return gloss
    cache[key] = None
    return None


best = {}
for key in by_key:
    gloss = resolve(key)
    if gloss:
        best[key] = ((0 if len(gloss) <= args.gloss_limit else 1, len(gloss)), gloss)

words = {}
for f in basis_dicts():
    for line in open(f, encoding='utf-8'):
        s = line.rstrip('\n')
        if not s or s.startswith(('#', '---', '...')) or re.match(r'^[a-zA-Z_]+:', s):
            continue
        p = s.split('\t')
        if len(p) < 2 or not p[0].strip() or len(p[0].strip()) > 8:
            continue
        try:
            wt = float(p[2]) if len(p) > 2 and p[2].strip() else 0.0
        except ValueError:
            wt = 0.0
        t = p[0].strip()
        if t not in words or wt > words[t]:
            words[t] = wt

hit = [(w, best[w][1], words[w]) for w in best if w in words]
single = [x for x in hit if len(x[0]) == 1]
multi = sorted([x for x in hit if len(x[0]) > 1], key=lambda x: (-x[2], len(x[0]), x[0]))
kept = single + (multi[:max(0, args.max - len(single))] if args.max > 0 else multi)
sel = {w: g for w, g, _ in kept}
print('CC-CEDICT 命中 %d，保留 %d（单字 %d）' % (len(hit), len(sel), len(single)))

if args.ecdict:
    ec = build_ecdict(args.ecdict, args.ecdict_common)
    filled = [w for w in words if w not in sel and w in ec]
    for w in filled:
        sel[w] = ec[w]
    print('ECDICT 补齐 %d 条（反向词条共 %d）' % (len(filled), len(ec)))

sel.update(OVERRIDES)
print('人工覆盖 %d 条' % len(OVERRIDES))


def luastr(s):
    return s.replace('\\', '/').replace('"', "'")


items = sorted(sel.items())
head = '''-- 中文候选 → 英文释义（纯离线：无网络请求、无外部进程、无 AI）
-- 数据来源：
--   1. CC-CEDICT（https://cc-cedict.org），授权 CC BY-SA 4.0（署名 / 相同方式共享）
--   2. ECDICT（https://github.com/skywind3000/ECDICT），授权 MIT，仅用于补齐 CEDICT 没有的词
-- 只保留输入法实际挂载的词库（由 rime_ice.dict.yaml 的 import_tables 推导）里的词条，
-- 清洗规则：去掉 (coll.)/(short name …) 之类括号注记、CL:、拼音注记，see/variant 交叉引用递归取释义，
--          长释义按逗号边界裁剪；ECDICT 反向映射按英文词频排名做质量闸门。
-- 末尾「人工修正」区的条目优先于上面所有自动结果。
-- 重新生成：python3 lua/zh_en_gloss_gen.py --cedict <cedict.txt> --ecdict <ecdict.csv>，再「重新部署」。
'''
lines = [head, 'local DATA = {}', 'do']
CH = 6000
chunks = [items[i:i + CH] for i in range(0, len(items), CH)]
for idx, chunk in enumerate(chunks):
    lines.append('  local p%d = {' % idx)
    for w, g in chunk:
        lines.append('    ["%s"]=[==[%s]==],' % (luastr(w), g.replace(']', '')))
    lines.append('  }')
    lines.append('  for k, v in pairs(p%d) do DATA[k] = v end' % idx)
lines += ['end', '', '-- ===== 人工修正（优先于上面自动生成的结果）=====']
for w, g in sorted(OVERRIDES.items()):
    lines.append('DATA["%s"] = [==[%s]==]' % (luastr(w), g.replace(']', '')))
lines += ['', '''local M = {}

-- 命中词表才写英文释义；其它候选（英文、数字、emoji）原样放行
function M.func(input)
    for cand in input:iter() do
        local g = DATA[cand.text]
        if g then cand:get_genuine().comment = g end
        yield(cand)
    end
end

return M''']
out = '\n'.join(lines) + '\n'
open(args.out, 'w', encoding='utf-8').write(out)
print('写入 %s：%.2f MB / %d 条' % (args.out, len(out.encode()) / 1024 / 1024, len(items)))
try:
    json.dump(sel, open('/tmp/rime-research/final_gloss.json', 'w'), ensure_ascii=False)
except OSError:
    pass
