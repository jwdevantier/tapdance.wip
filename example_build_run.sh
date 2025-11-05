#!/usr/bin/env sh
set -ex

python crowbar.py lol.c
gcc -O0 \
    allocator.c \
    custodian.c \
    lol.c \
    -o lol

echo "\n\n--execute--\n"
./lol