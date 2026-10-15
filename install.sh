#!/usr/bin/env bash
# Installs t3code-customize for the Linux AppImage or the macOS app. On Windows use install.ps1.
set -euo pipefail
for tool in git python3; do
  command -v "$tool" >/dev/null || { echo "$tool is required. Install it and run this again." >&2; exit 1; }
done
case "$(uname -s)" in
  Linux|Darwin) repo="${XDG_DATA_HOME:-$HOME/.local/share}/t3code-customize/repo" ;;
  MINGW*|MSYS*|CYGWIN*) echo 'Use install.ps1 on Windows.' >&2; exit 1 ;;
  *) echo 'Only Linux, macOS and Windows are supported.' >&2; exit 1 ;;
esac
remote="${T3_CUSTOMIZE_REPOSITORY:-https://github.com/btsouth/t3code-customize.git}"
branch="${T3_CUSTOMIZE_BRANCH:-main}"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo 'Python 3.10 or newer is required.' >&2; exit 1;
}
if [[ -d "$repo/.git" ]]; then
  [[ "$(git -C "$repo" remote get-url origin)" == "$remote" ]] || {
    echo "Existing checkout has a different origin: $repo" >&2; exit 1;
  }
  git -C "$repo" pull --ff-only --quiet
elif [[ -e "$repo" ]]; then
  echo "Destination already exists and is not a checkout: $repo" >&2; exit 1
else
  mkdir -p "$(dirname "$repo")"
  git clone --quiet --branch "$branch" "$remote" "$repo"
fi
exec python3 "$repo/t3code-customize" "$@"
