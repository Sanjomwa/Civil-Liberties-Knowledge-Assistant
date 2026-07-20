#!/usr/bin/env bash
# sync.sh — single source of truth for the Cowork <-> WSL sync, per ADR-shaped
# process decision 2026-07-20 (see project CLAUDE.md Section 9, and the
# Opus consult recorded there). Committed to the repo (not gitignored) so a
# fresh clone or a cold Claude Code session gets this automatically, without
# needing a human to hand-recreate it.
#
# Why this exists: the exclude-list for what should/shouldn't sync between
# the two sides has already changed twice as new generated files appeared
# (corpus/acquisition-log.md, corpus/manifest.csv, etc.). Keeping that list
# in one executable file, instead of duplicated across prose in two CLAUDE.md
# files and every handed-off prompt, means it only needs updating in one
# place when it changes again — and it fails loudly instead of silently
# doing the wrong thing.
#
# Usage:
#   ./sync.sh          (same as ./sync.sh pull)
#   ./sync.sh pull      Cowork -> WSL. Run this FIRST, before any task,
#                        every time, no exceptions -- pulls curated docs/
#                        YAML/ADRs from the OneDrive-synced Cowork mirror.
#   ./sync.sh push       WSL -> Cowork. Run this LAST, after a task
#                        finishes -- mirrors the WHOLE repo back (code,
#                        corpus/sources/*.yaml, corpus/acquisition-log.md,
#                        manifest, reports.md, everything except the
#                        excluded paths below), so nothing WSL wrote during
#                        the task can ever be silently lost on the next
#                        pull. See the 2026-07-20 incident log in project
#                        CLAUDE.md Section 9 -- this file-by-file patching
#                        approach (reports.md only, then +corpus/sources/)
#                        already failed once for real: ADR-0005's actual
#                        code in acquire.py/extract.py was never pushed
#                        anywhere, so the next pull silently reverted it
#                        back to the pre-ADR-0005 original. Push is now
#                        symmetric to pull instead of a curated list, so
#                        this class of bug can't recur the same way again.
#
# Fails loudly on purpose: if the OneDrive mount path doesn't exist, this
# exits non-zero with a clear message rather than silently no-op'ing (rsync
# against a missing source directory can otherwise look like "nothing to
# do" instead of "something is wrong").
#
# Post-sync summary + dotfile sanity scan (added 2026-07-20, after a
# retrospective on three separate incidents this same day -- an
# incomplete-exclude-list bug hit three times in a row: push missing a
# YAML directory, push missing src/*.py, then both pull and push missing
# .git/). The generalizable lesson (Opus-consulted): the exclude list is
# a MODEL of what matters, and every incident was that model silently
# drifting from reality without anything ever checking. Adding yet
# another named exclude only patches the specific instance already
# found -- it doesn't catch the next unanticipated category. So instead
# of only trusting the exclude list, every run now prints (a) rsync's
# own transfer stats, so an unexpectedly large/small transfer is visible
# at a glance instead of assumed correct, and (b) a scan for top-level
# dotfiles/dirs in the destination that aren't explicitly expected --
# this catches a FUTURE .git-shaped surprise (or anything else) even if
# nobody thought to add an exclude for it yet, which is the actual
# structural fix, not one more named exclude.

set -euo pipefail

COWORK_MIRROR="/mnt/c/Users/HP/OneDrive/Documents/New project/LLM-ZOOMCAMP/project/civili liberties RAG/repo"
WSL_REPO="$HOME/Projects/civil-liberties-knowledge-assistant"

MODE="${1:-pull}"

if [ ! -d "$COWORK_MIRROR" ]; then
  echo "FAIL: Cowork mirror not found at: $COWORK_MIRROR" >&2
  echo "This usually means OneDrive isn't mounted/synced right now, or the" >&2
  echo "path changed. Do not proceed with the task -- fix this first." >&2
  exit 1
fi

# Prints rsync's own transfer count/size, plus a dotfile/dir sanity scan
# of $1 (the sync destination) so an unanticipated category of file
# (like the .git/ incident) is visible immediately, not discovered by
# accident later. Not a substitute for correct excludes -- a
# complementary check that doesn't depend on anyone having anticipated
# the specific thing that went wrong.
print_sync_summary() {
  local dest="$1"
  local stats_file="$2"
  echo ""
  echo "[sync.sh] Transfer summary:"
  grep -E "Number of (regular files transferred|created files|deleted files)|Total transferred file size" "$stats_file" | sed 's/^/  /'
  echo ""
  echo "[sync.sh] Top-level dotfiles/dirs at $dest (sanity scan -- expect only"
  echo "  known entries like .gitignore; anything unfamiliar here is worth a"
  echo "  second look, especially anything that looks like .git/):"
  find "$dest" -maxdepth 1 -name '.*' -not -name '.' -not -name '..' -exec basename {} \; | sed 's/^/  /'
}

case "$MODE" in
  pull)
    echo "[sync.sh] Cowork -> WSL (pull) starting..."
    # Deliberately no --delete/--delete-excluded: this must never remove
    # anything from WSL, only add/update non-excluded files. Excluded
    # paths (.venv, data/, reports.md, CLAUDE.md, the generated corpus/
    # files) must stay completely untouched, not deleted -- that's the
    # whole point of excluding them. See the 2026-07-20 incident log in
    # project CLAUDE.md Section 9 for why this matters.
    #
    # --exclude='.git/' matters more here than on push: this pull writes
    # directly into WSL's real, live .git, not a working-copy mirror. The
    # Cowork mirror should never have a .git/ of its own (push already
    # excludes it), but if it ever did -- stale, foreign, or diverged from
    # this repo's real history -- an unguarded pull would merge that
    # content straight into the actual repo's git internals. Caught
    # 2026-07-20 right after the equivalent push-side gap: that first pull
    # (before this exclude existed) did inject the mirror's .git/ into
    # this repo's real one, confirmed harmless only because the mirror's
    # .git happened to originate from this same repo's history (a no-op
    # overlay) -- verified via git status/log/fsck all clean. Won't rely
    # on that coincidence again.
    stats_file="$(mktemp)"
    rsync -av --stats \
      --exclude='.venv' --exclude='__pycache__' --exclude='data/' \
      --exclude='reports.md' --exclude='CLAUDE.md' --exclude='.git/' \
      --exclude='corpus/acquisition-log.md' --exclude='corpus/manifest.csv' \
      --exclude='corpus/checksums.sha256' --exclude='corpus/validation-report.md' \
      "$COWORK_MIRROR/" \
      "$WSL_REPO/" | tee "$stats_file"
    print_sync_summary "$WSL_REPO" "$stats_file"
    rm -f "$stats_file"
    echo "[sync.sh] Pull complete."
    ;;
  push)
    if [ ! -f "$WSL_REPO/reports.md" ]; then
      echo "FAIL: no reports.md at $WSL_REPO/reports.md to push." >&2
      echo "Nothing to send back yet -- has the task actually finished" >&2
      echo "and written its report?" >&2
      exit 1
    fi
    echo "[sync.sh] WSL -> Cowork (push) starting..."
    # Full mirror, WSL -> Cowork, same exclude philosophy as pull but only
    # three exclusions: .venv/__pycache__/data/ (never worth the payload --
    # data/ especially can be large, and the Cowork session doesn't need
    # raw downloaded documents to do curation), CLAUDE.md (WSL-local
    # execution-layer conventions, deliberately never synced into Cowork's
    # copy -- the canonical reference for that content is
    # claude-code-wsl-CLAUDE.md), and claude-code-wsl-CLAUDE.md itself
    # (Cowork-authored, one-directional Cowork -> WSL only via pull;
    # excluded from push so a stale WSL copy can never overwrite Cowork's
    # canonical one -- moved into repo/ 2026-07-20, see its own revision
    # history v4, after living outside repo/ made it unreachable by pull
    # and blocked a real task).
    #
    # Everything else -- src/, corpus/sources/*.yaml, corpus/
    # acquisition-log.md, corpus/manifest.csv, corpus/checksums.sha256,
    # corpus/validation-report.md, docs/, reports.md -- flows back. This
    # used to be a curated per-file list (reports.md, then +corpus/
    # sources/) and that approach genuinely failed 2026-07-20: ADR-0005's
    # code changes in acquire.py/extract.py were never on the list, so the
    # next pull reverted them to the pre-ADR-0005 original with no warning.
    # A full mirror can't have that specific failure mode again -- whatever
    # WSL legitimately writes during a task, push sends back, no list to
    # forget an entry on. No --delete/--delete-excluded here either, same
    # reasoning as pull: this must only add/update on the Cowork side,
    # never remove something Cowork itself added since the last push.
    stats_file="$(mktemp)"
    rsync -av --stats \
      --exclude='.venv' --exclude='__pycache__' --exclude='data/' \
      --exclude='CLAUDE.md' --exclude='.git/' --exclude='claude-code-wsl-CLAUDE.md' \
      "$WSL_REPO/" \
      "$COWORK_MIRROR/" | tee "$stats_file"
    print_sync_summary "$COWORK_MIRROR" "$stats_file"
    rm -f "$stats_file"
    echo "[sync.sh] Push complete."
    ;;
  *)
    echo "FAIL: unknown mode '$MODE'. Use 'pull' or 'push'." >&2
    exit 1
    ;;
esac
