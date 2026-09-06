import os
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

def group_commits_by_author(commits):
    by_author = defaultdict(list)

    for commit in commits:
        if commit["commit"]["message"].startswith("Merge "):
            continue
        # Use the GitHub account login (matches PR authorship),
        # not the raw git config name, so the same person isn't split in two
        github_login = commit["author"]["login"] if commit.get("author") else commit["commit"]["author"]["name"]
        message = commit["commit"]["message"]
        date = commit["commit"]["author"]["date"]
        by_author[github_login].append({"message": message, "date": date})

    return dict(by_author)

GITHUB_OWNER = "VinstaPyae"
GITHUB_REPO = "ft_transcendence"

def fetch_recent_commits():
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = requests.get(
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits",
        headers={
            "Authorization": f"Bearer {os.environ['GH_PAT']}",
            "Accept": "application/vnd.github+json",
        },
        params={"since": since, "per_page": 100},
    )
    response.raise_for_status()
    return response.json()

# if __name__ == "__main__":
#     commits = fetch_recent_commits()
#     print(f"Found {len(commits)} commits")

#     grouped = group_commits_by_author(commits)
#     for author, commit_list in grouped.items():
#         print(f"\n{author}: {len(commit_list)} commits")
#         for c in commit_list:
#             print(f"  - {c['message']}")


def fetch_recent_pull_requests():
    since_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"repo:{GITHUB_OWNER}/{GITHUB_REPO} type:pr updated:>={since_date}"

    response = requests.get(
        "https://api.github.com/search/issues",
        headers={
            "Authorization": f"Bearer {os.environ['GH_PAT']}",
            "Accept": "application/vnd.github+json",
        },
        params={"q": query, "per_page": 100},
    )
    response.raise_for_status()
    return response.json()["items"]

def group_pull_requests_by_author(pull_requests):
    by_author = defaultdict(list)

    for pr in pull_requests:
        author = pr["user"]["login"]
        by_author[author].append({
            "title": pr["title"],
            "state": pr["state"],
            "url": pr["html_url"],
        })

    return dict(by_author)

def send_telegram_message(text):
    bot_token = os.environ["TEAM_TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TEAM_TELEGRAM_CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
    )
    response.raise_for_status()

def generate_standup_summary(grouped_commits, grouped_prs):
    lines = []
    all_authors = set(grouped_commits.keys()) | set(grouped_prs.keys())

    for author in all_authors:
        commits = grouped_commits.get(author, [])
        prs = grouped_prs.get(author, [])

        lines.append(f"\n{author}:")
        lines.append(f"  Commits ({len(commits)}):")
        for c in commits:
            lines.append(f"    - {c['message']}")
        lines.append(f"  Pull Requests ({len(prs)}):")
        for pr in prs:
            lines.append(f"    - [{pr['state']}] {pr['title']}")

    activity_text = "\n".join(lines)

    prompt = (
        f"You are writing a concise team standup summary based on the last 24 hours "
        f"of GitHub activity. Here's the raw data per team member:\n\n"
        f"{activity_text}\n\n"
        f"Write a short summary (a few sentences per person) covering what each "
        f"person worked on, inferred from their commit messages and PR titles. "
        f"If someone has very low or zero activity compared to others, note it "
        f"factually and neutrally (e.g. 'no commits today') — do not guess "
        f"at reasons why, and do not sound accusatory. "
        f"Format it as a readable team update, with each person's name as a "
        f"header. No excessive praise, just a factual, useful summary a team "
        f"lead could skim in 30 seconds."
    )

    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    commits = fetch_recent_commits()
    grouped_commits = group_commits_by_author(commits)

    prs = fetch_recent_pull_requests()
    grouped_prs = group_pull_requests_by_author(prs)

    print("=== COMMITS ===")
    for author, commit_list in grouped_commits.items():
        print(f"{author}: {len(commit_list)} commits")
        for c in commit_list:
            print(f"  - {c['message']}")

    print("\n=== PULL REQUESTS ===")
    for author, pr_list in grouped_prs.items():
        print(f"{author}: {len(pr_list)} PRs")
        for pr in pr_list:
            print(f"  - [{pr['state']}] {pr['title']}")

    print("\n=== AI STANDUP SUMMARY ===")
    summary = generate_standup_summary(grouped_commits, grouped_prs)
    print(summary)

    send_telegram_message(summary)
    print("\nSent to Telegram group!")
