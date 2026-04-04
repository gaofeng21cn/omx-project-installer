#!/usr/bin/env bash
set -euo pipefail

BASELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SKILLS_DIR="${CODEX_HOME_DIR}/skills"
SKILL_NAME="omx-project-installer"
SOURCE_SKILL_DIR="${BASELINE_DIR}/skills/${SKILL_NAME}"
TARGET_SKILL_DIR="${SKILLS_DIR}/${SKILL_NAME}"

mkdir -p "${SKILLS_DIR}"

if [[ ! -d "${SOURCE_SKILL_DIR}" ]]; then
  echo "Missing skill source: ${SOURCE_SKILL_DIR}" >&2
  exit 1
fi

ln -sfn "${SOURCE_SKILL_DIR}" "${TARGET_SKILL_DIR}"

echo "Installed ${SKILL_NAME} -> ${TARGET_SKILL_DIR}"
echo "Next: in a target repo, tell Codex:"
echo "  使用 \$${SKILL_NAME}，把当前项目按 runtime-service 或 project-native 模式完成 OMX project-scope 安装与合同分层收口。"

