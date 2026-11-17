# Recreating the repository

Forced pushes removed old commits from the branch, but the server may still serve
those objects by SHA. Recreating the repository is the only client-side way to make
them unreachable.

## Before deleting: keep a copy of the history

```bash
git bundle create ../ui-a11y-audit.bundle --all
```

The bundle is a single file containing every commit; it can restore the repository with
`git clone ui-a11y-audit.bundle`.

## Steps

1. GitHub → Settings → Danger Zone → Delete this repository
2. GitHub → New repository: same name, private, no README / .gitignore / license
3. Push the local history to the new repository:

```bash
git remote set-url origin https://github.com/<user>/<repo>.git
git push -u origin main
```

## Verify afterwards

```bash
git ls-remote origin            # one branch, expected commit
git ls-tree -r --name-only origin/main | wc -l
```

The old SHAs no longer resolve, so nothing from the earlier history is retrievable.