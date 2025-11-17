import dspy
import requests
from bs4 import BeautifulSoup
import html2text
from typing import List, Dict, Any
import json
from urllib.parse import urljoin, urlparse
import time
import re
from datetime import datetime

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


# 4. Run the Program
if __name__ == "__main__":
    proposal_writer = ProposalGenerator()
    topic = "The Future of Artificial Intelligence in Healthcare"
    generated_proposal = proposal_writer(topic=topic)

    print("Generated Proposal:")
    print("=" * 80)
    print(generated_proposal)
    print("=" * 80)

    # Save paragraph history
    proposal_writer.paragraph_history.save_to_file("proposal_paragraph_history.json")
    print("\nParagraph history saved to 'proposal_paragraph_history.json'")

    # Example: Parse LaTeX structure if LaTeX input is provided
    latex_example = r"""
    \documentclass{article}
    \title{Advanced AI in Healthcare}
    \section{Introduction}
    \subsection{Background}
    Some text here.
    \section{Methods}
    \cite{Smith2020}
    \$\$ E = mc^2 \$\$
    \begin{theorem}
    This is a theorem.
    \end{theorem}
    """
    
    parser = LaTeXStructureParser()
    structure = parser.parse_structure(latex_example)
    print("\nExtracted LaTeX Structure:")
    print(json.dumps(structure, indent=2))

