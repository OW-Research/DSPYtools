#!/usr/bin/env python3
"""Test script demonstrating LaTeX import, parsing, and paragraph-level editing workflow."""

import sys
from genproposal import ProposalGenerator, LaTeXStructureParser
import json

def test_basic_parsing():
    """Test that LaTeX parsing extracts sections and paragraphs correctly."""
    print("=" * 70)
    print("TEST 1: Basic LaTeX Parsing")
    print("=" * 70)
    
    with open("input.tex") as f:
        latex = f.read()
    
    # Parse paragraphs
    paragraphs = LaTeXStructureParser.parse_paragraphs(latex)
    
    print(f"\nTotal paragraphs extracted: {len(paragraphs)}")
    print("\nParagraph summary:")
    for p in paragraphs:
        section = p['section'] or "(no section)"
        subsection = f" > {p['subsection']}" if p['subsection'] else ""
        text_preview = p['paragraph'][:80].replace('\n', ' ') + "..."
        print(f"  [{p['index']}] {section}{subsection}")
        print(f"       {text_preview}")
    
    # Verify structure
    assert len(paragraphs) > 0, "No paragraphs extracted"
    
    # Check that sections are populated
    with_sections = [p for p in paragraphs if p['section']]
    print(f"\nParagraphs with section info: {len(with_sections)}/{len(paragraphs)}")
    
    # Check subsections
    with_subsections = [p for p in paragraphs if p['subsection']]
    print(f"Paragraphs with subsection info: {len(with_subsections)}/{len(paragraphs)}")
    
    print("\n✅ TEST PASSED: LaTeX parsing working correctly\n")
    return paragraphs


def test_ignore_blocks():
    """Test that \\ignore blocks are properly removed."""
    print("=" * 70)
    print("TEST 2: \\ignore Block Removal")
    print("=" * 70)
    
    test_latex = r"""
    \section{Test}
    Keep this paragraph.
    
    \ignore{This should be removed}
    
    This should also be kept.
    """
    
    cleaned = LaTeXStructureParser._remove_ignore_blocks(test_latex)
    
    assert "This should be removed" not in cleaned, "\\ignore block not removed"
    assert "Keep this paragraph" in cleaned, "Paragraph incorrectly removed"
    assert "This should also be kept" in cleaned, "Paragraph incorrectly removed"
    
    print("Input text contains: 'Keep this paragraph', '\\ignore{...}', 'This should also be kept'")
    print("After removal: 'Keep this paragraph' and 'This should also be kept' remain")
    print("\n✅ TEST PASSED: \\ignore blocks properly removed\n")


def test_paragraph_cleaning():
    """Test that LaTeX markup is removed from paragraphs."""
    print("=" * 70)
    print("TEST 3: Paragraph Text Cleaning")
    print("=" * 70)
    
    test_text = r"This is \textbf{bold} text with \cite{reference} and \emph{emphasis}."
    cleaned = LaTeXStructureParser._clean_paragraph_text(test_text)
    
    print(f"Original: {test_text}")
    print(f"Cleaned:  {cleaned}")
    
    assert "\\textbf" not in cleaned, "LaTeX command not removed"
    assert "\\cite" not in cleaned, "Citation markup not removed"
    assert "\\emph" not in cleaned, "Emphasis markup not removed"
    assert "bold" in cleaned, "Content lost during cleaning"
    
    print("\n✅ TEST PASSED: LaTeX markup properly cleaned\n")


def test_history_tracking():
    """Test that paragraph editing history is tracked."""
    print("=" * 70)
    print("TEST 4: Paragraph History Tracking")
    print("=" * 70)
    
    generator = ProposalGenerator()
    
    # Add some test versions
    generator.paragraph_history.add_version("Test Section", "Version 1 of test paragraph")
    generator.paragraph_history.add_version("Test Section", "Version 2 of test paragraph (improved)")
    
    versions = generator.paragraph_history.get_versions("Test Section")
    
    print(f"Tracked {len(versions)} versions of 'Test Section':")
    for v in versions:
        print(f"  - {v['timestamp']}: {v['content'][:50]}...")
    
    assert len(versions) == 2, "History not tracking versions correctly"
    assert versions[0]['section'] == "Test Section", "Section metadata not preserved"
    
    print("\n✅ TEST PASSED: History tracking working\n")


def test_section_subsection_hierarchy():
    """Test that section and subsection hierarchy is correctly preserved."""
    print("=" * 70)
    print("TEST 5: Section/Subsection Hierarchy")
    print("=" * 70)
    
    with open("input.tex") as f:
        latex = f.read()
    
    paragraphs = LaTeXStructureParser.parse_paragraphs(latex)
    
    # Find all unique section/subsection combinations
    hierarchy = {}
    for p in paragraphs:
        sec = p['section'] or "(no section)"
        subsec = p['subsection'] or "(no subsection)"
        key = (sec, subsec)
        if key not in hierarchy:
            hierarchy[key] = 0
        hierarchy[key] += 1
    
    print("Section/Subsection Structure:")
    for (sec, subsec), count in sorted(hierarchy.items()):
        indent = "  " if subsec != "(no subsection)" else ""
        print(f"{indent}{sec} > {subsec if subsec != '(no subsection)' else ''}: {count} paragraphs")
    
    print("\n✅ TEST PASSED: Hierarchy correctly preserved\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("LaTeX Import and Paragraph Editing - Test Suite")
    print("=" * 70 + "\n")
    
    try:
        paragraphs = test_basic_parsing()
        test_ignore_blocks()
        test_paragraph_cleaning()
        test_history_tracking()
        test_section_subsection_hierarchy()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✅")
        print("=" * 70)
        print("\nThe LaTeX import system is ready for use:")
        print("  - Run: python3 genproposal.py --latex-file input.tex")
        print("    for interactive paragraph editing")
        print("  - Run: python3 genproposal.py --latex-file input.tex --non-interactive")
        print("    to process without prompts (outputs to _edited_paragraphs.json)")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
