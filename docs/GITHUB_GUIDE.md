# Pushing FraudPulse v2 to GitHub

Two cases. Pick one.

## A. You already have a FraudPulse repository (recommended: keep the history)

```bash
# 1. clone your existing repo next to the unzipped project
git clone https://github.com/<your-username>/<your-repo>.git fraudpulse-old
cd fraudpulse-old

# 2. work on a branch so the old Scala version stays safe on main
git checkout -b v2-pyspark

# 3. replace the content with v2 (keep the .git folder!)
git rm -r -q --cached . && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -r ../fraudpulse/. .          # the unzipped v2 folder (includes hidden files)

# 4. check what will be committed
git status
git ls-files --others --exclude-standard | grep -E "\.env$|\.csv$|models/" && echo "STOP: secret/data file" || echo "clean"

# 5. commit and push the branch
git add .
git commit -m "feat: v2 - pure Python (PySpark + xgboost.spark), idempotent Mongo sink, DLQ, tests, CI"
git push -u origin v2-pyspark
```

Then on GitHub: **Compare & pull request → Merge**. (Or tag the old version first:
`git tag v1-scala main && git push origin v1-scala` so it stays reachable.)

## B. New repository

```bash
cd fraudpulse                        # the unzipped project folder
git init -b main
git add .
git status                           # make sure .env, data/*.csv and models/* are NOT listed
git commit -m "Initial commit: FraudPulse v2 (PySpark + XGBoost)"
```

Create an **empty** repo on https://github.com/new (no README/license/.gitignore — you already have them),
then:

```bash
git remote add origin https://github.com/<your-username>/fraudpulse.git
git push -u origin main
```

Or with the GitHub CLI: `gh repo create fraudpulse --public --source=. --remote=origin --push`

## Authentication (the part that usually fails)

HTTPS no longer accepts your account password. Use one of:

- **Personal access token**: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained →
  repo permission *Contents: Read and write*. Paste the token when Git asks for a password.
- **SSH key**: `ssh-keygen -t ed25519 -C "you@example.com"`, add `~/.ssh/id_ed25519.pub` in
  Settings → SSH keys, then use `git@github.com:<user>/fraudpulse.git` as the remote URL.
- **GitHub CLI**: `gh auth login` and follow the prompts.

## Before you push — checklist

- [ ] `.env` is **not** tracked (only `.env.example`). If a secret was ever committed, rotate it.
- [ ] No `data/*.csv` (PaySim is 470 MB; GitHub rejects files > 100 MB) and no `models/*` committed.
- [ ] You ran `make up && make train` at least once and the dashboard shows data.
- [ ] README "Status" section only claims what you actually ran. Add real numbers (throughput, AUC-PR on real PaySim).
- [ ] Add 1–2 screenshots (`docs/img/dashboard.png`) and link them in the README.
- [ ] Repo → About: description + topics (`pyspark`, `xgboost`, `kafka`, `structured-streaming`,
      `fraud-detection`, `mongodb`, `data-engineering`).
- [ ] The CI badge works after the first push (Actions tab → CI).

## Day-to-day workflow

```bash
git checkout -b feature/load-test
# ...edit...
git add -p && git commit -m "feat: add load test script"
git push -u origin feature/load-test      # open a Pull Request, CI runs automatically
```

Use small commits with prefixes (`feat:`, `fix:`, `docs:`, `test:`) — recruiters read the history.
