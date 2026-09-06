# 🤖 Team Standup Bot

An automated system that watches a team's GitHub activity and keeps everyone in the loop — a daily AI-generated standup summary, plus instant AI-written notifications when a new PR needs review.

## What it does

**Daily standup (scheduled, weekdays 9 AM SGT)**
1. Fetches the last 24 hours of commits and pull requests from a GitHub repo
2. Groups activity by contributor
3. Sends it to an AI model, which writes a factual, concise team update — what each person worked on, with any low-activity days noted neutrally rather than judged
4. Delivers the summary to a Telegram group chat

**Instant PR review notification** (companion workflow, lives in the target repo itself)
1. Triggers the moment a PR is opened
2. AI reads the PR title/description and writes a short, casual "here's what this changes, please review" message
3. Posts it to the same Telegram group in seconds

## Architecture

```
Daily Standup (this repo, scheduled):
GitHub REST API (commits + search API for PRs)
        │
        ▼
Group by contributor, filter out merge-commit noise
        │
        ▼
AI (DeepSeek) → factual team summary
        │
        ▼
Telegram group chat

PR Notification (companion workflow, lives in target repo):
GitHub `pull_request: opened` event
        │
        ▼
AI (DeepSeek) → casual review-request message
        │
        ▼
Telegram group chat
```

## Why two repos?

GitHub Actions only reacts to events happening in the same repository as the workflow file. The daily standup summarizer reads data *about* a team's repo via the API, so it can live anywhere. But the instant PR notification needs to react to `pull_request` events *in that repo directly* — so it lives as a small companion workflow inside the target project itself, rather than being centralized here. This repo is intentionally the general-purpose piece; the notification workflow is repo-specific by necessity.

## Tech stack

- **Python** — data fetching, grouping, orchestration
- **GitHub REST API** — commits endpoint (timestamp-filtered) and Search API (date-filtered) for PRs
- **DeepSeek API** — AI-generated summaries and notifications
- **Telegram Bot API** — group chat delivery
- **GitHub Actions** — scheduled cron (standup) + event-triggered (PR notification)

## How AI was used (and how it wasn't)

**AI as a build assistant** — helped scaffold the initial GitHub API calls. Most real debugging, though, came from carefully reading actual API responses and error messages myself: a 400 error revealing the wrong query parameter, a `KeyError` from a missing environment variable, and a Telegram `"chat_id is empty"` error that traced back to a secret-naming mismatch in GitHub's settings.

**AI as a product feature** — the actual standup summary and PR notifications are AI-generated, not templated. This surfaced a real, non-obvious bug: the AI correctly split one person's activity into two entries ("Jace" and "VinstaPyae"), because GitHub's commits API exposes both a raw git-config author name *and* a separate matched GitHub account login, while the PR API only exposes the account login. The AI didn't do anything wrong — my data pipeline was feeding it two different identity systems for the same person. I caught this by reading the AI's output critically rather than assuming it was correct, then fixed the root cause (using the account login consistently) rather than patching around it.

I also explicitly constrained the AI's tone in the prompt: for low-activity flags, it's instructed to state facts neutrally ("no commits today") and never speculate about *why* — since guessing at reasons behind someone's activity level would be unfair and inappropriate for a tool a whole team sees.

## Known limitations

- The Search API used for PRs only filters by date, not exact time — so "last 24 hours" for PRs is closer to "since the start of yesterday" than a precise rolling window. Fine for a daily standup, worth knowing if exact precision mattered.
- Merge commits are filtered out by checking if the message starts with "Merge " — a simple heuristic that works for GitHub's default merge commit messages but could miss custom merge commit formats.
- GitHub Actions' free-tier scheduled workflows can be delayed (sometimes significantly) versus their exact configured time — this is a platform-level limitation, not something fixable in this codebase.

## Setup

Requires four repository secrets:

- `GH_PAT` — GitHub Personal Access Token with `repo` scope (named to avoid GitHub's reserved `GITHUB_` prefix)
- `DEEPSEEK_API_KEY`
- `TEAM_TELEGRAM_BOT_TOKEN`
- `TEAM_TELEGRAM_CHAT_ID` (negative number, since it's a group chat)

Update `GITHUB_OWNER` and `GITHUB_REPO` at the top of `fetch_commits.py` to point at your target repository.
