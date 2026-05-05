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
                # Use start_span as root if trace() is missing
                self.trace_obs = self.client.start_span(
                    name=self.trace_name,
                    id=self.trace_id, # Some SDKs allow passing ID here
                    session_id=self.session_id,
                    metadata={
                        **self.metadata,
                        "provider": self.provider,
                        "filename": self.filename
                    }
                )
                logger.info(f"Started Langfuse trace: {self.trace_id} (Session: {self.session_id})")
            except Exception as e:
                # Fallback to start_observation if start_span fails
                try:
                    self.trace_obs = self.client.start_observation(
                        name=self.trace_name,
                        as_type="span",
                        trace_context={"trace_id": self.trace_id},
                        metadata=self.metadata
                    )
                except Exception as e2:
                    logger.error(f"Failed to start trace: {e2}")
        return self
        
    def start_span(self, name, as_type="span", metadata=None):
        if not self.client or not self.trace_obs: return None
        try:
            if as_type == "generation":
                span = self.trace_obs.start_generation(
                    name=name,
                    metadata=metadata or {}
                )
            else:
                span = self.trace_obs.start_span(
                    name=name,
                    metadata=metadata or {}
                )
            self.current_spans[name] = span
            return span
        except Exception as e:
            logger.error(f"Failed to start span {name}: {e}")
            return None
            
    def end_span(self, name, metadata=None, level="INFO"):
        if name in self.current_spans:
            try:
                span = self.current_spans[name]
                # Try update first if metadata is provided
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
                self.trace_obs.update(level="ERROR", status_message=error_msg)
            except:
                pass

    def log_generation(self, input_messages, output_text, model, latency_ms=None, input_tokens=None, output_tokens=None, name="Generation"):
        if not self.trace_obs: return
        try:
            gen = self.trace_obs.start_generation(
                name=name,
                model=model,
                input=input_messages,
                output=output_text
            )
            # Try to update usage if possible
            try:
                gen.update(usage={
                    "promptTokens": input_tokens or 0,
                    "completionTokens": output_tokens or 0,
                    "totalTokens": (input_tokens or 0) + (output_tokens or 0)
                })
            except:
                pass
            gen.end()
        except Exception as e:
            logger.error(f"Failed to log generation: {e}")

    def log_stt(self, duration_sec, model="whisper"):
        if not self.trace_obs: return
        try:
            gen = self.trace_obs.start_generation(
                name="Transcription",
                model=model,
                metadata={"duration_sec": duration_sec}
            )
            try:
                gen.update(usage={
                    "unit": "SECONDS",
                    "input": int(duration_sec)
                })
            except:
                pass
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
