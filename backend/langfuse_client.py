import os
import time
import uuid
import json
from loguru import logger
from langfuse import Langfuse
from typing import Optional, List, Dict, Any

# Initialize client globally
_langfuse = None

def get_langfuse_client():
    global _langfuse
    if _langfuse is None:
        try:
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
            
            if public_key and secret_key:
                _langfuse = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host
                )
                logger.info(f"Langfuse initialized successfully (Host: {host})")
            else:
                logger.warning("Langfuse credentials missing in .env")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")
    return _langfuse

class PipelineTrace:
    def __init__(self, file_id, filename, provider, metadata=None, session_id=None, trace_name="protocolist"):
        self.trace_id = file_id.replace("-", "")
        self.filename = filename
        self.provider = provider
        self.session_id = session_id
        self.metadata = metadata or {}
        self.trace_name = trace_name
        
        self.client = get_langfuse_client()
        self.trace_obs = None
        self.current_spans = {}
        
    def __enter__(self):
        if self.client:
            try:
                # In SDK 3.x, start_span doesn't take id/session_id directly.
                # We use trace_context for trace_id and update_trace for other fields.
                self.trace_obs = self.client.start_span(
                    name=self.trace_name,
                    trace_context={"trace_id": self.trace_id}
                )
                
                # Set session_id and metadata via update_trace
                self.trace_obs.update_trace(
                    session_id=self.session_id,
                    metadata={
                        **self.metadata,
                        "provider": self.provider,
                        "filename": self.filename
                    }
                )
                logger.info(f"Started Langfuse trace: {self.trace_id} (Session: {self.session_id})")
            except Exception as e:
                logger.error(f"Failed to start trace: {e}")
        return self
        
    def start_span(self, name, as_type="span", metadata=None):
        if not self.client or not self.trace_obs: return None
        try:
            # Using start_observation as standard in v3
            span = self.trace_obs.start_observation(
                name=name,
                as_type=as_type,
                metadata=metadata or {}
            )
            self.current_spans[name] = span
            return span
        except Exception as e:
            logger.error(f"Failed to start {as_type} {name}: {e}")
            return None
            
    def end_span(self, name, metadata=None, level="INFO"):
        if name in self.current_spans:
            try:
                span = self.current_spans[name]
                if metadata:
                    try:
                        span.update(metadata=metadata, level=level)
                    except:
                        pass
                span.end()
                del self.current_spans[name]
            except Exception as e:
                logger.error(f"Failed to end span {name}: {e}")

    def log_error(self, span_name, error_msg):
        if span_name in self.current_spans:
            self.end_span(span_name, metadata={"error": error_msg}, level="ERROR")
        elif self.trace_obs:
            try:
                self.trace_obs.update_trace(status_message=error_msg)
            except:
                pass

    def log_generation(self, input_messages, output_text, model, latency_ms=None, input_tokens=None, output_tokens=None, name="Generation"):
        if not self.trace_obs: return
        try:
            # SDK 3.x uses usage_details (Dict[str, int])
            usage_data = {
                "input": int(input_tokens or 0),
                "output": int(output_tokens or 0),
                "total": int((input_tokens or 0) + (output_tokens or 0))
            }
            
            logger.info(f"Logging generation to Langfuse: {name} (Model: {model}, Tokens: {usage_data['total']})")
            
            # SDK v3 style: start_observation and update for usage
            gen = self.trace_obs.start_observation(
                name=name,
                as_type="generation",
                model=model,
                input=input_messages,
                output=output_text
            )
            # Use usage_details instead of usage
            gen.update(usage_details=usage_data)
            gen.end()
        except Exception as e:
            logger.error(f"Failed to log generation: {e}")

    def log_stt(self, duration_sec, model="whisper"):
        if not self.trace_obs: return
        try:
            gen = self.trace_obs.start_observation(
                name="Speech-to-Text",
                as_type="generation",
                model=model
            )
            # usage_details for STT (usually just input)
            gen.update(usage_details={
                "input": int(duration_sec)
            }, metadata={"unit": "SECONDS"})
            gen.end()
        except Exception as e:
            logger.error(f"Failed to log STT: {e}")

    def score(self, name, value, comment=None):
        if not self.client: return
        try:
            # Check if we should use trace_obs.score or client.create_score
            if self.trace_obs:
                self.trace_obs.score(name=name, value=value, comment=comment)
            else:
                self.client.create_score(trace_id=self.trace_id, name=name, value=value, comment=comment)
        except Exception as e:
            logger.error(f"Failed to add score {name}: {e}")
        
    def finish(self, status="completed"):
        if self.trace_obs:
            try:
                for span_name in list(self.current_spans.keys()):
                    self.end_span(span_name)
                
                try:
                    self.trace_obs.update(status_message=status)
                except:
                    pass
                self.trace_obs.end()
                
                if self.client:
                    self.client.flush()
                logger.info(f"Langfuse Trace Finished: {self.trace_id}")
            except Exception as e:
                logger.error(f"Failed to finish trace: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.finish(status=f"Error: {str(exc_val)}")
        else:
            self.finish(status="completed")

def get_prompt(name, version=None, fallback=None, **kwargs):
    """
    Fetches a prompt with local caching support for closed-loop environments.
    Priority: Local JSON -> Langfuse API -> Hardcoded Fallback
    """
    p_text = None
    prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
    local_path = os.path.join(prompt_dir, f"{name}.json")

    # 1. Try Local Cache (JSON)
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                p_text = data.get("prompt")
                if p_text:
                    logger.debug(f"Loaded prompt '{name}' from local cache")
        except Exception as e:
            logger.warning(f"Failed to read local prompt {name}: {e}")

    # 2. Try Langfuse API (if online and local missing/failed)
    if not p_text:
        client = get_langfuse_client()
        if client:
            try:
                prompt = client.get_prompt(name, version=version)
                p_text = getattr(prompt, "prompt", None)
                if p_text:
                    logger.info(f"Fetched prompt '{name}' from Langfuse")
                    # Optional: Update local cache if we have a successful fetch
                    if not os.path.exists(prompt_dir):
                        os.makedirs(prompt_dir)
                    try:
                        with open(local_path, "w", encoding="utf-8") as f:
                            json.dump({"name": name, "prompt": p_text, "version": version or "latest", "updated_at": time.time()}, f, ensure_ascii=False, indent=2)
                    except: pass
            except Exception as e:
                logger.warning(f"Failed to fetch prompt {name} from Langfuse: {e}")

    # 3. Final Fallback
    final_text = p_text or fallback
    
    # 4. Handle template variables if any remain (Ollama/Yandex style)
    if final_text:
        for k, v in kwargs.items():
            final_text = final_text.replace(f"{{{{{k}}}}}", str(v))
            
    return final_text

def submit_score(trace_id, name, value, comment=None):
    client = get_langfuse_client()
    if client:
        try:
            client.create_score(
                trace_id=trace_id.replace("-", ""),
                name=name,
                value=value,
                comment=comment
            )
            return True
        except Exception as e:
            logger.error(f"Failed to submit global score: {e}")
    return False
