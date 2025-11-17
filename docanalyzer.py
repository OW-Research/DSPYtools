from IPython.display import display, Markdown, HTML
import re
import dspy
import requests
from bs4 import BeautifulSoup
import html2text
from typing import List, Dict, Any
import json
from urllib.parse import urljoin, urlparse
import time


# --- Helper: Optional SVG Cleaner ---
def clean_svg(svg_text: str) -> str:
	"""
	Clean model-generated SVG text to ensure proper HTML display.
	Removes surrounding quotes, code fences, and prefixes like '''svg ... '''.
	Only modifies text if it matches known patterns.
	"""
	if not svg_text:
		return svg_text

	cleaned = svg_text.strip()

	# Remove code fences (```svg ... ``` or ``` ... ```)
	if cleaned.startswith("```"):
		cleaned = re.sub(r"^```(?:svg)?\s*(.*?)```$", r"\1", cleaned, flags=re.DOTALL).strip()

	# Remove triple quotes wrapping SVG
	if cleaned.startswith("'''svg") or cleaned.startswith("'''<svg"):
		cleaned = re.sub(r"^'''(?:svg)?(.*?)'''$", r"\1", cleaned, flags=re.DOTALL).strip()

	# Remove Markdown-style <svg> tags surrounded by extra quotes
	if cleaned.startswith('"') or cleaned.startswith("'"):
		cleaned = cleaned.strip('"\'').strip()

	return cleaned


# --- dspy Signatures and Module ---
class Outline(dspy.Signature):
	"""Outline a thorough overview of a topic."""
	topic: str = dspy.InputField()
	title: str = dspy.OutputField()
	sections: list[str] = dspy.OutputField()
	section_subheadings: dict[str, list[str]] = dspy.OutputField(
		desc="mapping from section headings to subheadings"
	)


class DraftSection(dspy.Signature):
	"""Draft a top-level section of an article."""
	topic: str = dspy.InputField()
	section_heading: str = dspy.InputField()
	section_subheadings: list[str] = dspy.InputField()
	content: str = dspy.OutputField(desc="markdown-formatted section")
	image: str = dspy.OutputField(desc="generate an image in svg that helps describe the section")


class DraftArticle(dspy.Module):
	def __init__(self):
		self.build_outline = dspy.ChainOfThought(Outline)
		self.draft_section = dspy.ChainOfThought(DraftSection)

	def forward(self, topic):
		outline = self.build_outline(topic=topic)
		sections = []
		for heading, subheadings in outline.section_subheadings.items():
			section_heading = f"## {heading}"
			subheading_list = [f"### {s}" for s in subheadings]
			section = self.draft_section(
				topic=outline.title,
				section_heading=section_heading,
				section_subheadings=subheading_list,
			)
			# Apply cleaner to image
			cleaned_image = clean_svg(section.image)
			sections.append((section.content, cleaned_image))
		return dspy.Prediction(title=outline.title, sections=sections)


# --- Run the Model ---
if __name__ == "__main__":
	draft_article = DraftArticle()
	topic = "The Future of Artificial Intelligence in Healthcare"
	article = draft_article(topic=topic)
	# Display if running in notebook
	try:
		display(Markdown(f"# {article.title}"))
		for i, (content, svg) in enumerate(article.sections, 1):
			display(Markdown(content))
			if svg:
				display(HTML(svg))
	except Exception:
		# Fallback to printing
		print("Title:", article.title)
		for i, (content, svg) in enumerate(article.sections, 1):
			print(f"\n--- Section {i} ---\n")
			print(content)
			if svg:
				print("[SVG content omitted; use a notebook to render]")




