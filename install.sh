#!/usr/bin/env bash
# 把本仓库的配置装进鼠须管的用户目录（默认 ~/Library/Rime）。
# 已存在的同名文件会先备份成 *.bak-<时间戳>，不会静默覆盖。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RIME_DIR="${1:-$HOME/Library/Rime}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [ ! -d "$RIME_DIR" ]; then
  echo "找不到 Rime 配置目录：$RIME_DIR"
  echo "请先安装鼠须管 Squirrel 并运行过一次。"
  exit 1
fi
if [ ! -f "$RIME_DIR/rime_ice.schema.yaml" ]; then
  echo "警告：$RIME_DIR/rime_ice.schema.yaml 不存在。"
  echo "这些配置依赖雾凇拼音（rime-ice），请先装它，否则部署会失败。"
  echo "  下载 full.zip 解压到 $RIME_DIR（weasel.yaml 可跳过）"
  echo "  https://github.com/iDvel/rime-ice"
  echo
  read -r -p "仍然继续？[y/N] " ans
  case "$ans" in [yY]*) ;; *) exit 1 ;; esac
fi

install_one() {
  local rel="$1"
  local dst="$RIME_DIR/$rel"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] && ! cmp -s "$SRC/$rel" "$dst"; then
    cp "$dst" "$dst.bak-$STAMP"
    echo "  备份 $rel -> $rel.bak-$STAMP"
  fi
  cp "$SRC/$rel" "$dst"
  echo "  安装 $rel"
}

echo "配置目录：$RIME_DIR"
for f in default.custom.yaml rime_ice.custom.yaml squirrel.custom.yaml \
         lua/zh_en_gloss.lua lua/zh_en_gloss_gen.py lua/zh_en_gloss_overrides.json; do
  install_one "$f"
done

echo
echo "完成。接下来点菜单栏 🐿️ →「重新部署」（或重启输入法）。"
