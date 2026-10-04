import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone


USERNAME = os.getenv("GITHUB_USERNAME", "prakash0604")
TOKEN = os.getenv("GITHUB_TOKEN")

API_URL = "https://api.github.com"


def github_request(path):
    url = API_URL + path

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-profile-stats",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        raise RuntimeError(
            f"GitHub API error {error.code}: {body}"
        )


def graphql_request(query, variables):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({
            "query": query,
            "variables": variables,
        }).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-profile-stats",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))

            if "errors" in result:
                raise RuntimeError(
                    json.dumps(result["errors"], indent=2)
                )

            return result["data"]

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        raise RuntimeError(
            f"GitHub GraphQL error {error.code}: {body}"
        )


def escape_xml(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_number(number):
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"

    if number >= 1_000:
        return f"{number / 1_000:.1f}K"

    return str(number)


def get_user():
    return github_request(f"/users/{USERNAME}")


def get_repositories():
    repositories = []

    page = 1

    while True:
        data = github_request(
            f"/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner"
        )

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

    return repositories


def get_languages(repo):
    owner = repo["owner"]["login"]
    name = repo["name"]

    try:
        return github_request(
            f"/repos/{owner}/{name}/languages"
        )
    except Exception:
        return {}


def calculate_languages(repositories):
    totals = {}

    for repo in repositories:
        if repo.get("fork"):
            continue

        languages = get_languages(repo)

        for language, bytes_count in languages.items():
            totals[language] = totals.get(language, 0) + bytes_count

    return sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True
    )


def get_contributions():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """

    data = graphql_request(
        query,
        {"login": USERNAME}
    )

    return (
        data["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"]
    )


def build_stats():
    user = get_user()
    repositories = get_repositories()

    total_stars = sum(
        repo.get("stargazers_count", 0)
        for repo in repositories
        if not repo.get("fork")
    )

    total_forks = sum(
        repo.get("forks_count", 0)
        for repo in repositories
        if not repo.get("fork")
    )

    languages = calculate_languages(repositories)

    contributions = get_contributions()

    return {
        "repositories": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "stars": total_stars,
        "forks": total_forks,
        "contributions": contributions,
        "languages": languages[:6],
    }


def svg_text(
    x,
    y,
    text,
    size=14,
    weight="400",
    fill="#c9d1d9",
    anchor="start"
):
    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}px" '
        f'font-weight="{weight}" '
        f'fill="{fill}" '
        f'text-anchor="{anchor}">'
        f'{escape_xml(text)}</text>'
    )


def generate_svg(stats):
    width = 900
    height = 520

    background = "#0d1117"
    border = "#30363d"
    primary = "#f0f6fc"
    secondary = "#8b949e"
    accent = "#58a6ff"
    bar_background = "#21262d"

    svg = []

    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    svg.append(
        f'<rect width="{width}" height="{height}" '
        f'rx="12" fill="{background}" '
        f'stroke="{border}" stroke-width="1"/>'
    )

    # Header
    svg.append(
        svg_text(
            40,
            50,
            f"{USERNAME}'s GitHub",
            size=24,
            weight="700",
            fill=primary,
        )
    )

    svg.append(
        svg_text(
            40,
            77,
            "GitHub activity and development stack",
            size=13,
            fill=secondary,
        )
    )

    # Stats cards
    cards = [
        ("Repositories", stats["repositories"]),
        ("Followers", stats["followers"]),
        ("Stars", stats["stars"]),
        ("Forks", stats["forks"]),
        ("Contributions", stats["contributions"]),
    ]

    card_width = 155
    card_height = 82
    gap = 15
    start_x = 40
    start_y = 105

    for index, (label, value) in enumerate(cards):
        x = start_x + index * (card_width + gap)

        svg.append(
            f'<rect x="{x}" y="{start_y}" '
            f'width="{card_width}" height="{card_height}" '
            f'rx="8" fill="{bar_background}" '
            f'stroke="{border}" stroke-width="1"/>'
        )

        svg.append(
            svg_text(
                x + 15,
                start_y + 27,
                label,
                size=12,
                fill=secondary,
            )
        )

        svg.append(
            svg_text(
                x + 15,
                start_y + 57,
                format_number(value),
                size=23,
                weight="700",
                fill=primary,
            )
        )

    # Primary stack
    svg.append(
        svg_text(
            40,
            235,
            "Primary Stack",
            size=18,
            weight="700",
            fill=primary,
        )
    )

    svg.append(
        svg_text(
            40,
            258,
            "Technologies I mainly work with",
            size=12,
            fill=secondary,
        )
    )

    stack = [
        ("PHP", 100),
        ("Laravel", 92),
        ("JavaScript", 70),
        ("jQuery", 64),
        ("MySQL", 55),
        ("PostgreSQL", 48),
    ]

    y = 290

    for language, percentage in stack:
        svg.append(
            svg_text(
                40,
                y,
                language,
                size=13,
                weight="600",
                fill=primary,
            )
        )

        svg.append(
            f'<rect x="145" y="{y - 12}" '
            f'width="600" height="10" rx="5" '
            f'fill="{bar_background}"/>'
        )

        svg.append(
            f'<rect x="145" y="{y - 12}" '
            f'width="{percentage * 5.2}" height="10" '
            f'rx="5" fill="{accent}"/>'
        )

        y += 32

    # GitHub detected languages
    svg.append(
        svg_text(
            40,
            490,
            "Languages detected in repositories:",
            size=11,
            fill=secondary,
        )
    )

    detected = [
        language
        for language, _ in stats["languages"]
    ]

    detected_text = ", ".join(detected) if detected else "No data"

    svg.append(
        svg_text(
            250,
            490,
            detected_text,
            size=11,
            fill=secondary,
        )
    )

    svg.append("</svg>")

    return "\n".join(svg)


def main():
    os.makedirs("assets", exist_ok=True)

    stats = build_stats()

    svg = generate_svg(stats)

    with open(
        "assets/github-stats.svg",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(svg)

    print(json.dumps(stats, indent=2))
    print("GitHub stats generated successfully.")


if __name__ == "__main__":
    main()
