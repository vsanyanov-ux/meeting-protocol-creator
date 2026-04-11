from langfuse import Langfuse
import os

pk = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-mock")
sk = os.getenv("LANGFUSE_SECRET_KEY", "sk-mock")
lf = Langfuse(public_key=pk, secret_key=sk)

print(f"Langfuse object type: {type(lf)}")
print("Available methods:")
for m in dir(lf):
    if not m.startswith("_"):
        print(f" - {m}")
