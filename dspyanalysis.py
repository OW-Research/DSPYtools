# This is from https://dspy.ai/tutorials/llms_txt_generation/ 
import dspy
from pathlib import Path
from typing import List
import utils
from typing import List, Dict, Any

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
      
class LibraryAnalyzer(dspy.Signature):
    """Analyze library documentation to understand core concepts and patterns."""
    library_name: str = dspy.InputField(desc="Name of the library to analyze")
    documentation_content: str = dspy.InputField(desc="Combined documentation content")

    core_concepts: list[str] = dspy.OutputField(desc="Main concepts and components")
    common_patterns: list[str] = dspy.OutputField(desc="Common usage patterns")
    key_methods: list[str] = dspy.OutputField(desc="Important methods and functions")
    installation_info: str = dspy.OutputField(desc="Installation and setup information")
    code_examples: list[str] = dspy.OutputField(desc="Example code snippets found")

class CodeGenerator(dspy.Signature):
    """Generate code examples for specific use cases using the target library."""
    library_info: str = dspy.InputField(desc="Library concepts and patterns")
    use_case: str = dspy.InputField(desc="Specific use case to implement")
    requirements: str = dspy.InputField(desc="Additional requirements or constraints")

    code_example: str = dspy.OutputField(desc="Complete, working code example")
    explanation: str = dspy.OutputField(desc="Step-by-step explanation of the code")
    best_practices: list[str] = dspy.OutputField(desc="Best practices and tips")
    imports_needed: list[str] = dspy.OutputField(desc="Required imports and dependencies")

class DocumentationLearningAgent(dspy.Module):
    """Agent that learns from documentation URLs and generates code examples."""

    def __init__(self):
        super().__init__()
        self.fetcher = DocumentationFetcher()
        self.analyze_docs = dspy.ChainOfThought(LibraryAnalyzer)
        self.generate_code = dspy.ChainOfThought(CodeGenerator)
        self.refine_code = dspy.ChainOfThought(
            "code, feedback -> improved_code: str, changes_made: list[str]"
        )

    def learn_from_urls(self, library_name: str, doc_urls: list[str]) -> Dict:
        """Learn about a library from its documentation URLs."""

        print(f"📚 Learning about {library_name} from {len(doc_urls)} URLs...")

        # Fetch all documentation
        docs = self.fetcher.fetch_documentation(doc_urls)

        # Combine successful fetches
        combined_content = "\n\n---\n\n".join([
            f"URL: {doc['url']}\nTitle: {doc['title']}\n\n{doc['content']}"
            for doc in docs if doc['success']
        ])

        if not combined_content:
            raise ValueError("No documentation could be fetched successfully")

        # Analyze combined documentation
        analysis = self.analyze_docs(
            library_name=library_name,
            documentation_content=combined_content
        )

        return {
            "library": library_name,
            "source_urls": [doc['url'] for doc in docs if doc['success']],
            "core_concepts": analysis.core_concepts,
            "patterns": analysis.common_patterns,
            "methods": analysis.key_methods,
            "installation": analysis.installation_info,
            "examples": analysis.code_examples,
            "fetched_docs": docs
        }

    def generate_example(self, library_info: Dict, use_case: str, requirements: str = "") -> Dict:
        """Generate a code example for a specific use case."""

        # Format library information for the generator
        info_text = f"""
        Library: {library_info['library']}
        Core Concepts: {', '.join(library_info['core_concepts'])}
        Common Patterns: {', '.join(library_info['patterns'])}
        Key Methods: {', '.join(library_info['methods'])}
        Installation: {library_info['installation']}
        Example Code Snippets: {'; '.join(library_info['examples'][:3])}  # First 3 examples
        """

        code_result = self.generate_code(
            library_info=info_text,
            use_case=use_case,
            requirements=requirements
        )

        return {
            "code": code_result.code_example,
            "explanation": code_result.explanation,
            "best_practices": code_result.best_practices,
            "imports": code_result.imports_needed
        }


