"""
This script automates the release process for a Python package. It will:
- Add a git tag for the given version.
- Remove the previous dist folder.
- Create a build.
- Ask the user to verify the build.
- Upload the build to PyPI.
- Push all git tags to the remote.
- Create a draft release on GitHub using the version notes in CHANGELOG.md.
"""

import json
import os
import re
import subprocess
import sys

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
is_test = None
version_number = None


def add_git_tag_for_version(version: str) -> None:
    """Add a git tag for the given version."""
    subprocess.run(["git", "tag", "-a", version, "-m", version], check=True)
    print(f"Version {version} tag added successfully.")


def remove_previous_dist() -> None:
    """Check for dist folder, and if it exists, remove it."""
    subprocess.run(["rm", "-rf", "dist/"], check=True)
    print("Previous dist folder removed successfully.")


def create_build() -> None:
    """Create a build."""
    subprocess.run(["python", "-m", "build"], check=True)
    print("Build created successfully.")


def verify_build() -> None:
    """Verify the build."""
    if len(os.listdir("dist")) != 2:
        print(
            "WARNING: dist folder contains incorrect number of files.", file=sys.stderr
        )
    print("Contents of dist folder:")
    subprocess.run(["ls", "-l", "dist/"], check=True)
    print("Contents of tar files in dist folder:")
    for directory in os.listdir("dist"):
        subprocess.run(["tar", "tvf", "dist/" + directory], check=True)
    confirmation = input("Does the build look correct? (y/n): ")
    if confirmation == "y":
        print("Build verified successfully.")
        upload_build_to_pypi()
        push_git_tags()
    else:
        raise Exception("Could not verify. Build was not uploaded.")


def generate_github_release_notes_body(version) -> str:
    """Generate and grab release notes URL from Github."""
    try:
        command = [
            "curl",
            "-L",
            "-X",
            "POST",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            f"Authorization: Bearer {GITHUB_TOKEN}",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            "https://api.github.com/repos/ekcorso/releasetestrepo2/releases/generate-notes",
            "-d",
            f'{{"tag_name":"{version_number}"}}',
        ]
        response_json = subprocess.run(command, check=True, capture_output=True)
        parsed_json = json.loads(response_json.stdout)
        body = parsed_json["body"]
        return body
    except subprocess.CalledProcessError as error:
        print(
            f"WARNING: Failed to generate release notes from Github: {error}",
            file=sys.stderr,
        )
        return ""


def get_release_notes_url(body) -> str:
    """Parse the release notes content to get the changelog URL."""
    url_pattern = re.compile(r"\*\*Full Changelog\*\*: (.*)$")
    match = url_pattern.search(body)
    if match:
        return match.group(1)
    else:
        print(
            "WARNING: Failed to parse release notes URL from GitHub response.",
            file=sys.stderr,
        )
        return ""


def get_changelog_release_notes(release_notes_url) -> str:
    """Get the changelog release notes.

    Uses a regex starting on a heading beginning with the version number literal, and matching until the next heading. Using regex to match markup is brittle. Consider a Markdown-parsing library instead.
    """

    changelog_text = None
    with open("CHANGELOG.md") as file:

        changelog_text = file.read()
    pattern = re.compile(rf"## {re.escape(version_number)}[^\n]*(.*?)## ", re.DOTALL)
    match = pattern.search(changelog_text)
    if match:
        return str(match.group(1)).strip()
    else:
        print(
            f"WARNING: Failed to parse changelog release notes. Manually copy this version's notes from the CHANGELOG.md file to {release_notes_url}.",
            file=sys.stderr,
        )
        return ""


def create_release_notes_body() -> str:
    """Compile the release notes."""
    github_release_body = generate_github_release_notes_body(version_number)
    release_notes_url = get_release_notes_url(github_release_body)
    changelog_notes = get_changelog_release_notes(release_notes_url)
    full_release_notes = (
        changelog_notes + "\n\n**Full Changelog**: " + release_notes_url
    )
    return full_release_notes


def create_github_release_draft() -> None:
    """Create a release on GitHub."""
    release_body = create_release_notes_body()
    release_body = release_body.replace("\n", "\\n")
    command = [
        "curl",
        "-L",
        "-X",
        "POST",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"Authorization: Bearer {GITHUB_TOKEN}",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        "https://api.github.com/repos/ekcorso/releasetestrepo2/releases",
        "-d",
        f'{{"tag_name":"{version_number}","name":"{version_number}","body":"{release_body}","draft":true,"prerelease":false}}',
    ]
    response_json = subprocess.run(command, check=True, capture_output=True)
    parsed_json = json.loads(response_json.stdout)
    if "html_url" in parsed_json:
        print("Release created successfully: " + parsed_json["html_url"])
    else:
        print(
            "WARNING: There may have been an error creating this release. Visit https://github.com/john-kurkowski/tldextract/releases to confirm release was created.",
            file=sys.stderr,
        )


def upload_build_to_pypi() -> None:
    """Upload the build to PyPI."""
    if is_test == "n":
        subprocess.run(
            ["twine", "upload", "dist/*"],
            check=True,
        )
    else:
        subprocess.run(
            ["twine", "upload", "--repository", "testpypi", "dist/*"],
            check=True,
        )


def push_git_tags() -> None:
    """Push all git tags to the remote."""
    subprocess.run(["git", "push", "--tags", "origin", "master"], check=True)


def main() -> None:
    """Run the main program."""
    global is_test, version_number

    print("Starting the release process...")
    print("Checking for github token environment variable...")
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN environment variable not set.")
        sys.exit(1)
    else:
        print("GITHUB_TOKEN environment variable is good to go.")

    is_test = input("Is this a test release? (y/n): ")
    while is_test not in ["y", "n"]:
        print("Invalid input. Please enter 'y' or 'n'.")
        is_test = input("Is this a test release? (y/n): ")

    version_number = input("Enter the version number: ")

    add_git_tag_for_version(version_number)
    remove_previous_dist()
    create_build()
    verify_build()
    create_github_release_draft()


if __name__ == "__main__":
    main()
