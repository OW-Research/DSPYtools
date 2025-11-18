import dspy
import requests
from bs4 import BeautifulSoup
#import html2text
from typing import List, Dict, Any
import json
from urllib.parse import urljoin, urlparse
import time
import re
from datetime import datetime
import argparse
import sys
import difflib
import os

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)


# 1. Paragraph Versioning System
class ParagraphVersion:
    """Store a single version of a paragraph with metadata."""
    def __init__(self, content: str, section_title: str = ""):
        self.content = content
        self.section_title = section_title
        self.timestamp = datetime.now().isoformat()
        self.version_id = hash((content, self.timestamp)) % 10000

    def to_dict(self) -> Dict:
        return {
            "version_id": self.version_id,
            "section": self.section_title,
            "content": self.content,
            "timestamp": self.timestamp
        }


class ParagraphHistory:
    """Track all versions of paragraphs in a proposal."""
    def __init__(self):
        self.history: Dict[str, List[ParagraphVersion]] = {}

    def add_version(self, section_title: str, content: str) -> None:
        """Add a new version of a paragraph."""
        if section_title not in self.history:
            self.history[section_title] = []
        self.history[section_title].append(ParagraphVersion(content, section_title))

    def get_versions(self, section_title: str) -> List[Dict]:
        """Get all versions of a paragraph."""
        return [v.to_dict() for v in self.history.get(section_title, [])]

    def save_to_file(self, filename: str = "paragraph_history.json") -> None:
        """Save paragraph history to a JSON file."""
        data = {section: [v.to_dict() for v in versions] for section, versions in self.history.items()}
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filename: str = "paragraph_history.json") -> None:
        """Load paragraph history from a JSON file."""
        with open(filename, "r") as f:
            data = json.load(f)
            for section, versions in data.items():
                self.history[section] = [ParagraphVersion(v["content"], section) for v in versions]


# 2. LaTeX Structure Parser
class LaTeXStructureParser:
    """Parse LaTeX documents and extract structure."""
    
    @staticmethod
    def parse_structure(latex_content: str) -> Dict[str, Any]:
        """Extract structure from LaTeX content."""
        structure = {
            "title": LaTeXStructureParser._extract_title(latex_content),
            "sections": LaTeXStructureParser._extract_sections(latex_content),
            "subsections": LaTeXStructureParser._extract_subsections(latex_content),
            "equations": LaTeXStructureParser._extract_equations(latex_content),
            "citations": LaTeXStructureParser._extract_citations(latex_content),
            "environments": LaTeXStructureParser._extract_environments(latex_content)
        }
        return structure

    @staticmethod
    def _remove_ignore_blocks(latex_content: str) -> str:
        r"""Remove any \ignore{...} blocks (nested braces handled).

        Removes content wrapped in \ignore{...} which is commonly used to
        hide content in LaTeX documents.
        """
        # Remove brace form \ignore{...} with nesting support
        while '\\ignore{' in latex_content:
            latex_content = re.sub(r'\\ignore\{([^{}]|\{[^{}]*\})*\}', '', latex_content, flags=re.DOTALL)
        return latex_content

    @staticmethod
    def parse_paragraphs(latex_content: str) -> List[Dict[str, Any]]:
        r"""Parse LaTeX content into paragraphs with section/subsection hierarchy.

        Returns a list of dicts with structure:
        {
            "index": int,
            "section": str (section title or empty),
            "subsection": str (subsection title or empty),
            "paragraph": str (cleaned paragraph text),
            "is_in_environment": bool (True if inside itemize, enumerate, etc.)
        }

        - Removes \ignore{...} blocks before parsing
        - Preserves section/subsection hierarchy
        - Splits paragraphs on blank lines (2+ newlines)
        - Filters out LaTeX commands and environments
        """
        content = LaTeXStructureParser._remove_ignore_blocks(latex_content)

        # Remove LaTeX preamble (everything before \begin{document})
        match = re.search(r'\\begin\{document\}', content)
        if match:
            content = content[match.end():]

        # Remove \end{document} and anything after
        content = re.sub(r'\\end\{document\}.*', '', content, flags=re.DOTALL)

        # Normalize line endings
        content = content.replace('\r\n', '\n')

        # Extract section and subsection positions with their titles
        sections_map = []
        for m in re.finditer(r'\\section\*?\{([^}]+)\}', content):
            sections_map.append((m.start(), m.group(1), 'section'))
        for m in re.finditer(r'\\subsection\*?\{([^}]+)\}', content):
            sections_map.append((m.start(), m.group(1), 'subsection'))
        sections_map.sort(key=lambda x: x[0])

        # Split into raw paragraphs on blank lines (2+ newlines)
        raw_paras = re.split(r'\n\n+', content)

        paragraphs = []
        current_section = ""
        current_subsection = ""
        section_pos = 0

        for idx, raw_para in enumerate(raw_paras):
            para = raw_para.strip()
            if not para:
                continue

            # Skip pure LaTeX structure lines (section/subsection definitions)
            if para.startswith('\\section') or para.startswith('\\subsection'):
                continue

            # Skip \maketitle and other document markup
            if para in ('\\maketitle', '\\tableofcontents', '\\begin{document}', '\\end{document}'):
                continue

            # Update current section/subsection based on position
            para_pos = content.find(para, section_pos)
            if para_pos == -1:
                para_pos = section_pos
            section_pos = para_pos + len(para)

            for s_pos, title, s_type in sections_map:
                if s_pos <= para_pos:
                    if s_type == 'section':
                        current_section = title
                        current_subsection = ""
                    elif s_type == 'subsection':
                        current_subsection = title
                else:
                    break

            # Clean up the paragraph: remove LaTeX-specific markup
            cleaned = LaTeXStructureParser._clean_paragraph_text(para)
            
            if not cleaned:
                continue

            # Detect if inside an environment (itemize, enumerate)
            in_env = bool(re.search(r'\\item\b', para))

            paragraphs.append({
                "index": len(paragraphs),
                "section": current_section,
                "subsection": current_subsection,
                "paragraph": cleaned,
                "is_in_environment": in_env
            })

        return paragraphs

    @staticmethod
    def _clean_paragraph_text(text: str) -> str:
        r"""Remove LaTeX markup from paragraph text while preserving content.

        Removes or simplifies:
        - \cite{...}, \ref{...}, \label{...}
        - \textbf{...}, \textit{...}, \emph{...}
        - \item directives
        - Math mode delimiters (but keeps the math)
        - \begin{...} and \end{...} environment markers
        """
        # Remove \begin{...} and \end{...} but keep content inside
        text = re.sub(r'\\(begin|end)\{[^}]*\}', '', text)
        
        # Remove citation, reference, label commands
        text = re.sub(r'\\(cite|ref|label)\{[^}]*\}', '', text)
        
        # Remove text formatting commands (keep inner text)
        text = re.sub(r'\\(textbf|textit|emph|texttt|text|sout|uline)\{([^}]*)\}', r'\2', text)
        
        # Remove \em, \it, \bf styling marks
        text = re.sub(r'\\(em|it|bf)\b\s*', '', text)
        
        # Remove \item markers
        text = re.sub(r'\\item\s+', '', text)
        
        # Simplify inline math ($ ... $)
        text = re.sub(r'\$([^$]+)\$', r'[\1]', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    @staticmethod
    def _extract_title(latex_content: str) -> str:
        """Extract document title."""
        match = re.search(r'\\title\{([^}]+)\}', latex_content)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_sections(latex_content: str) -> List[str]:
        """Extract all section titles."""
        return re.findall(r'\\section\{([^}]+)\}', latex_content)

    @staticmethod
    def _extract_subsections(latex_content: str) -> List[str]:
        """Extract all subsection titles."""
        return re.findall(r'\\subsection\{([^}]+)\}', latex_content)

    @staticmethod
    def _extract_equations(latex_content: str) -> List[str]:
        """Extract all equations."""
        equations = re.findall(r'\$\$(.+?)\$\$', latex_content, re.DOTALL)
        equations += re.findall(r'\$(.+?)\$', latex_content)
        return equations

    @staticmethod
    def _extract_citations(latex_content: str) -> List[str]:
        """Extract all citations."""
        return re.findall(r'\\cite\{([^}]+)\}', latex_content)

    @staticmethod
    def _extract_environments(latex_content: str) -> List[str]:
        """Extract LaTeX environments (theorem, proof, etc.)."""
        return re.findall(r'\\begin\{([a-z*]+)\}', latex_content)


# 2. Define Signatures
class GenerateOutline(dspy.Signature):
    """
    Generate a detailed proposal outline for a given topic, including a title,
    introduction, main sections with bullet points, and a conclusion.
    """
    topic: str = dspy.InputField(desc="The main subject of the proposal")
    outline: str = dspy.OutputField(desc="A structured outline with title, sections, and conclusion")


class GenerateSection(dspy.Signature):
    """
    Write a complete, well-written section of a proposal based on the provided topic,
    outline details, and section title.
    """
    topic: str = dspy.InputField()
    outline_details: str = dspy.InputField(desc="Specific bullet points and information to cover")
    section_title: str = dspy.InputField()
    section_content: str = dspy.OutputField(desc="The fully written content for this section")


class Proofread(dspy.Signature):
    """
    Proofread a blog post and output a more well-written, polished version of the original post.
    Add few references for the main points.
    """
    blog_post: str = dspy.InputField()
    proofread_blog_post: str = dspy.OutputField(desc="Text with added references.")


class EditParagraph(dspy.Signature):
    """Edit a single paragraph according to an instruction.

    This signature allows the LLM to operate on one paragraph at a time.
    """
    paragraph: str = dspy.InputField()
    instruction: str = dspy.InputField()
    edited_paragraph: str = dspy.OutputField()



# 3. Create the Proposal Generator Pipeline as a DSPy Module
class ProposalGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        # Define the modules to be used in the pipeline
        self.generate_outline = dspy.Predict(GenerateOutline)
        self.generate_intro = dspy.Predict(GenerateSection)
        self.generate_section_1 = dspy.Predict(GenerateSection)
        self.generate_section_2 = dspy.Predict(GenerateSection)
        self.generate_conclusion = dspy.Predict(GenerateSection)
        self.proofread = dspy.Predict(Proofread)
        self.edit_paragraph_predict = dspy.Predict(EditParagraph)
        self.paragraph_history = ParagraphHistory()

    def forward(self, topic):
        # Step 1: Generate the outline
        outline_response = self.generate_outline(topic=topic)
        outline_str = outline_response.outline

        # Step 2: Generate each section and track versions
        intro_content = self.generate_intro(
            topic=topic,
            outline_details="Write a captivating introduction that sets the stage and summarizes the proposal's value.",
            section_title="Introduction"
        ).section_content
        self.paragraph_history.add_version("Introduction", intro_content)

        section_1_content = self.generate_section_1(
            topic=topic,
            outline_details="Detail the first main point, based on the generated outline.",
            section_title="Main Point One"
        ).section_content
        self.paragraph_history.add_version("Main Point One", section_1_content)

        section_2_content = self.generate_section_2(
            topic=topic,
            outline_details="Detail the second main point, based on the generated outline.",
            section_title="Main Point Two"
        ).section_content
        self.paragraph_history.add_version("Main Point Two", section_2_content)

        conclusion_content = self.generate_conclusion(
            topic=topic,
            outline_details="Summarize the key takeaways and provide a call to action.",
            section_title="Conclusion"
        ).section_content
        self.paragraph_history.add_version("Conclusion", conclusion_content)

        # Step 3: Combine sections
        title_line = outline_str.splitlines()[0] if outline_str else "Untitled Proposal"
        full_proposal = (
            f"Title: {title_line}\n\n"
            f"{intro_content}\n\n"
            f"{section_1_content}\n\n"
            f"{section_2_content}\n\n"
            f"{conclusion_content}"
        )

        # Step 4: Proofread
        polished_proposal = self.proofread(blog_post=full_proposal).proofread_blog_post
        self.paragraph_history.add_version("Final Proposal", polished_proposal)

        return polished_proposal

    def edit_paragraph_via_llm(self, paragraph_text: str, instruction: str, section_title: str = "", user_hint: str = "") -> str:
        """Use the LLM to edit a single paragraph and record a new version.

        Args:
            paragraph_text: The paragraph to edit
            instruction: The editing instruction for the LLM
            section_title: The section this paragraph belongs to
            user_hint: Optional user-provided context/hint to guide the LLM

        Returns the edited paragraph text.
        """
        # Combine instruction with user hint if provided
        full_instruction = instruction
        if user_hint:
            full_instruction = f"{instruction}\n\nUser hints/context: {user_hint}"
        
        resp = self.edit_paragraph_predict(paragraph=paragraph_text, instruction=full_instruction)
        edited = resp.edited_paragraph
        # record version
        key = section_title or f"Paragraph_{hash(paragraph_text) % 10000}"
        self.paragraph_history.add_version(key, edited)
        return edited

    def _compute_unified_diff(self, original: str, edited: str) -> str:
        """Return a unified diff between original and edited paragraph texts."""
        orig_lines = original.splitlines(keepends=True)
        edited_lines = edited.splitlines(keepends=True)
        diff = difflib.unified_diff(orig_lines, edited_lines, fromfile='original', tofile='edited', lineterm='')
        return '\n'.join(diff)

    def process_json_instructions(self, json_path: str, apply_changes: bool = True, extract_changes: bool = False, global_hint: str = None) -> Dict[str, Any]:
        """Process a JSON file containing paragraph objects and apply instructions.

        The expected JSON is an array of paragraph dicts similar to the output
        of `import_and_edit_latex`. Entries may contain an `instruction` or
        `hint` field. If `apply_changes` is True, the LLM will be used to edit
        paragraphs according to the instruction (or `global_hint` if provided).

        If `extract_changes` is True, returns a dict mapping paragraph indices
        to unified diffs between the original and final text.
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        results = []
        diffs = {}

        for item in data:
            idx = item.get('index')
            orig = item.get('paragraph') or item.get('original') or ''
            # instruction precedence: item.instruction -> item.hint -> global_hint
            instr = item.get('instruction') or item.get('hint') or global_hint

            final_text = item.get('final', orig)

            if apply_changes and instr:
                # apply LLM edit
                try:
                    edited = self.edit_paragraph_via_llm(orig, instr, section_title=item.get('section', ''), user_hint=item.get('hint', '') or global_hint or '')
                    final_text = edited
                except Exception as e:
                    # on error, keep original and record error in item
                    item['error'] = str(e)

            # record final
            item['final'] = final_text
            results.append(item)

            if extract_changes:
                d = self._compute_unified_diff(orig, final_text)
                diffs[str(idx)] = d

        # Save back results next to original JSON
        base, ext = os.path.splitext(json_path)
        out_path = base + '_processed' + ext
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

        # also save diffs if requested
        if extract_changes:
            diff_path = base + '_diffs.json'
            with open(diff_path, 'w', encoding='utf-8') as f:
                json.dump(diffs, f, indent=2)
            return {'processed_json': out_path, 'diffs_json': diff_path}

        return {'processed_json': out_path}

    def extract_changes(self, original_paragraphs: List[Dict[str, Any]], edited_paragraphs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract and summarize changes between original and edited paragraphs.

        Returns a dict with:
        - total_paragraphs: number of paragraphs
        - changed_paragraphs: number that were edited
        - changes: list of dicts with {index, section, subsection, original, edited, change_type}
        """
        changes = []
        changed_count = 0
        
        for orig, edited in zip(original_paragraphs, edited_paragraphs):
            if orig['paragraph'] != edited.get('final', orig['paragraph']):
                changed_count += 1
                changes.append({
                    "index": orig['index'],
                    "section": orig['section'],
                    "subsection": orig['subsection'],
                    "original": orig['paragraph'],
                    "edited": edited.get('final', orig['paragraph']),
                    "change_type": "llm_edit" if edited.get('final') else "manual_edit"
                })
        
        return {
            "total_paragraphs": len(original_paragraphs),
            "changed_paragraphs": changed_count,
            "change_percentage": (changed_count / len(original_paragraphs) * 100) if original_paragraphs else 0,
            "changes": changes
        }

    def import_and_edit_latex(self, filepath: str, auto_instruction: str = None, interactive: bool = True, 
                              auto_hints: str = None, extract_changes_summary: bool = False) -> tuple:
        """Import a .tex file, parse paragraphs, and allow editing each paragraph.

        Args:
            filepath: Path to the .tex file
            auto_instruction: Instruction to apply to all paragraphs in non-interactive mode
            interactive: If True, prompt user for each paragraph
            auto_hints: Optional hints/context to provide to the LLM (same for all paragraphs)
            extract_changes_summary: If True, return a summary of all changes made

        Interactive mode options per paragraph:
          (e)dit via LLM, (h)int - provide context hint, (r)eplace manually, (s)kip, (q)uit

        Returns: 
            tuple of (results, changes_summary) if extract_changes_summary=True
            else just results list
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            latex = f.read()

        paragraphs = LaTeXStructureParser.parse_paragraphs(latex)
        results = []
        original_paragraphs = [p.copy() for p in paragraphs]  # Keep original for comparison

        for p in paragraphs:
            para_text = p['paragraph']
            current_hint = ""  # Track hint for this paragraph
            
            print('\n' + '=' * 60)
            header = p['section'] or '(no section)'
            if p['subsection']:
                header += f' > {p["subsection"]}'
            print(f"Paragraph {p['index']} — Section: {header}\n")
            print(para_text)

            final_text = para_text

            if interactive:
                while True:
                    choice = input("\nChoose: (e)dit via LLM, (h)int, (r)eplace manually, (s)kip, (q)uit: ").strip().lower()
                    if choice == 'e':
                        instr = input('Enter edit instruction (or leave blank for "Improve clarity and grammar"): ').strip()
                        if not instr:
                            instr = 'Improve clarity and grammar while preserving meaning.'
                        final_text = self.edit_paragraph_via_llm(
                            para_text, instr, 
                            section_title=p['section'] or '', 
                            user_hint=current_hint
                        )
                        print('\nEdited paragraph:\n')
                        print(final_text)
                        break
                    elif choice == 'h':
                        hint_input = input('Provide a hint or context for the LLM (e.g., "focus on technical accuracy"): ').strip()
                        if hint_input:
                            current_hint = hint_input
                            print(f'✓ Hint saved: "{hint_input}"')
                        else:
                            print('No hint provided.')
                    elif choice == 'r':
                        print('Enter replacement text (end with a single line containing only ".end")')
                        lines = []
                        while True:
                            line = input()
                            if line.strip() == '.end':
                                break
                            lines.append(line)
                        final_text = '\n'.join(lines)
                        self.paragraph_history.add_version(p['section'] or f'Paragraph_{p["index"]}', final_text)
                        break
                    elif choice == 's':
                        break
                    elif choice == 'q':
                        print('Quitting interactive editor.')
                        results.append({**p, 'final': final_text})
                        if extract_changes_summary:
                            changes = self.extract_changes(original_paragraphs, results)
                            return results, changes
                        return results
                    else:
                        print('Unknown choice, please enter e, h, r, s, or q.')
            else:
                # non-interactive: apply auto_instruction to all paragraphs
                if auto_instruction:
                    final_text = self.edit_paragraph_via_llm(
                        para_text, auto_instruction, 
                        section_title=p['section'] or '', 
                        user_hint=auto_hints or ""
                    )

            results.append({**p, 'final': final_text})

        if extract_changes_summary:
            changes = self.extract_changes(original_paragraphs, results)
            return results, changes
        return results


# 4. Run the Program
if __name__ == "__main__":
    parser = LaTeXStructureParser()

    ap = argparse.ArgumentParser(description='Generate and edit proposals / import LaTeX and edit paragraphs.')
    ap.add_argument('--latex-file', '-l', help='Path to a .tex file to import and edit')
    ap.add_argument('--auto-instruction', '-a', help='If provided with --latex-file and --non-interactive, apply this instruction to all paragraphs')
    ap.add_argument('--auto-hints', '--hints', help='Provide hints/context to guide the LLM (used with --auto-instruction)')
    ap.add_argument('--non-interactive', action='store_true', help='Run auto edits without prompting')
    ap.add_argument('--extract-changes', action='store_true', help='Extract and save a summary of all changes made')
    ap.add_argument('--apply-json', help='Path to a JSON file with paragraph objects to apply instructions from')
    ap.add_argument('--json-hint', help='Global hint/context to apply to JSON-driven edits (overridden by per-item hint/instruction)')
    ap.add_argument('--json-extract-diffs', action='store_true', help='When applying JSON instructions, also extract unified diffs for each paragraph')
    args = ap.parse_args()

    proposal_writer = ProposalGenerator()

    # If user wants to process a JSON of paragraph instructions, handle that first
    if args.apply_json:
        print(f"Processing JSON instructions from '{args.apply_json}'...")
        res = proposal_writer.process_json_instructions(
            args.apply_json,
            apply_changes=True,
            extract_changes=args.json_extract_diffs,
            global_hint=args.json_hint
        )
        print("JSON processing completed. Outputs:")
        for k, v in res.items():
            print(f" - {k}: {v}")
        # exit after processing JSON unless user also provided a LaTeX file
        if not args.latex_file:
            sys.exit(0)

    if args.latex_file:
        interactive = not args.non_interactive
        result = proposal_writer.import_and_edit_latex(
            args.latex_file, 
            auto_instruction=args.auto_instruction, 
            interactive=interactive,
            auto_hints=args.auto_hints,
            extract_changes_summary=args.extract_changes
        )
        
        # Handle return value (might be tuple if extract_changes is True)
        if args.extract_changes:
            results, changes_summary = result
        else:
            results = result
            changes_summary = None
        
        # Save paragraph history and results
        proposal_writer.paragraph_history.save_to_file("proposal_paragraph_history.json")
        out_json = args.latex_file.rstrip('.tex') + '_edited_paragraphs.json'
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nParagraph editing completed. Results saved to '{out_json}' and history to 'proposal_paragraph_history.json'.")
        
        # Save changes summary if requested
        if changes_summary:
            changes_file = args.latex_file.rstrip('.tex') + '_changes_summary.json'
            with open(changes_file, 'w', encoding='utf-8') as f:
                json.dump(changes_summary, f, indent=2)
            print(f"Changes summary saved to '{changes_file}'.")
            print(f"\nSummary: {changes_summary['changed_paragraphs']}/{changes_summary['total_paragraphs']} paragraphs modified ({changes_summary['change_percentage']:.1f}%)")
        
        sys.exit(0)

    # Default behavior: generate a proposal from topic
    sys.exit(0)
    
