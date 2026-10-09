#!/usr/bin/env bash
# 下载生成英文释义词表所需的两个原始数据源。
# 默认输出到 /tmp/rime-research（重启会清空），可以传参换个目录：
#     scripts/fetch-sources.sh ~/Library/Rime/sources
set -euo pipefail

OUT="${1:-/tmp/rime-research}"
mkdir -p "$OUT"
cd "$OUT"

# 1) CC-CEDICT（CC BY-SA 4.0）—— 官方导出，约 4 MB
if [ ! -s cedict.txt ]; then
  echo "下载 CC-CEDICT ..."
  curl -fL --retry 3 -o cedict.gz \
    "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
  gunzip -f cedict.gz
fi
echo "  $OUT/cedict.txt  ($(wc -l < cedict.txt) 行)"

# 2) ECDICT（MIT，约 66 MB）—— 走 GitHub Git Data API，
#    因为 raw.githubusercontent.com / codeload 在部分网络下不通。
if [ ! -s ecdict.csv ]; then
  echo "下载 ECDICT ..."
  api="https://api.github.com/repos/skywind3000/ECDICT"
  sha=$(curl -fsSL "$api/git/trees/master" \
        | python3 -c "import json,sys;print(next(t['sha'] for t in json.load(sys.stdin)['tree'] if t['path']=='ecdict.csv'))")
  curl -fL --retry 3 -o ecdict_blob.json "$api/git/blobs/$sha"
  python3 - <<'PY'
import base64, json
d = json.load(open('ecdict_blob.json'))
open('ecdict.csv', 'wb').write(base64.b64decode(d['content']))
PY
  rm -f ecdict_blob.json
fi
echo "  $OUT/ecdict.csv  ($(wc -l < ecdict.csv) 行)"

echo
echo "下一步："
echo "  python3 lua/zh_en_gloss_gen.py --cedict $OUT/cedict.txt --ecdict $OUT/ecdict.csv"
