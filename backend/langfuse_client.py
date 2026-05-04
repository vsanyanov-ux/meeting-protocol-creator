import os
import time
from loguru import logger
from langfuse import Langfuse

# Initialize client globally
_langfuse = None

def get_langfuse_client():
    global _langfuse
    if _langfuse is None:
        try:
            _langfuse = Langfuse()
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")
    return _langfuse

class PipelineTrace:
    def __init__(self, file_id, filename, provider, metadata=None, session_id=None):
        self.trace_id = file_id.replace("-", "")
        self.filename = filename
        self.session_id = session_id
        self.metadata = metadata or {}
        
        self.client = get_langfuse_client()
        self.trace = None
        self.current_spans = {}
        
    def __enter__(self):
        if self.client:
            try:
                self.trace = self.client.trace(
                    id=self.trace_id,
                    name=f"protocol_{self.filename}",
                    session_id=self.session_id,
                    metadata=self.metadata
                )
            except Exception as e:
                logger.error(f"Failed to start trace: {e}")
        return self
        
    def start_span(self, name, as_type="span", metadata=None):
        if not self.trace: return None
        try:
            if as_type == "generation":
                span = self.trace.generation(name=name, metadata=metadata or {})
            else:
                span = self.trace.span(name=name, metadata=metadata or {})
            self.current_spans[name] = span
            return span
        except Exception as e:
            logger.error(f"Failed to start span {name}: {e}")
            return None
            
    def end_span(self, name, metadata=None):
        if name in self.current_spans:
            try:
                if metadata:
                    self.current_spans[name].update(metadata=metadata)
                self.current_spans[name].end()
                del self.current_spans[name]
            except Exception as e:
                logger.error(f"Failed to end span {name}: {e}")
            
    def log_generation(self, *args, **kwargs): 
        pass
        
    def score(self, *args, **kwargs): 
        pass
        
    def finish(self, status="completed"):
        if self.trace:
            try:
                self.trace.update(level="INFO" if status == "completed" else "ERROR", status_message=status)
                if self.client:
                    self.client.flush()
                logger.info(f"Langfuse Trace Finished: {self.trace_id}")
            except Exception as e:
                logger.error(f"Failed to finish trace: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and self.trace:
            try:
                self.trace.update(level="ERROR", status_message=str(exc_val))
                if self.client:
                    self.client.flush()
            except Exception:
                pass

def get_prompt(name, version=None, fallback=None, **kwargs):
    client = get_langfuse_client()
    if client:
        try:
            prompt = client.get_prompt(name, version=version)
            return getattr(prompt, "prompt", fallback)
        except Exception as e:
            logger.warning(f"Failed to fetch prompt {name} from Langfuse: {e}")
    return fallback

def submit_score(*args, **kwargs):
    pass
