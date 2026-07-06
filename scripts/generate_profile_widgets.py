#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "yashodipp")
TOKEN = os.environ.get("GITHUB_TOKEN")
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "profile-widgets"


def fetch_json(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-widget-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_repos():
    repos = []
    page = 1
    while True:
        batch = fetch_json(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated&type=owner"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def summarize():
    user = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_repos()
    non_forks = [repo for repo in repos if not repo.get("fork")]
    total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    total_forks = sum(repo.get("forks_count", 0) for repo in repos)
    language_counts = {}
    for repo in non_forks:
        lang = repo.get("language") or "Other"
        language_counts[lang] = language_counts.get(lang, 0) + 1
    top_languages = sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    return {
        "user": user,
        "repos": repos,
        "non_forks": non_forks,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "top_languages": top_languages,
    }


def metric_card(x, y, title, value, accent="#22C55E"):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="250" height="96" rx="16" fill="#111827" stroke="{accent}" stroke-opacity="0.45"/>
      <text x="22" y="34" fill="#9CA3AF" font-size="14" font-family="Inter,Segoe UI,Arial">{escape(title)}</text>
      <text x="22" y="72" fill="#FFFFFF" font-size="30" font-weight="800" font-family="Inter,Segoe UI,Arial">{escape(str(value))}</text>
    </g>
    """


def analytics_svg(data):
    user = data["user"]
    top_langs = data["top_languages"] or [("Python", 1)]
    created = user.get("created_at", "")[:10]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lang_total = sum(count for _, count in top_langs) or 1
    bars = []
    y = 354
    colors = ["#22C55E", "#A855F7", "#60A5FA", "#F59E0B", "#EC4899"]
    for i, (name, count) in enumerate(top_langs):
        width = int(430 * count / lang_total)
        color = colors[i % len(colors)]
        bars.append(
            f"""
            <text x="70" y="{y + 14}" fill="#E5E7EB" font-size="14" font-family="Inter,Segoe UI,Arial">{escape(name)}</text>
            <rect x="215" y="{y}" width="430" height="18" rx="9" fill="#1F2937"/>
            <rect x="215" y="{y}" width="{max(width, 18)}" height="18" rx="9" fill="{color}"/>
            <text x="670" y="{y + 14}" fill="#9CA3AF" font-size="13" font-family="Inter,Segoe UI,Arial">{count} projects</text>
            """
        )
        y += 34

    signals = [
        ("Data Science", "Python, statistics, EDA"),
        ("Analytics", "SQL, Excel, Power BI"),
        ("Machine Learning", "Modeling and evaluation"),
        ("GenAI + MLOps", "AI workflows and deployment"),
    ]
    signal_rows = []
    y = 354
    for title, detail in signals:
        signal_rows.append(
            f"""
            <text x="780" y="{y + 14}" fill="#E5E7EB" font-size="14" font-weight="700" font-family="Inter,Segoe UI,Arial">{escape(title)}</text>
            <text x="1085" y="{y + 14}" fill="#9CA3AF" font-size="13" text-anchor="end" font-family="Inter,Segoe UI,Arial">{escape(detail)}</text>
            """
        )
        y += 34

    return f"""<svg width="1160" height="560" viewBox="0 0 1160 560" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1160" y2="560">
      <stop offset="0%" stop-color="#020617"/>
      <stop offset="45%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#312E81"/>
    </linearGradient>
    <linearGradient id="line" x1="0" y1="0" x2="1160" y2="0">
      <stop stop-color="#22C55E"/>
      <stop offset="0.5" stop-color="#A855F7"/>
      <stop offset="1" stop-color="#60A5FA"/>
    </linearGradient>
  </defs>
  <rect width="1160" height="560" rx="26" fill="url(#bg)"/>
  <rect x="1" y="1" width="1158" height="558" rx="25" stroke="url(#line)" stroke-opacity="0.7"/>
  <circle cx="1010" cy="80" r="150" fill="#22C55E" opacity="0.08"/>
  <circle cx="160" cy="480" r="170" fill="#A855F7" opacity="0.10"/>
  <text x="60" y="70" fill="#FFFFFF" font-size="32" font-weight="850" font-family="Inter,Segoe UI,Arial">Live GitHub Analytics</text>
  <text x="60" y="102" fill="#9CA3AF" font-size="15" font-family="Inter,Segoe UI,Arial">Generated from the GitHub API for @{escape(USERNAME)} | {generated}</text>
  {metric_card(60, 142, "Portfolio Projects", user.get("public_repos", 0), "#A855F7")}
  {metric_card(330, 142, "Followers", user.get("followers", 0), "#22C55E")}
  {metric_card(600, 142, "Total Stars", data["total_stars"], "#60A5FA")}
  {metric_card(870, 142, "Total Forks", data["total_forks"], "#F59E0B")}
  <text x="60" y="310" fill="#FFFFFF" font-size="22" font-weight="800" font-family="Inter,Segoe UI,Arial">Top Languages</text>
  <text x="760" y="310" fill="#FFFFFF" font-size="22" font-weight="800" font-family="Inter,Segoe UI,Arial">Career Signal</text>
  {''.join(bars)}
  {''.join(signal_rows)}
  <text x="60" y="525" fill="#9CA3AF" font-size="13" font-family="Inter,Segoe UI,Arial">GitHub since {escape(created)} | Data Science | Analytics | ML | GenAI</text>
</svg>
"""


def trophy_card(x, y, title, subtitle, value, accent):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="332" height="126" rx="18" fill="#111827" stroke="{accent}" stroke-opacity="0.55"/>
      <circle cx="54" cy="63" r="31" fill="{accent}" opacity="0.18"/>
      <path d="M42 45h24v15c0 11-5 20-12 23-7-3-12-12-12-23V45z" fill="{accent}"/>
      <text x="100" y="48" fill="#FFFFFF" font-size="20" font-weight="800" font-family="Inter,Segoe UI,Arial">{escape(title)}</text>
      <text x="100" y="76" fill="#9CA3AF" font-size="13" font-family="Inter,Segoe UI,Arial">{escape(subtitle)}</text>
      <text x="100" y="106" fill="{accent}" font-size="24" font-weight="850" font-family="Inter,Segoe UI,Arial">{escape(str(value))}</text>
    </g>
    """


def trophies_svg(data):
    top_language = (data["top_languages"] or [("Python", 0)])[0][0]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trophies = [
        ("Data Builder", "Portfolio direction", "Analytics + AI", "#22C55E"),
        ("Project Base", "Public portfolio count", data["user"].get("public_repos", 0), "#A855F7"),
        ("Community", "GitHub followers", data["user"].get("followers", 0), "#60A5FA"),
        ("Recognition", "Total repository stars", data["total_stars"], "#F59E0B"),
        ("Top Language", "Primary repo language", top_language, "#EC4899"),
        ("Learning Track", "Current career path", "DS + GenAI", "#14B8A6"),
    ]
    cards = []
    for idx, trophy in enumerate(trophies):
        x = 58 + (idx % 3) * 366
        y = 138 + (idx // 3) * 156
        cards.append(trophy_card(x, y, *trophy))
    return f"""<svg width="1160" height="500" viewBox="0 0 1160 500" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1160" y2="500">
      <stop offset="0%" stop-color="#020617"/>
      <stop offset="45%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#312E81"/>
    </linearGradient>
    <linearGradient id="line" x1="0" y1="0" x2="1160" y2="0">
      <stop stop-color="#22C55E"/>
      <stop offset="0.5" stop-color="#A855F7"/>
      <stop offset="1" stop-color="#60A5FA"/>
    </linearGradient>
  </defs>
  <rect width="1160" height="500" rx="26" fill="url(#bg)"/>
  <rect x="1" y="1" width="1158" height="498" rx="25" stroke="url(#line)" stroke-opacity="0.7"/>
  <circle cx="1010" cy="80" r="150" fill="#A855F7" opacity="0.08"/>
  <circle cx="120" cy="420" r="160" fill="#22C55E" opacity="0.10"/>
  <text x="60" y="72" fill="#FFFFFF" font-size="32" font-weight="850" font-family="Inter,Segoe UI,Arial">GitHub Achievement Board</text>
  <text x="60" y="104" fill="#9CA3AF" font-size="15" font-family="Inter,Segoe UI,Arial">Reliable local trophy cards generated from GitHub API data | {generated}</text>
  {''.join(cards)}
</svg>
"""


def main():
    OUT_DIR.mkdir(exist_ok=True)
    data = summarize()
    (OUT_DIR / "github-analytics.svg").write_text(analytics_svg(data), encoding="utf-8")
    (OUT_DIR / "github-trophies.svg").write_text(trophies_svg(data), encoding="utf-8")


if __name__ == "__main__":
    main()
