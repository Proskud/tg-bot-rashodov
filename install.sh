#!/usr/bin/env bash

set -Eeuo pipefail

readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ENV_FILE="${PROJECT_DIR}/.env"
COMPOSE=()

info() {
  printf '\n\033[1;34m%s\033[0m\n' "$*"
}

success() {
  printf '\033[1;32m%s\033[0m\n' "$*"
}

fail() {
  printf '\033[1;31mОшибка: %s\033[0m\n' "$*" >&2
  exit 1
}

validate_token() {
  [[ "$1" =~ ^[0-9]{6,}:[A-Za-z0-9_-]{20,}$ ]]
}

normalize_ids() {
  local value="${1//[[:space:]]/}"

  [[ "$value" =~ ^[0-9]+(,[0-9]+)*$ ]] || return 1
  printf '%s' "$value"
}

self_test() {
  validate_token '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcd' || fail 'self-test token'
  ! validate_token 'not-a-token' || fail 'self-test invalid token'
  [[ "$(normalize_ids '123, 456,789')" == '123,456,789' ]] || fail 'self-test IDs'
  ! normalize_ids '123,user' >/dev/null || fail 'self-test invalid IDs'
  success 'Self-test установщика пройден.'
}

require_tty() {
  [[ -r /dev/tty && -w /dev/tty ]] || fail \
    'нужен интерактивный терминал для безопасного ввода токена и Telegram ID.'
  exec 3<>/dev/tty
}

prompt_secret() {
  local prompt="$1"
  local value

  printf '%s' "$prompt" >&3
  IFS= read -r -s -u 3 value
  printf '\n' >&3
  printf '%s' "$value"
}

prompt_value() {
  local prompt="$1"
  local default_value="${2:-}"
  local value

  printf '%s' "$prompt" >&3
  IFS= read -r -u 3 value
  printf '%s' "${value:-$default_value}"
}

configure_env() {
  local token ids_input ids overwrite

  if [[ -f "$ENV_FILE" ]]; then
    overwrite="$(prompt_value 'Файл .env уже существует. Настроить заново? [y/N]: ' 'n')"
    if [[ ! "$overwrite" =~ ^[YyДд]$ ]]; then
      info 'Существующая конфигурация сохранена.'
      return
    fi
  fi

  while true; do
    token="$(prompt_secret 'Токен Telegram-бота от @BotFather: ')"
    validate_token "$token" && break
    printf 'Формат токена не распознан. Попробуйте ещё раз.\n' >&3
  done

  while true; do
    ids_input="$(prompt_value 'Разрешённые Telegram ID через запятую: ')"
    if ids="$(normalize_ids "$ids_input")"; then
      break
    fi
    printf 'Укажите один или несколько числовых ID, например: 123456789,987654321\n' >&3
  done

  umask 077
  local temp_env="${ENV_FILE}.tmp.$$"
  trap 'rm -f "${temp_env:-}"' RETURN
  {
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$token"
    printf 'ALLOWED_TELEGRAM_USER_IDS=%s\n' "$ids"
    printf 'DATABASE_URL=sqlite+aiosqlite:///./data/expenses.db\n'
    printf 'TIMEZONE=Asia/Yekaterinburg\n'
    printf 'CURRENCY=RUB\n'
    printf 'MONTHLY_REPORT_HOUR=20\n'
    printf 'LOG_LEVEL=INFO\n'
  } >"$temp_env"
  chmod 600 "$temp_env"
  mv "$temp_env" "$ENV_FILE"
  trap - RETURN

  unset token ids_input
  success 'Конфигурация сохранена в .env с правами 600.'
}

install_docker_debian() {
  local packages=(docker.io)

  [[ "${EUID}" -eq 0 ]] || fail \
    'Docker не найден. Запустите установщик через sudo, чтобы установить его автоматически.'
  command -v apt-get >/dev/null 2>&1 || fail \
    'автоматическая установка Docker поддерживается на Ubuntu и Debian.'

  info 'Docker не найден — устанавливаю системные пакеты.'
  apt-get update
  if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
    packages+=(docker-compose-v2)
  elif apt-cache show docker-compose-plugin >/dev/null 2>&1; then
    packages+=(docker-compose-plugin)
  elif apt-cache show docker-compose >/dev/null 2>&1; then
    packages+=(docker-compose)
  else
    fail 'не найден пакет Docker Compose.'
  fi

  DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker
  fi
}

detect_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
  else
    install_docker_debian
    if docker compose version >/dev/null 2>&1; then
      COMPOSE=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
      COMPOSE=(docker-compose)
    else
      fail 'Docker Compose установлен, но не запускается.'
    fi
  fi
}

deploy() {
  local container_id

  cd "$PROJECT_DIR"
  info 'Проверяю конфигурацию Docker Compose.'
  "${COMPOSE[@]}" -f "$PROJECT_DIR/compose.yaml" config --quiet

  info 'Собираю и запускаю Telegram-бота.'
  "${COMPOSE[@]}" -f "$PROJECT_DIR/compose.yaml" up -d --build --remove-orphans

  sleep 3
  container_id="$("${COMPOSE[@]}" -f "$PROJECT_DIR/compose.yaml" ps -q bot)"
  if [[ -n "$container_id" ]] && \
    [[ "$(docker inspect --format '{{.State.Running}}' "$container_id")" == 'true' ]]; then
    success 'Бот установлен и запущен.'
    printf 'Статус: cd %q && %s -f compose.yaml ps\n' "$PROJECT_DIR" "${COMPOSE[*]}"
    printf 'Логи:  cd %q && %s -f compose.yaml logs -f bot\n' \
      "$PROJECT_DIR" "${COMPOSE[*]}"
  else
    "${COMPOSE[@]}" -f "$PROJECT_DIR/compose.yaml" logs --tail=50 bot >&2 || true
    fail 'контейнер бота не запустился. Диагностика показана выше.'
  fi
}

main() {
  if [[ "${1:-}" == '--self-test' ]]; then
    self_test
    return
  fi

  require_tty
  info 'Настройка Telegram-бота для учёта расходов'
  configure_env
  detect_compose
  deploy
}

main "$@"
