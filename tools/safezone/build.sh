#!/bin/sh
# Builds _files/mods/safezone-1.0.0.jar (server-only). Stubs only for compiling, not packed.
set -e
cd "$(dirname "$0")"
rm -rf build && mkdir -p build/stubs build/out
javac --release 21 -d build/stubs $(find stubs -name '*.java')
javac --release 21 -cp build/stubs -d build/out src/ru/oleg/safezone/SafeZone.java
cp -r res/* build/out/
jar --create --file ../../_files/mods/safezone-1.0.0.jar -C build/out .
rm -rf build
