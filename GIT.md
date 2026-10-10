# Git and GitHub

The repo already has its history: one commit per milestone (M1 to M8) on the `main` branch.

```sh
git log --oneline
```

## Put it on GitHub

1. Create an empty repository on GitHub (no README, licence or .gitignore, so the histories don't clash). Call it `pulse`, for example.
2. From the repo root:

```sh
git remote add origin https://github.com/<your-username>/pulse.git
git push -u origin main
```

With the GitHub CLI you can do both in one step: `gh repo create pulse --private --source . --push`.

CI starts on the first push (lint, type checks, tests, E2E). It never deploys.

## What is ignored

`.gitignore` keeps out `.env`, virtualenvs, `node_modules`, the SQLite files, uploaded media, build output and test reports. Only `.env.example` is committed; never commit `.env`, since it holds your secret key and push keys.

## Starting from the files without the history

If you copied the files without the `.git` folder:

```sh
git init -b main
git add .
git commit -m "Leon and Learning Hub"
```

Then follow the GitHub steps above.
