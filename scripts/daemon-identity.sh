# Daemon identity check shared by wacom-ctl and wacom-status (sourced).
# Mirrors is_daemon_argv() in wacom-daemon.py.

# True when PID $1 is a live long-lived daemon: argv is exactly
# `python3 .../wacom-daemon.py` plus optional daemon flags (--match/--config),
# with no one-shot flag (--probe, --check-config, --dump-events, --help).
# With $2, argv[1] must also equal that exact script path (used by the
# straggler sweep, so only this install's daemon is ever signalled).
#
# The exact argv is matched, not a substring of the cmdline: an editor or
# pager with the script open (`nvim wacom-daemon.py`) is not the daemon.
is_daemon_pid() {
  local pid="${1:-}" want_path="${2:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [[ "$pid" -gt 1 ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  local -a argv=()
  if [[ -r "/proc/$pid/cmdline" ]]; then
    mapfile -d '' -t argv < "/proc/$pid/cmdline" 2>/dev/null || return 1
  elif command -v ps >/dev/null 2>&1; then
    read -r -a argv <<< "$(ps -p "$pid" -o args= 2>/dev/null)"
  else
    return 1
  fi
  [[ "${#argv[@]}" -ge 2 ]] || return 1
  [[ "${argv[0]##*/}" =~ ^python[0-9.]*$ ]] || return 1
  [[ "${argv[1]##*/}" == "wacom-daemon.py" ]] || return 1
  if [[ -n "$want_path" && "${argv[1]}" != "$want_path" ]]; then
    return 1
  fi
  local arg
  for arg in "${argv[@]:2}"; do
    case "$arg" in
      --probe|--check-config|--dump-events|-h|--help) return 1 ;;
    esac
  done
  return 0
}
