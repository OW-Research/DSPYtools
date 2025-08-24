# This is from https://dspy.ai/tutorials/llms_txt_generation/ 
import dspy
import requests
import os
from pathlib import Path

from typing import List

class AnalyzeRepository(dspy.Signature):
    """Analyze a repository structure and identify key components."""
    repo_url: str = dspy.InputField(desc="GitHub repository URL")
    file_tree: str = dspy.InputField(desc="Repository file structure")
    readme_content: str = dspy.InputField(desc="README content")

    project_purpose: str = dspy.OutputField(desc="Main purpose and goals of the project")
    key_concepts: list[str] = dspy.OutputField(desc="List of important concepts and terminology")
    architecture_overview: str = dspy.OutputField(desc="High-level architecture description")

class AnalyzeCodeStructure(dspy.Signature):
    """Analyze code structure to identify important directories and files."""
    file_tree: str = dspy.InputField(desc="Repository file structure")
    package_files: str = dspy.InputField(desc="Key package and configuration files")

    important_directories: list[str] = dspy.OutputField(desc="Key directories and their purposes")
    entry_points: list[str] = dspy.OutputField(desc="Main entry points and important files")
    development_info: str = dspy.OutputField(desc="Development setup and workflow information")

class GenerateLLMsTxt(dspy.Signature):
    """Generate a comprehensive llms.txt file from analyzed repository information."""
    project_purpose: str = dspy.InputField()
    key_concepts: list[str] = dspy.InputField()
    architecture_overview: str = dspy.InputField()
    important_directories: list[str] = dspy.InputField()
    entry_points: list[str] = dspy.InputField()
    development_info: str = dspy.InputField()
    usage_examples: str = dspy.InputField(desc="Common usage patterns and examples")

    llms_txt_content: str = dspy.OutputField(desc="Complete llms.txt file content following the standard format")

class RepositoryAnalyzer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze_repo = dspy.ChainOfThought(AnalyzeRepository)
        self.analyze_structure = dspy.ChainOfThought(AnalyzeCodeStructure)
        self.generate_examples = dspy.ChainOfThought("repo_info -> usage_examples")
        self.generate_llms_txt = dspy.ChainOfThought(GenerateLLMsTxt)

    def forward(self, repo_url, file_tree, readme_content, package_files):
        # Analyze repository purpose and concepts
        print(len(file_tree))
        print(len(readme_content))
        repo_analysis = self.analyze_repo(
            repo_url=repo_url,
            file_tree=file_tree,
            readme_content=readme_content
        )

        # Analyze code structure
        structure_analysis = self.analyze_structure(
            file_tree=file_tree,
            package_files=package_files
        )

        # Generate usage examples
        usage_examples = self.generate_examples(
            repo_info=f"Purpose: {repo_analysis.project_purpose}\nConcepts: {repo_analysis.key_concepts}"
        )

        # Generate final llms.txt
        llms_txt = self.generate_llms_txt(
            project_purpose=repo_analysis.project_purpose,
            key_concepts=repo_analysis.key_concepts,
            architecture_overview=repo_analysis.architecture_overview,
            important_directories=structure_analysis.important_directories,
            entry_points=structure_analysis.entry_points,
            development_info=structure_analysis.development_info,
            usage_examples=usage_examples.usage_examples
        )

        return dspy.Prediction(
            llms_txt_content=llms_txt.llms_txt_content,
            analysis=repo_analysis,
            structure=structure_analysis
        )
      
def get_url(owner, repo, branch="main"):
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        
        response = requests.get(api_url, headers={
            "Authorization": f"Bearer {os.environ.get('GITHUB_ACCESS_TOKEN')}"
        })
        if response.status_code != 200:
            raise Exception(f"Failed to fetch repository tree: {response.status_code}")
    except Exception as e:
        print(branch)
        if branch=="main":
            return get_url(owner, repo, branch="master")
        else:            
            raise e

    return response



def get_github_file_tree(repo_url):
    """Get repository file structure from GitHub API."""
    # Extract owner/repo from URL
    parts = repo_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]
    response= get_url(owner, repo)
    if response.status_code == 200:
        tree_data = response.json()
        file_paths = [item['path'] for item in tree_data['tree'] if item['type'] == 'blob']
        return sorted(file_paths)
    else:
        raise Exception(f"Failed to fetch repository tree: {response.status_code}")

def get_github_file_content(repo_url, file_path):
    """Get specific file content from GitHub."""
    parts = repo_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    response = requests.get(api_url, headers={
        "Authorization": f"Bearer {os.environ.get('GITHUB_ACCESS_TOKEN')}"
    })

    if response.status_code == 200:
        import base64
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        return content
    else:
        return f"Could not fetch {file_path}"

def gather_repository_info(repo_url):
    """Gather all necessary repository information."""
    file_tree = get_github_file_tree(repo_url)
    matches=[]
    #print(type(file_tree))
    for s in file_tree:
        #print(s)
        if "README" in s:
        #    print("<<<<<<<<<<<<<<"+s)
            matches.append(s)
    #matches = [s for s in file_tree if "README" in s]
    #print(matches)
    readme_content=""
    if len(matches)>0:
        #print(matches)
        readme_content = get_github_file_content(repo_url, matches[0])
        #print(readme_content)
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
    file_tree_txt= '\n'.join(sorted(file_tree))
    return file_tree_txt, readme_content, package_files_content
