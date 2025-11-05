#!/usr/bin/env sh
set -ex

meson setup builddir
meson compile -C builddir
echo "\n\n--execute--\n"
./builddir/lol
