import os
from dotenv import load_dotenv
from langfuse import Langfuse
import inspect

load_dotenv()

def inspect_source():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    lf = Langfuse(public_key=pk, secret_key=sk)
    
    try:
        source = inspect.getsource(lf.start_observation)
        print("--- lf.start_observation source ---")
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

if __name__ == "__main__":
    inspect_source()
