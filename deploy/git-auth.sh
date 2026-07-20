#!/bin/bash
export GIT_CONFIG_GLOBAL=/home/ramon/.ura/.gitconfig
echo "Git auth configured for: $(git remote get-url origin 2>/dev/null || echo 'no repo')"
