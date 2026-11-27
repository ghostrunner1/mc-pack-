#!/bin/sh
# Builds _files/mods/sporeguard-1.0.0.jar (server-only). Stubs only for compiling, not packed.
set -e
cd "$(dirname "$0")"
rm -rf build && mkdir -p build/stubs build/out
javac --release 21 -d build/stubs $(find stubs -name '*.java')
javac --release 21 -encoding UTF-8 -cp build/stubs -d build/out $(find src -name '*.java')
cp -r res/* build/out/
jar --create --file ../../_files/mods/sporeguard-1.0.0.jar -C build/out .
rm -rf build
