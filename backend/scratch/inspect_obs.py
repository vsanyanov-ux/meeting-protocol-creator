from langfuse import Langfuse
import os
import uuid

pk = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-mock")
sk = os.getenv("LANGFUSE_SECRET_KEY", "sk-mock")
lf = Langfuse(public_key=pk, secret_key=sk)

obs = lf.start_observation(
    name="test_obs",
    as_type="span",
    trace_context={"trace_id": uuid.uuid4().hex}
)

print(f"Observation object type: {type(obs)}")
print("Available methods:")
for m in dir(obs):
    if not m.startswith("_"):
        print(f" - {m}")
