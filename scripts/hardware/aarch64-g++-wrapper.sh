#!/bin/bash
# Strip -stdlib=libc++ which is not supported by the GNU cross-compiler
ARGS=()
for arg in "$@"; do
    if [[ "$arg" != "-stdlib=libc++" ]]; then
        ARGS+=("$arg")
    fi
done
exec /opt/homebrew/bin/aarch64-unknown-linux-gnu-g++ "${ARGS[@]}"
