import shutil
import subprocess
import os
import requests
import html2text
from typing import List, Dict, Any
import json
from urllib.parse import urljoin, urlparse
import time
from bs4 import BeautifulSoup

def get_url(owner, repo, branch="main"):
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        response = requests.get(
            api_url,
            headers={
                "Authorization": f"Bearer {os.environ.get('GITHUB_ACCESS_TOKEN')}"
            },
        )
        if response.status_code != 200:
            raise Exception(f"Failed to fetch repository tree: {response.status_code}")
    except Exception as e:
        print(branch)
        if branch == "main":
            return get_url(owner, repo, branch="master")
        else:
            raise e

    return response


def get_github_file_tree(repo_url):
    """Get repository file structure from GitHub API."""
    # Extract owner/repo from URL
    parts = repo_url.rstrip("/").split("/")
    owner, repo = parts[-2], parts[-1]
    response = get_url(owner, repo)
    if response.status_code == 200:
        tree_data = response.json()
        file_paths = [
            item["path"] for item in tree_data["tree"] if item["type"] == "blob"
        ]
        return sorted(file_paths)
    else:
        raise Exception(f"Failed to fetch repository tree: {response.status_code}")


def get_github_file_content(repo_url, file_path):
    """Get specific file content from GitHub."""
    parts = repo_url.rstrip("/").split("/")
    owner, repo = parts[-2], parts[-1]

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    response = requests.get(
        api_url,
        headers={"Authorization": f"Bearer {os.environ.get('GITHUB_ACCESS_TOKEN')}"},
    )

    if response.status_code == 200:
        import base64

        content = base64.b64decode(response.json()["content"]).decode("utf-8")
        return content
    else:
        return f"Could not fetch {file_path}"


def gather_repository_info(repo_url):
    """Gather all necessary repository information."""
    file_tree = get_github_file_tree(repo_url)
    matches = []
    for s in file_tree:
        if "README" in s:
            matches.append(s)
    readme_content = ""
    if len(matches) > 0:
        readme_content = get_github_file_content(repo_url, matches[0])
    # Get key package files
    package_files = []
    for file_path in ["pyproject.toml", "setup.py", "requirements.txt", "package.json"]:
        try:
            content = get_github_file_content(repo_url, file_path)
            if "Could not fetch" not in content:
                package_files.append(f"=== {file_path} ===\n{content}")
        except:
            continue

    package_files_content = "\n\n".join(package_files)
    file_tree_txt = "\n".join(sorted(file_tree))

    combined_tags = collect_cpp_ctags(repo_url, file_tree)

    return file_tree_txt, readme_content, package_files_content, combined_tags


def clone_repo_to_tmp(repo_url: str) -> str:
    """
    Clone the given GitHub repo into /tmp and return the local path.
    """
    import subprocess
    import re

    repo_name = repo_url.rstrip("/").split("/")[-1]
    local_path = f"/tmp/{repo_name}"
    # Remove if already exists
    if os.path.exists(local_path):
        shutil.rmtree(local_path)
    # Convert https://github.com/owner/repo(.git)? to git clone url
    if repo_url.endswith(".git"):
        clone_url = repo_url
    else:
        clone_url = repo_url + ".git"
    subprocess.run(["git", "clone", "--depth", "1", clone_url, local_path], check=True)
    return local_path


def collect_cpp_ctags(repo_url, file_tree) -> str:
    """
    Iterate over C++ files in root_dir, generate ctags for each, and collect all tags into a single string.
    """
    cpp_extensions = {".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".hxx"}
    tags_output = []
    local_repo_path = clone_repo_to_tmp(repo_url)
    for filename in file_tree:
        ext = os.path.splitext(filename)[1].lower()
        if ext in cpp_extensions:
            local_file_path = os.path.join(local_repo_path, filename)
            if os.path.exists(local_file_path):
                try:
                    print(f"Generating ctags for {local_file_path}")
                    result = subprocess.run([
                            'ctags', '-f', '-', '--fields=+n', local_file_path
                        ], capture_output=True, text=True, check=True)
                    tags_output.append(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"ctags failed for {local_file_path}: {e}")
            else:
                # fallback: fetch and save to /tmp as before
                file_content = get_github_file_content(repo_url, filename)
                tmp_file_path = os.path.basename(filename)
                with open(tmp_file_path, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(file_content)
                    try:
                        result = subprocess.run([
                            'ctags', '-f', '-', '--fields=+n', tmp_file_path
                        ], capture_output=True, text=True, check=True)
                    tags_output.append(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"ctags failed for {tmp_file_path}: {e}")
            finally:
                    os.remove(tmp_file_path)
    return "".join(tags_output)


class DocumentationFetcher:
    """Fetches and processes documentation from URLs."""

    def __init__(self, max_retries=3, delay=1):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.max_retries = max_retries
        self.delay = delay
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True

    def fetch_url(self, url: str) -> dict[str, str]:
        """Fetch content from a single URL."""
        for attempt in range(self.max_retries):
            try:
                print(f"📡 Fetching: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Convert to markdown for better LLM processing
                markdown_content = self.html_converter.handle(str(soup))

                return {
                    "url": url,
                    "title": soup.title.string if soup.title else "No title",
                    "content": markdown_content,
                    "success": True,
                }

            except Exception as e:
                print(f"❌ Error fetching {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay)
                else:
                    return {
                        "url": url,
                        "title": "Failed to fetch",
                        "content": f"Error: {str(e)}",
                        "success": False,
                    }

        return {"url": url, "title": "Failed", "content": "", "success": False}

    def fetch_documentation(self, urls: list[str]) -> list[dict[str, str]]:
        """Fetch documentation from multiple URLs."""
        results = []

        for url in urls:
            result = self.fetch_url(url)
            results.append(result)
            time.sleep(self.delay)  # Be respectful to servers

        return results


def learn_library_from_urls(
    agent, library_name: str, documentation_urls: list[str]
) -> Dict:
    """Learn about any library from its documentation URLs."""

    try:
        library_info = agent.learn_from_urls(library_name, documentation_urls)

        print(f"\n🔍 Library Analysis Results for {library_name}:")
        print(f"Sources: {len(library_info['source_urls'])} successful fetches")
        print(f"Core Concepts: {library_info['core_concepts']}")
        print(f"Common Patterns: {library_info['patterns']}")
        print(f"Key Methods: {library_info['methods']}")
        print(f"Installation: {library_info['installation']}")
        print(f"Found {len(library_info['examples'])} code examples")

        return library_info

    except Exception as e:
        print(f"❌ Error learning library: {e}")
        raise


def generate_examples_for_library(agent, library_info: Dict, library_name: str):
    """Generate code examples for any library based on its documentation."""

    # Define generic use cases that can apply to most libraries
    use_cases = [
        {
            "name": "Basic Setup and Hello World",
            "description": f"Create a minimal working example with {library_name}",
            "requirements": "Include installation, imports, and basic usage",
        },
        {
            "name": "Common Operations",
            "description": f"Demonstrate the most common {library_name} operations",
            "requirements": "Show typical workflow and best practices",
        },
        {
            "name": "Advanced Usage",
            "description": f"Create a more complex example showcasing {library_name} capabilities",
            "requirements": "Include error handling and optimization",
        },
    ]

    generated_examples = []

    print(f"\n🔧 Generating examples for {library_name}...")

    for use_case in use_cases:
        print(f"\n📝 {use_case['name']}")
        print(f"Description: {use_case['description']}")

        example = agent.generate_example(
            library_info=library_info,
            use_case=use_case["description"],
            requirements=use_case["requirements"],
        )

        print("\n💻 Generated Code:")
        print("```python")
        print(example["code"])
        print("```")

        print("\n📦 Required Imports:")
        for imp in example["imports"]:
            print(f"  • {imp}")

        print("\n📝 Explanation:")
        print(example["explanation"])

        print("\n✅ Best Practices:")
        for practice in example["best_practices"]:
            print(f"  • {practice}")

        generated_examples.append(
            {
                "use_case": use_case["name"],
                "code": example["code"],
                "imports": example["imports"],
                "explanation": example["explanation"],
                "best_practices": example["best_practices"],
            }
        )

        print("-" * 80)

    return generated_examples


def learn_any_library(
    agent, library_name: str, documentation_urls: list[str], use_cases: list[str] = None
):
    """Learn any library from its documentation and generate examples."""

    if use_cases is None:
        use_cases = [
            "Basic setup and hello world example",
            "Common operations and workflows",
            "Advanced usage with best practices",
        ]

    print(f"🚀 Starting automated learning for {library_name}...")
    print(f"Documentation sources: {len(documentation_urls)} URLs")

    try:
        # Step 1: Learn from documentation
        library_info = agent.learn_from_urls(library_name, documentation_urls)

        # Step 2: Generate examples for each use case
        all_examples = []

        for i, use_case in enumerate(use_cases, 1):
            print(f"\n📝 Generating example {i}/{len(use_cases)}: {use_case}")

            example = agent.generate_example(
                library_info=library_info,
                use_case=use_case,
                requirements="Include error handling, comments, and follow best practices",
            )

            all_examples.append(
                {
                    "use_case": use_case,
                    "code": example["code"],
                    "imports": example["imports"],
                    "explanation": example["explanation"],
                    "best_practices": example["best_practices"],
                }
            )

        return {"library_info": library_info, "examples": all_examples}

    except Exception as e:
        print(f"❌ Error learning {library_name}: {e}")
        return None
