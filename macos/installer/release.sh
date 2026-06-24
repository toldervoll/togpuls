#!/usr/bin/env bash
# Bump macos/VERSION, commit bumpen, tag og push for å trigge release-
# workflowen. Kalles av Makefile-target `macos-release`.
#
# Defaults til patch-bump. Overstyr med BUMP=minor|major eller sett en
# eksplisitt versjon via NEW_VERSION=x.y.z.
#
#     make macos-release
#     make macos-release BUMP=minor
#     make macos-release NEW_VERSION=1.0.0
#
# Krever ren arbeidsmappe på main, i sync med origin. Det forhindrer
# tilfeldige release-er med uncommitted endringer eller fra feil branch.

set -euo pipefail

BUMP="${BUMP:-patch}"
NEW_VERSION="${NEW_VERSION:-}"
VERSION_FILE="macos/VERSION"

# ── Validering ────────────────────────────────────────────────────────────

if [ ! -f "$VERSION_FILE" ]; then
    echo "Finner ikke $VERSION_FILE." >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Working tree er ikke ren. Commit eller stash først." >&2
    exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
    echo "Taggar bare fra main (du står på $branch)." >&2
    exit 1
fi

git fetch --quiet origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
    echo "HEAD er ikke i sync med origin/main. Push eller pull først." >&2
    exit 1
fi

# ── Beregn ny versjon ────────────────────────────────────────────────────

current="$(cat "$VERSION_FILE" | tr -d '[:space:]')"
if [ -z "$current" ]; then
    echo "$VERSION_FILE er tom." >&2
    exit 1
fi

if [ -n "$NEW_VERSION" ]; then
    new="$NEW_VERSION"
    if ! [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Ugyldig NEW_VERSION: '$new' (forvent MAJOR.MINOR.PATCH)." >&2
        exit 1
    fi
else
    if ! [[ "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        echo "Nåværende versjon '$current' følger ikke MAJOR.MINOR.PATCH." >&2
        exit 1
    fi
    maj="${BASH_REMATCH[1]}"
    min="${BASH_REMATCH[2]}"
    pat="${BASH_REMATCH[3]}"
    case "$BUMP" in
        patch) pat=$((pat + 1)) ;;
        minor) min=$((min + 1)); pat=0 ;;
        major) maj=$((maj + 1)); min=0; pat=0 ;;
        *) echo "BUMP må være patch, minor eller major (var: '$BUMP')." >&2; exit 1 ;;
    esac
    new="${maj}.${min}.${pat}"
fi

tag="macos-v${new}"

if git rev-parse "$tag" >/dev/null 2>&1; then
    echo "Tag $tag finnes allerede. Bruk høyere versjon eller slett taggen først." >&2
    exit 1
fi

# ── Bump, commit, tag, push ──────────────────────────────────────────────

echo "Bumper $VERSION_FILE: $current → $new"
echo "$new" > "$VERSION_FILE"
git add "$VERSION_FILE"
git commit --quiet -m "macOS: bump til $new"

echo "Tagger $tag …"
git tag -a "$tag" -m "macOS release $new"
git push --quiet origin main "$tag"

echo "→ $tag pushet. Workflow kjører på github.com/kengu/togpuls/actions"
