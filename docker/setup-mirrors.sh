#!/bin/bash

# Script to configure APT to use Tsinghua mirror
# Usage: setup-mirrors.sh [true|false]

USE_TSINGHUA_MIRROR=$1

if [ "$USE_TSINGHUA_MIRROR" = "true" ]; then
    echo "Configuring APT to use Tsinghua mirrors..."
    
    # Process sources.list file (if it exists)
    if [ -f /etc/apt/sources.list ]; then
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
        sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
    fi
    
    # Process sources.list.d directory
    if [ -d /etc/apt/sources.list.d ]; then
        rm -f /etc/apt/sources.list.d/*
        echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list.d/debian.list
        echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list
        echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list
        echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list
    fi
    
    echo "Mirror configuration completed."
else
    echo "Using default mirrors."
fi
