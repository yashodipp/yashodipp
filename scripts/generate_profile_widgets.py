#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
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


def fetch_graphql(query, variables):
    if not TOKEN:
        return None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "profile-widget-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errors"):
        return None
    return result.get("data")


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


def contribution_summary():
    today = datetime.now(timezone.utc).date()
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": f"{today - timedelta(days=370)}T00:00:00Z",
        "to": f"{today}T23:59:59Z",
    }
    data = fetch_graphql(query, variables)
    calendar = (
        data
        and data.get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar")
    )
    if calendar:
        days = []
        for week in calendar.get("weeks", []):
            for item in week.get("contributionDays", []):
                days.append(
                    {
                        "date": item.get("date"),
                        "count": item.get("contributionCount", 0),
                        "color": item.get("color") or "#161B22",
                    }
                )
        return {
            "days": days,
            "total": calendar.get("totalContributions", 0),
            "source": "GitHub GraphQL API",
        }

    counts = {}
    try:
        events = fetch_json(f"https://api.github.com/users/{USERNAME}/events/public?per_page=100")
        for event in events:
            event_date = event.get("created_at", "")[:10]
            if event_date:
                counts[event_date] = counts.get(event_date, 0) + 1
    except Exception:
        events = []

    days = []
    for offset in range(370, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        days.append({"date": key, "count": counts.get(key, 0), "color": contribution_color(counts.get(key, 0))})
    return {
        "days": days,
        "total": sum(counts.values()),
        "source": "Public Events API fallback",
    }


def contribution_color(count):
    if count <= 0:
        return "#161B22"
    if count == 1:
        return "#0E4429"
    if count <= 3:
        return "#006D32"
    if count <= 6:
        return "#26A641"
    return "#39D353"


def streak_metrics(summary):
    counts = {}
    colors = {}
    for item in summary["days"]:
        if not item.get("date"):
            continue
        day = datetime.strptime(item["date"], "%Y-%m-%d").date()
        counts[day] = item.get("count", 0)
        colors[day] = item.get("color") or contribution_color(item.get("count", 0))

    today = datetime.now(timezone.utc).date()
    cursor = today
    if counts.get(cursor, 0) == 0 and counts.get(cursor - timedelta(days=1), 0) > 0:
        cursor -= timedelta(days=1)

    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    active_days = 0
    for day in sorted(counts):
        if counts[day] > 0:
            run += 1
            active_days += 1
            longest = max(longest, run)
        else:
            run = 0

    last_active = max((day for day, count in counts.items() if count > 0), default=None)
    return {
        "counts": counts,
        "colors": colors,
        "current": current,
        "longest": longest,
        "active_days": active_days,
        "last_active": last_active.isoformat() if last_active else "No public activity yet",
    }


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


def streak_svg(summary):
    metrics = streak_metrics(summary)
    today = datetime.now(timezone.utc).date()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    start = today - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    cells = []
    cell = 10
    gap = 3
    grid_x = 60
    grid_y = 276
    for offset in range((today - start).days + 1):
        day = start + timedelta(days=offset)
        week = offset // 7
        weekday = (day.weekday() + 1) % 7
        count = metrics["counts"].get(day, 0)
        color = metrics["colors"].get(day) or contribution_color(count)
        if count <= 0:
            color = "#161B22"
        cells.append(
            f'<rect x="{grid_x + week * (cell + gap)}" y="{grid_y + weekday * (cell + gap)}" '
            f'width="{cell}" height="{cell}" rx="2" fill="{escape(color)}">'
            f'<title>{day.isoformat()}: {count} contributions</title></rect>'
        )

    legend = []
    legend_colors = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]
    for idx, color in enumerate(legend_colors):
        legend.append(
            f'<rect x="{905 + idx * 18}" y="330" width="11" height="11" rx="2" fill="{color}"/>'
        )

    return f"""<svg width="1160" height="400" viewBox="0 0 1160 400" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1160" y2="400">
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
  <rect width="1160" height="400" rx="26" fill="url(#bg)"/>
  <rect x="1" y="1" width="1158" height="398" rx="25" stroke="url(#line)" stroke-opacity="0.7"/>
  <circle cx="1020" cy="80" r="145" fill="#22C55E" opacity="0.08"/>
  <circle cx="125" cy="350" r="145" fill="#A855F7" opacity="0.10"/>
  <text x="60" y="70" fill="#FFFFFF" font-size="32" font-weight="850" font-family="Inter,Segoe UI,Arial">Live Contribution Streak</text>
  <text x="60" y="102" fill="#9CA3AF" font-size="15" font-family="Inter,Segoe UI,Arial">Generated from {escape(summary["source"])} for @{escape(USERNAME)} | {generated}</text>
  {metric_card(60, 136, "Current Streak", f'{metrics["current"]} days', "#22C55E")}
  {metric_card(330, 136, "Longest Streak", f'{metrics["longest"]} days', "#A855F7")}
  {metric_card(600, 136, "Year Contributions", summary["total"], "#60A5FA")}
  {metric_card(870, 136, "Active Days", metrics["active_days"], "#F59E0B")}
  <text x="60" y="256" fill="#FFFFFF" font-size="20" font-weight="800" font-family="Inter,Segoe UI,Arial">Contribution Calendar</text>
  <text x="905" y="256" fill="#FFFFFF" font-size="20" font-weight="800" font-family="Inter,Segoe UI,Arial">Last Active</text>
  <text x="905" y="285" fill="#22C55E" font-size="22" font-weight="850" font-family="Inter,Segoe UI,Arial">{escape(metrics["last_active"])}</text>
  {''.join(cells)}
  <text x="905" y="340" fill="#9CA3AF" font-size="13" font-family="Inter,Segoe UI,Arial">Less</text>
  {''.join(legend)}
  <text x="1010" y="340" fill="#9CA3AF" font-size="13" font-family="Inter,Segoe UI,Arial">More</text>
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
    contributions = contribution_summary()
    (OUT_DIR / "github-analytics.svg").write_text(analytics_svg(data), encoding="utf-8")
    (OUT_DIR / "github-streak.svg").write_text(streak_svg(contributions), encoding="utf-8")
    (OUT_DIR / "github-trophies.svg").write_text(trophies_svg(data), encoding="utf-8")


if __name__ == "__main__":
    main()
