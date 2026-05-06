import os
import json
from dotenv import load_dotenv
from langfuse import Langfuse

# Load environment variables from .env
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

def main():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

    if not public_key or not secret_key:
        print("Error: Langfuse credentials missing in .env")
        return

    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host
    )

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    
    prompts_to_update = [
        "meeting_create_protocol",
        "meeting_verify_protocol"
    ]

    for name in prompts_to_update:
        file_path = os.path.join(prompts_dir, f"{name}.json")
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Skipping.")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                prompt_text = data.get("prompt")
                if not prompt_text:
                    print(f"Error: No 'prompt' field in {file_path}")
                    continue

                print(f"Pushing prompt '{name}' to Langfuse...")
                # create_prompt creates a new version and marks it as active by default if not specified
                # In newer SDKs it might be slightly different but this is the standard way
                langfuse.create_prompt(
                    name=name,
                    prompt=prompt_text,
                    config=data.get("config", {}),
                    type="chat" if "messages" in prompt_text.lower() else "text" # simplistic check
                )
                print(f"Successfully updated '{name}' in Langfuse.")
            except Exception as e:
                print(f"Failed to update '{name}': {e}")

if __name__ == "__main__":
    main()
