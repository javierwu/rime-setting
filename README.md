# rime-setting

macOS 鼠须管（Squirrel）的个人配置，基于 [雾凇拼音 rime-ice](https://github.com/iDvel/rime-ice)。

目标：**中英混合输入、英文联想、默认半角标点、中文候选后直接显示英文释义**，全部离线，不联网、不装守护进程、不用 AI。

## 环境

| 项目 | 版本 / 说明 |
| --- | --- |
| 系统 | macOS（Apple Silicon 已验证） |
| 输入法 | 鼠须管 Squirrel 1.1.2（librime 1.16.0） |
| 方案 | 雾凇拼音 rime-ice（全量包） |
| 配置目录 | `~/Library/Rime` |

## 快速开始

1. **装雾凇拼音**（本仓库不含词库，只含自定义配置）：

   ```bash
   cd ~/Library/Rime
   curl -LO https://mirror.nju.edu.cn/github-release/iDvel/rime-ice/LatestRelease/full.zip
   unzip -o full.zip -x weasel.yaml        # weasel.yaml 是 Windows 专用，跳过
   ```

2. **放本仓库的配置**：

   ```bash
   git clone https://github.com/javierwu/rime-setting.git /tmp/rime-setting
   /tmp/rime-setting/install.sh            # 复制 3 个 custom 文件 + lua/ 释义文件，旧的会备份
   ```

3. **重新部署**：点菜单栏 🐿️ →「重新部署」。

## 功能对照

### 1. 中英文混合输入

用 `rime_ice` 方案：中文状态下直接敲英文单词，按空格/回车即上屏原文，不用切输入法（如 `zuogeDNAjiance` → `做个DNA检测`）。

### 2. 英文联想

`default.custom.yaml` 里挂了第二个方案 `melt_eng`（纯英文）。切过去后输入前缀即联想补全完整英文单词（`melt_eng.dict.yaml` 的 8 万词表）。

> ⚠️ `melt_eng` 是**纯英文方案，没有中文词库**，切进去打不出中文。中文请切回 `rime_ice`。

### 3. 默认半角标点

`rime_ice.custom.yaml` 里给 `ascii_punct` 加了 `reset: 1`，每次加载都回到半角。

- `⌃.`（Control+句号）或 `⌃⇧3` 在 半角 `, . ? !` / 全角 `，。？！` 之间切换。
- 想让它**记住**全角状态，把 `rime_ice.custom.yaml` 里 `ascii_punct` 下面的 `reset: 1` 删掉。

### 4. 中文候选 → 英文释义（本仓库的主要工作）

拼音提示码被关掉（`translator/spelling_hints: 0`），候选后面那一栏专门用来显示英文：

```
苹果         Apple
深圳         Shenzhen, sub-provincial city in Guangdong Province
保险公司     insurer; insurance firm; insurance company
钡灌肠       barium enema
```

## 仓库内容

```
default.custom.yaml              输入方案列表（rime_ice + melt_eng）、⌃. 切换中英标点
rime_ice.custom.yaml             switches、默认半角、关拼音提示码、挂载释义过滤器
squirrel.custom.yaml             外观：沿用系统自带的 native 皮肤（跟随深浅色）
lua/zh_en_gloss.lua              释义词表（生成产物，15.5 万条，7.7 MB）
lua/zh_en_gloss_gen.py           生成脚本
lua/zh_en_gloss_overrides.json   人工修正（优先级最高）
scripts/fetch-sources.sh         下载两个原始数据源
install.sh                       把配置复制进 ~/Library/Rime
```

## 英文释义词表是怎么来的

`lua/zh_en_gloss.lua` 是个纯数据表，配合 `lua/zh_en_gloss_gen.py` 生成的 Lua 过滤器使用：

```lua
local g = DATA[cand.text]
if g then cand:get_genuine().comment = g end   -- 命中才写 comment，其它候选原样放行
```

**数据来源**

| 来源 | 授权 | 用量 |
| --- | --- | --- |
| [CC-CEDICT](https://cc-cedict.org) | CC BY-SA 4.0 | 主词表，10.3 万条 |
| [ECDICT](https://github.com/skywind3000/ECDICT) | MIT | 仅补 CEDICT 缺的词，5.3 万条 |

**只给输入法真能打出来的词配释义**：词条白名单由 `rime_ice.dict.yaml` 的 `import_tables` 自动推导，所以词表和你的输入法不会对不上。

**清洗规则**：去掉 `(coll.)` / `(short name …)` 之类括号注记、`CL:`、拼音注记；`see X[…]` 交叉引用递归取被引用词的释义；长释义按逗号边界裁剪。ECDICT 部分按英文词频排名做质量闸门（单词限 3 万名以内，多词技术短语放宽）。

**覆盖率**（对照 187 万条词库）

| 词长 | 覆盖率 |
| --- | --- |
| 1 字 | 88% |
| 2 字 | 42% |
| 3 字 | 9% |
| 4 字 | 5% |

> 越长的词覆盖越低是数据本身决定的——腾讯大词库里有大量人名、地名、句子片段（`金慧琴`、`打得过呀`），任何词典都不会收录。

### 重新生成

```bash
cd ~/Library/Rime
scripts/fetch-sources.sh                # → /tmp/rime-research/{cedict.txt,ecdict.csv}
python3 lua/zh_en_gloss_gen.py \
    --cedict cedict.txt --ecdict ecdict.csv
# 成功后菜单栏 🐿️ →「重新部署」
```

常用开关：`--gloss-limit 72`（单条释义字符上限）、`--ecdict-common 30000`（英文词频门槛，调小更严格）。

### 手动修正

`lua/zh_en_gloss_overrides.json` 里的条目**优先于所有自动结果**，改完重新生成即可：

```json
{
  "摸鱼": "to slack off; goof off",
  "抓手": "grip; lever; (fig.) means to get things done"
}
```

## 常见问题

- **切到纯英文后打不出中文** → 你切到了 `melt_eng`，按 `⌃`` 或 Shift 切回 `rime_ice`。
- **候选栏的拼音没了** → 故意的，`spelling_hints: 0` 把注释栏让给了英文释义。
- **改了 `page_size` 无效** → 改 `default.custom.yaml` 的 `patch:` 段再重新部署，直接改 `default.yaml` 会被覆盖。

## 许可证

本仓库的配置文件为个人配置，可自由取用。

`lua/zh_en_gloss.lua` 是 CC-CEDICT（CC BY-SA 4.0）与 ECDICT（MIT）的衍生数据，**再分发请保留两者署名**，CC-CEDICT 部分需相同方式共享。

其余依赖的授权：鼠须管 GPL-3.0、librime BSD-3、rime-ice GPL-3.0。
