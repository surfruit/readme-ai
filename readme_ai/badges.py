"""Generate shields.io badges for README."""

from __future__ import annotations

from readme_ai.analyzer import ProjectInfo

LANG_COLORS: dict[str, str] = {
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "TypeScript": "3178C6",
    "Go": "00ADD8",
    "Rust": "CE4A02",
    "Ruby": "CC342D",
    "Java": "007396",
    "Kotlin": "7F52FF",
    "Swift": "F05138",
    "C++": "00599C",
    "C": "A8B9CC",
    "C#": "512BD4",
    "PHP": "777BB4",
}


def _badge(label: str, message: str, color: str, style: str = "flat-square", logo: str = "") -> str:
    label_enc = label.replace("-", "--").replace("_", "__").replace(" ", "_")
    msg_enc = message.replace("-", "--").replace("_", "__").replace(" ", "_")
    url = f"https://img.shields.io/badge/{label_enc}-{msg_enc}-{color}?style={style}"
    if logo:
        url += f"&logo={logo}"
    return f"![{label}]({url})"


def generate_badges(info: ProjectInfo) -> str:
    """Return a row of markdown badges for the project."""
    badges: list[str] = []

    # Language badge
    lang = info.language
    color = LANG_COLORS.get(lang, "grey")
    logo = lang.lower().replace("+", "plus").replace("#", "sharp")
    badges.append(_badge(lang, lang, color, logo=logo))

    # License
    if info.license_type:
        badges.append(_badge("License", info.license_type, "green"))

    # CI badge (GitHub Actions)
    if info.has_ci and info.repo_url and "github.com" in info.repo_url:
        parts = info.repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[-2], parts[-1]
            ci_url = f"https://github.com/{owner}/{repo}/actions/workflows/ci.yml/badge.svg"
            badges.append(f"![CI]({ci_url})")

    # Python version
    if info.python_version:
        ver = info.python_version.lstrip(">=~^")
        badges.append(_badge("python", ver, "3776AB", logo="python"))

    # Docker
    if info.has_docker:
        badges.append(_badge("Docker", "ready", "2496ED", logo="docker"))

    # PRs welcome
    badges.append(_badge("PRs", "welcome", "brightgreen"))

    return " ".join(badges)
