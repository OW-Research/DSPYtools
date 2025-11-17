<!-- Auto-generated guidance for AI coding agents working on DSPYtools -->
# DSPYtools — Copilot Instructions

Summary
- Purpose: DSPYtools is a small toolkit that analyzes GitHub repositories and documentation to generate `llms.txt` and library usage examples using the `dspy` framework.
- Key components: repository analyzer (`dspyanalysis.py`), helpers and fetchers (`utils.py`), interactive/example runner (`gencode.py`), and the CLI/entrypoint that generates `llms.txt` (`run.py`).

Quick start (developer environment)
- Set environment variables in a `.env` or the shell:
  - `openai_key2` : API key used in `gencode.py` and `run.py` for the LLM.
  - `GITHUB_ACCESS_TOKEN` : token used by `utils.get_github_file_tree` and file content fetches.
- Use the provided `uv` helper to manage virtual environments (instead of `venv`).
  - Create an environment: `./scripts/uv create .venv`
  - Install dependencies: `./scripts/uv install .venv`
  - Run commands inside the env: `./scripts/uv run .venv python run.py`
- Dependencies: a canonical `requirements.txt` is present at the repo root. Install via the `uv` helper or manually with `pip install -r requirements.txt`.
- Run examples:
  - Generate llms.txt: `python3 run.py` (edit the `url` in the `__main__` block to target a repo).
  - Run the interactive generator: `python3 gencode.py` (it runs `run_example` in `__main__`).

Architecture and patterns (what to know)
- dspy-first design: Many classes inherit from `dspy.Signature` and `dspy.Module` and use `dspy.ChainOfThought`. Inspect `dspyanalysis.py` for example signatures (AnalyzeRepository, AnalyzeCodeStructure, GenerateLLMsTxt).
- Separation of concerns:
  - `utils.py`: GitHub API wrappers, cloning, ctags collection, HTML -> markdown conversion, and the `DocumentationFetcher` used by higher-level agents.
  - `dspyanalysis.py`: high-level LLM-driven analysis flows and example generation. This file is the canonical place to extend the analysis pipeline.
  - `gencode.py`: user-facing interactive learning session and examples of how to call the agent APIs.
  - `run.py`: thin entrypoint that wires `RepositoryAnalyzer` and `utils.gather_repository_info` to produce `llms.txt`.

Project-specific conventions and gotchas
- Environment variable names: the code expects `openai_key2` (not `OPENAI_API_KEY`) and `GITHUB_ACCESS_TOKEN`. Keep those exact names or update code consistently.
- Model configuration: the LLM is instantiated inline in multiple places, e.g. `dspy.LM("openai/gpt-4o-mini", api_key=key)` — change model strings in both `gencode.py` and `run.py` when switching models.
- Requirements filename is misspelled: `requirments.txt`. Do not assume `requirements.txt` exists; double-check package manifests before installing.
- Branch fallback: `utils.get_url` attempts `main` then falls back to `master` automatically — useful when adding repo fetch logic.
- Temporary repo clones and ctags: `collect_cpp_ctags` clones to `/tmp/<repo>` and expects `ctags` to be installed. Be cautious when running on remote CI or limited containers.

Integration points & external dependencies
- GitHub REST API: used in `utils.get_github_file_tree` and `get_github_file_content`.
- OpenAI/dspy LMs: configured via `dspy.LM` and `dspy.settings.configure(lm=lm)` in `gencode.py` and `run.py`.
- Network calls and scraping: `DocumentationFetcher` uses `requests`, `BeautifulSoup`, and `html2text` and sets a polite delay between requests.

Where to make common edits (examples)
- Change the LLM model or api_key:
  - Edit the `dspy.LM(...)` line in `gencode.py` and `run.py`.
- Change the repository target for llms generation:
  - Edit the `url` variable in `run.py` or call `generate_llms_txt_for_dspy` with a new URL.
- Add new analysis steps or outputs:
  - Add a new `dspy.Signature` in `dspyanalysis.py` and wire it into `RepositoryAnalyzer.__init__` as another `ChainOfThought`.
- Extend documentation fetching logic:
  - Modify `DocumentationFetcher.fetch_url` in `utils.py` (content conversion and excluded tags live there).

Searchable anchors (key files to open first)
- `dspyanalysis.py` — core LLM signatures and pipeline
- `utils.py` — GitHub fetching, cloning, ctags, HTML->markdown, `DocumentationFetcher`
- `gencode.py` — interactive session and example flows
- `run.py` — llms.txt generation entrypoint
- `docanalyzer.py` — currently minimal/placeholder imports; intended for additional analyzer utilities

Behavioral norms for AI code edits
- Preserve environment variable names unless you change all call sites.
- Keep LLM wiring and `dspy.settings.configure` calls consistent across entrypoints.
- Avoid changing network retry semantics without testing; many flows assume `DocumentationFetcher` will return combined markdown.
- When adding new files, update `gather_repository_info` and `RepositoryAnalyzer` wiring if the file is an entrypoint.


---

## Extending DSPYtools: Agents, Reference Finder, and SVG Visualization

### Adding a New Agent to Process the Flow
- Create a new class inheriting from `dspy.Module` (see `RepositoryAnalyzer` or `DocumentationLearningAgent` in `dspyanalysis.py`).
- Implement your flow using `dspy.ChainOfThought` and custom `dspy.Signature` classes for each step.
- Register your agent in the entrypoint (`run.py` or `gencode.py`) and wire it into the CLI or interactive session as needed.
- Example stub:
  ```python
  class MyFlowAgent(dspy.Module):
      def __init__(self):
          super().__init__()
          self.step1 = dspy.ChainOfThought(MyStepSignature)
      def forward(self, ...):
          ... # Compose steps
  ```

### Implementing a Tool to Find Relevant References
- Add a function in `utils.py` (or a new module) that takes a symbol or keyword and searches the codebase for references.
- Use Python's `ast` or regex for local analysis, or leverage GitHub API for remote repos.
- Expose this as a callable from your agent or CLI.
- Example stub:
  ```python
  def find_references(symbol: str, file_tree: list[str]) -> list[str]:
      # Search for symbol in all files
      ...
  ```

### Implementing a Tool to Create SVG (XML) Visualizations
- Add a function or class (e.g., `create_svg_visualization(data)`) in a new or existing module.
- Use string formatting or an XML library to generate SVG markup.
- Save the SVG as a `.svg` file or return the XML string for downstream use.
- Example stub:
  ```python
  def create_svg_visualization(data: dict) -> str:
      # Build SVG XML as a string
      svg = f'<svg ...>...</svg>'
      return svg
  ```

If you need a concrete example or want to wire these into the CLI, ask for a code sample or PR.
