import os
import sys
from loguru import logger

try:
    from langfuse import Langfuse
    print(f"IMPORT SUCCESS: {Langfuse}")
    
    # Имитируем загрузку из .env
    pk = "pk-lf-36201d56-0fa0-4ea5-b3d1-eb7004c0142d"
    sk = "sk-lf-39e748b6-ef45-45e2-8011-08f99dc8a682"
    host = "https://us.cloud.langfuse.com/"
    
    lf = Langfuse(public_key=pk, secret_key=sk, host=host)
    print(f"INSTANCE CREATED: {type(lf)}")
    
    methods = dir(lf)
    print("AVAILABLE METHODS (including trace?):")
    print([m for m in methods if not m.startswith('_')])
    
    if 'trace' in methods:
        print("!!! TRACE METHOD FOUND !!!")
        t = lf.trace(name="test_diagnostic")
        print(f"TRACE CREATED: {t}")
    else:
        print("??? TRACE METHOD MISSING ???")
        
except Exception as e:
    print(f"DIAGNOSTIC FAILED: {e}")
    import traceback
    traceback.print_exc()
