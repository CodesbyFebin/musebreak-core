#!/usr/bin/env bash
# Download the official Firecracker release binary. Kernel + rootfs: follow
# https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md
set -euo pipefail
ARCH="$(uname -m)"
VER="${FC_VERSION:-$(curl -fsSL https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest | sed -n 's/.*"tag_name": "v\([^"]*\)".*/\1/p')}"
curl -fsSL -o /tmp/fc.tgz "https://github.com/firecracker-microvm/firecracker/releases/download/v${VER}/firecracker-v${VER}-${ARCH}.tgz"
tar -xzf /tmp/fc.tgz -C /tmp
install -m 0755 "/tmp/release-v${VER}-${ARCH}/firecracker-v${VER}-${ARCH}" /usr/local/bin/firecracker
echo "installed firecracker v${VER}. Set FC_KERNEL=/path/vmlinux FC_ROOTFS=/path/rootfs.ext4 (see getting-started.md)"
