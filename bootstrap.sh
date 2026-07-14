#!/usr/bin/env bash

set -Eeuo pipefail

readonly REPOSITORY_URL="https://github.com/Proskud/tg-bot-rashodov.git"
readonly BRANCH="main"
readonly INSTALL_DIR="${INSTALL_DIR:-/opt/tg-bot-rashodov}"

info() {
  printf '\n\033[1;34m%s\033[0m\n' "$*"
}

fail() {
  printf '\033[1;31mОшибка: %s\033[0m\n' "$*" >&2
  exit 1
}

require_root() {
  [[ "${EUID}" -eq 0 ]] || fail \
    'запустите команду через sudo, чтобы установить проект в /opt и настроить Docker.'
}

ensure_git() {
  command -v git >/dev/null 2>&1 && return

  command -v apt-get >/dev/null 2>&1 || fail \
    'Git не найден. Автоматическая установка поддерживается на Ubuntu и Debian.'

  info 'Git не найден — устанавливаю системный пакет.'
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates
}

download_project() {
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    info 'Проект уже установлен — получаю обновления.'
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
    return
  fi

  if [[ -e "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
    fail "каталог ${INSTALL_DIR} уже существует и не является копией проекта."
  fi

  info "Скачиваю проект в ${INSTALL_DIR}."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth 1 --branch "$BRANCH" "$REPOSITORY_URL" "$INSTALL_DIR"
}

main() {
  require_root
  ensure_git
  download_project

  [[ -r /dev/tty && -w /dev/tty ]] || fail \
    'нужен интерактивный терминал для безопасного ввода токена и Telegram ID.'
  exec bash "${INSTALL_DIR}/install.sh" </dev/tty
}

main "$@"
