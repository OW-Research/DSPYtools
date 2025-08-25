from dotenv import load_dotenv
import docanalyzer as d
import os
import dspy
import openai   

def interactive_learning_session(agent):
    """Interactive session for learning libraries with user input."""

    print("🎯 Welcome to the Interactive Library Learning System!")
    print("This system will help you learn any Python library from its documentation.\n")

    learned_libraries = {}

    while True:
        print("\n" + "="*60)
        print("🚀 LIBRARY LEARNING SESSION")
        print("="*60)

        # Get library name from user
        library_name = input("\n📚 Enter the library name you want to learn (or 'quit' to exit): ").strip()

        if library_name.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Thanks for using the Interactive Library Learning System!")
            break

        if not library_name:
            print("❌ Please enter a valid library name.")
            continue

        # Get documentation URLs
        print(f"\n🔗 Enter documentation URLs for {library_name} (one per line, empty line to finish):")
        urls = []
        while True:
            url = input("  URL: ").strip()
            if not url:
                break
            if not url.startswith(('http://', 'https://')):
                print("    ⚠️  Please enter a valid URL starting with http:// or https://")
                continue
            urls.append(url)

        if not urls:
            print("❌ No valid URLs provided. Skipping this library.")
            continue

        # Get custom use cases from user
        print(f"\n🎯 Define use cases for {library_name} (optional, press Enter for defaults):")
        print("   Default use cases will be: Basic setup, Common operations, Advanced usage")

        user_wants_custom = input("   Do you want to define custom use cases? (y/n): ").strip().lower()

        use_cases = None
        if user_wants_custom in ['y', 'yes']:
            print("   Enter your use cases (one per line, empty line to finish):")
            use_cases = []
            while True:
                use_case = input("     Use case: ").strip()
                if not use_case:
                    break
                use_cases.append(use_case)

            if not use_cases:
                print("   No custom use cases provided, using defaults.")
                use_cases = None

        # Learn the library
        print(f"\n🚀 Starting learning process for {library_name}...")
        result = d.learn_any_library(agent,library_name, urls, use_cases)

        if result:
            learned_libraries[library_name] = result
            print(f"\n✅ Successfully learned {library_name}!")

            # Show summary
            print(f"\n📊 Learning Summary for {library_name}:")
            print(f"   • Core concepts: {len(result['library_info']['core_concepts'])} identified")
            print(f"   • Common patterns: {len(result['library_info']['patterns'])} found")
            print(f"   • Examples generated: {len(result['examples'])}")

            # Ask if user wants to see examples
            show_examples = input(f"\n👀 Do you want to see the generated examples for {library_name}? (y/n): ").strip().lower()

            if show_examples in ['y', 'yes']:
                for i, example in enumerate(result['examples'], 1):
                    print(f"\n{'─'*50}")
                    print(f"📝 Example {i}: {example['use_case']}")
                    print(f"{'─'*50}")

                    print("\n💻 Generated Code:")
                    print("```python")
                    print(example['code'])
                    print("```")

                    print(f"\n📦 Required Imports:")
                    for imp in example['imports']:
                        print(f"  • {imp}")

                    print(f"\n📝 Explanation:")
                    print(example['explanation'])

                    print(f"\n✅ Best Practices:")
                    for practice in example['best_practices']:
                        print(f"  • {practice}")

                    # Ask if user wants to see the next example
                    if i < len(result['examples']):
                        continue_viewing = input(f"\nContinue to next example? (y/n): ").strip().lower()
                        if continue_viewing not in ['y', 'yes']:
                            break

            # Offer to save results
            save_results = input(f"\n💾 Save learning results for {library_name} to file? (y/n): ").strip().lower()

            if save_results in ['y', 'yes']:
                filename = input(f"   Enter filename (default: {library_name.lower()}_learning.json): ").strip()
                if not filename:
                    filename = f"{library_name.lower()}_learning.json"

                try:
                    import json
                    with open(filename, 'w') as f:
                        json.dump(result, f, indent=2, default=str)
                    print(f"   ✅ Results saved to {filename}")
                except Exception as e:
                    print(f"   ❌ Error saving file: {e}")

        else:
            print(f"❌ Failed to learn {library_name}")

        # Ask if user wants to learn another library
        print(f"\n📚 Libraries learned so far: {list(learned_libraries.keys())}")
        continue_learning = input("\n🔄 Do you want to learn another library? (y/n): ").strip().lower()

        if continue_learning not in ['y', 'yes']:
            break

    # Final summary
    if learned_libraries:
        print(f"\n🎉 Session Summary:")
        print(f"Successfully learned {len(learned_libraries)} libraries:")
        for lib_name, info in learned_libraries.items():
            print(f"  • {lib_name}: {len(info['examples'])} examples generated")

    return learned_libraries


def run_example(agent):
    # Example 1: Learn FastAPI from official documentation
    fastapi_urls = [
        "https://fastapi.tiangolo.com/",
        "https://fastapi.tiangolo.com/tutorial/first-steps/",
        "https://fastapi.tiangolo.com/tutorial/path-params/",
        "https://fastapi.tiangolo.com/tutorial/query-params/"
    ]

    print("🚀 Learning FastAPI from official documentation...")
    fastapi_info = d.learn_library_from_urls(agent,"FastAPI", fastapi_urls)
    print("🎯 Generating FastAPI Examples:")
    fastapi_examples = d.generate_examples_for_library(agent,fastapi_info, "FastAPI")
    library_name = "FastAPI"
    use_cases = [ex['use_case'] for ex in fastapi_examples]
    result = d.learn_any_library(agent,library_name, fastapi_urls, use_cases)
    if result:
            
            print(f"\n✅ Successfully learned {library_name}!")

            # Show summary
            print(f"\n📊 Learning Summary for {library_name}:")
            print(f"   • Core concepts: {len(result['library_info']['core_concepts'])} identified")
            print(f"   • Common patterns: {len(result['library_info']['patterns'])} found")
            print(f"   • Examples generated: {len(result['examples'])}")
    # # Example 2: Learn a different library (you can replace with any library)
    # streamlit_urls = [
    #     "https://docs.streamlit.io/",
    #     "https://docs.streamlit.io/get-started",
    #     "https://docs.streamlit.io/develop/api-reference"
    # ]

    # print("\n\n📊 Learning Streamlit from official documentation...")
    # streamlit_info = learn_library_from_urls("Streamlit", streamlit_urls)




# print("\n\n🎯 Generating Streamlit Examples:")
# streamlit_examples = generate_examples_for_library(streamlit_info, "Streamlit")


# Example: Run interactive learning session
if __name__ == "__main__":
    load_dotenv()
    key= os.getenv("openai_key2")
    openai.api_key = key
    lm = dspy.LM("openai/gpt-4o-mini",api_key=key)
    dspy.settings.configure(lm=lm)
    # Run interactive session
    #learned_libraries = interactive_learning_session()
    # Initialize the learning agent
    agent = d.DocumentationLearningAgent()
    run_example(agent)
    
# Generate examples for both libraries
