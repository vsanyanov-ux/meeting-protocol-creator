import os
from dotenv import load_dotenv
from langfuse import propagate_attributes
import inspect

load_dotenv()

def inspect_source():
    try:
        source = inspect.getsource(propagate_attributes)
        print("--- propagate_attributes source ---")
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

if __name__ == "__main__":
    inspect_source()
