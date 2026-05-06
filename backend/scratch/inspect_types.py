import langfuse.types
import inspect

try:
    print(f"TraceContext fields: {langfuse.types.TraceContext.__annotations__}")
except:
    print("Could not get TraceContext annotations")
