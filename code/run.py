import re
import openai
import dspy
from dspy.teleprompt import BootstrapFewShot

from markitdown import MarkItDown
import os
import dspyanalysis as g
from dotenv import load_dotenv
import  json
import sys
import utils


def generate_llms_txt_for_dspy(gurl,lm):
    # Initialize our analyzer
    analyzer = g.RepositoryAnalyzer()

    # Gather DSPy repository information
    repo_url = gurl
    file_tree, readme_content, package_files = utils.gather_repository_info(repo_url)

    # Generate llms.txt
    result = analyzer(
        repo_url=repo_url,
        file_tree=file_tree,
        readme_content=readme_content,
        package_files=package_files
    )

    return result

# Run the generation
if __name__ == "__main__":
    load_dotenv()
    key= os.getenv("openai_key2")
    openai.api_key = key
    lm = dspy.LM("openai/gpt-4o-mini",api_key=key)
    dspy.settings.configure(lm=lm)
    url="https://github.com/electrum/tpch-dbgen"
    file_tree_txt, readme_content, package_files_content, combined_tags = utils.gather_repository_info(url)
    print(combined_tags)
    exit(1)
    #url="https://github.com/stanfordnlp/dspy"
    try:
        result = generate_llms_txt_for_dspy(url,lm)

    # Save the generated llms.txt
        with open("llms.txt", "w") as f:
            f.write(result.llms_txt_content)

        print("Generated llms.txt file!")
        print("\nPreview:")
        print(result.llms_txt_content[:500] + "...")
    except Exception as e:
        print(f"Error: {e}")
    


    with open("history.log", "a", encoding="utf-8") as f:
        sys.stdout = f
        dspy.inspect_history()
