#!/usr/bin/env bash
# Push / pull OpenCore Studio source and the last EFI between two machines.
#
#   ./sync-share.sh init
#   ./sync-share.sh push          # this Mac -> share folder or other Mac
#   ./sync-share.sh pull          # share folder or other Mac -> this Mac
#   ./sync-share.sh export-efi    # copy latest EFI + config.plist into share/efi
#   ./sync-share.sh push efi      # only the EFI folder
#   ./sync-share.sh pull efi
#   ./sync-share.sh push --dry-run
#
# Edit share/remote.conf after init. Default is a folder on /Volumes/tools
# that both Macs can mount. Set REMOTE=user@host and REMOTE_PATH=... for SSH.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARE_DIR="${SCRIPT_DIR}/share"
EXCLUDE="${SHARE_DIR}/rsync-exclude.txt"
CONF="${SHARE_DIR}/remote.conf"
EXAMPLE="${SHARE_DIR}/remote.conf.example"

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \?//'
  exit "${1:-0}"
}

need_rsync() {
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required (it ships with macOS)." >&2
    exit 1
  fi
}

init_share() {
  mkdir -p "${SHARE_DIR}/efi" "${SHARE_DIR}/incoming"
  if [[ ! -f "$CONF" ]]; then
    cp "$EXAMPLE" "$CONF"
    echo "Wrote ${CONF} — edit REMOTE (and REMOTE_PATH if you use SSH)."
  else
    echo "Already initialized: ${CONF}"
  fi
}

load_conf() {
  if [[ ! -f "$CONF" ]]; then
    echo "No share/remote.conf yet. Run: ./sync-share.sh init" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$CONF"
  if [[ -z "${REMOTE:-}" ]]; then
    echo "REMOTE is empty in share/remote.conf" >&2
    exit 1
  fi
}

dest_root() {
  if [[ "$REMOTE" == *@* ]]; then
    echo "${REMOTE}:${REMOTE_PATH:?Set REMOTE_PATH in share/remote.conf for SSH}"
  else
    echo "$REMOTE"
  fi
}

rsync_base() {
  local dry=()
  if [[ "${DRY_RUN:-}" == "1" ]]; then
    dry=(--dry-run)
  fi
  rsync -a "${dry[@]}" --human-readable --progress --exclude-from="$EXCLUDE" "$@"
}

export_efi() {
  local src=""
  local support="${HOME}/Library/Application Support/OpenCore Studio/builds/latest"
  if [[ -d "$support/EFI" ]]; then
    src="$support"
  elif [[ -d "${SCRIPT_DIR}/data/builds/latest/EFI" ]]; then
    src="${SCRIPT_DIR}/data/builds/latest"
  fi
  mkdir -p "${SHARE_DIR}/efi"
  if [[ -z "$src" ]]; then
    echo "No EFI build found. Build EFI in Studio first." >&2
    exit 1
  fi
  rsync -a --delete "${src}/" "${SHARE_DIR}/efi/"
  echo "Copied EFI from ${src} -> share/efi"
}

run_sync() {
  local direction="$1"
  local what="${2:-source}"
  local dest
  dest="$(dest_root)"
  mkdir -p "${SHARE_DIR}/efi" "${SHARE_DIR}/incoming"

  if [[ "$what" == "efi" ]]; then
    if [[ "$direction" == "push" ]]; then
      export_efi
      mkdir -p "${dest}/efi" 2>/dev/null || true
      rsync_base "${SHARE_DIR}/efi/" "${dest}/efi/"
    else
      mkdir -p "${SHARE_DIR}/efi"
      rsync_base "${dest}/efi/" "${SHARE_DIR}/efi/"
    fi
    return
  fi

  if [[ "$direction" == "push" ]]; then
    rsync_base "${SCRIPT_DIR}/" "${dest}/"
  else
    rsync_base "${dest}/" "${SCRIPT_DIR}/"
  fi
}

DRY_RUN=""
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage 0 ;;
    *) ARGS+=("$arg") ;;
  esac
done

cmd="${ARGS[0]:-}"
extra="${ARGS[1]:-source}"

need_rsync
case "$cmd" in
  init) init_share ;;
  export-efi) export_efi ;;
  push|pull)
    load_conf
    run_sync "$cmd" "$extra"
    echo "Done: ${cmd} ${extra}"
    ;;
  *)
    usage 1
    ;;
esac
