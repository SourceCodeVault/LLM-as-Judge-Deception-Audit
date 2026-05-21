# // version: 2.9 (Fixed OpenRouter Provider Routing via extra_body)
# // path: shared/api_clients/openrouter_client.py
import os
import json
import re
import time
import requests
from openai import OpenAI, APIError
from shared.ui_utils import print_warning, print_failure, print_info
from shared.string_utils import extract_json_from_string

def call_openrouter_llm(messages: list[dict], model_id: str, params: dict, cost_mapping: dict) -> tuple[dict | str | None, dict]:
    """Handles API calls to the OpenRouter service, returning the full message object."""
    
    safe_name = params.get('display_name', model_id) 
    # print_info(f"Routing request to '{safe_name}'...", level=3)
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing from your .env file.")
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=900.0,
    )

    # Standard OpenAI params
    standard_params = ['temperature', 'max_tokens', 'stop', 'seed']
    # Extra params supported by OpenRouter/Qwen (passed via extra_body)
    extra_params_keys = ['top_k', 'top_p', 'repetition_penalty', 'min_p']

    # --- DYNAMIC STRICT ROUTING ---
    # Retrieve the specific config for this model from YAML
    model_config = cost_mapping.get(model_id, cost_mapping.get('default', {}))
    routing_config = model_config.get('routing', {})

    provider_preferences = {
        "quantizations": routing_config.get("quantizations", ["fp8", "bf16", "fp16", "fp32", "unknown"]),
        "allow_fallbacks": routing_config.get("allow_fallbacks", True)
    }

    # OpenRouter API uses the "order" array to strictly enforce a specific provider
    yaml_provider = routing_config.get("provider")
    if yaml_provider:
        # Strip out custom flags like /turbo if you accidentally added them
        clean_provider = yaml_provider.split('/')[0].strip() 
        provider_preferences["order"] = [clean_provider]

    # print_info(f"Applying Routing Rules: {provider_preferences}", level=4)
    
    # 1. Build Base Request
    request_params = {
        "model": model_id, 
        "messages": messages,
        # "provider": ...  <-- REMOVED: This causes the crash in OpenAI SDK
    }
    
    for param in standard_params:
        if param in params:
            request_params[param] = params[param]

    # 2. Build extra_body (The Container for OpenRouter Specials)
    extra_body = {}
    
    # Inject Provider Preferences Here
    extra_body['provider'] = provider_preferences  

    # Add other extra params (top_k, etc)
    for param in extra_params_keys:
        if param in params:
            extra_body[param] = params[param]

    # DeepSeek Reasoning Logic
    if "deepseek" in model_id.lower() and "reasoning" not in extra_body:
        extra_body["reasoning"] = {"enabled": True}
    
    # Attach extra_body to request
    if extra_body:
        request_params['extra_body'] = extra_body

    # JSON Mode Handling
    is_gpt_oss_model = 'gpt-oss' in model_id.lower()
    is_json_requested = params.get('is_json', False)

    if is_json_requested and not is_gpt_oss_model:
        request_params["response_format"] = {"type": "json_object"}
    
    try:
        start_time = time.monotonic()
                
        # Use with_raw_response to intercept HTTP-level data
        raw_response = client.chat.completions.with_raw_response.create(**request_params)

        completion = raw_response.parse()
        wire_headers = dict(raw_response.headers) 
        
        # Capture the response text first
        raw_text = raw_response.http_response.text

        try:
            # Try to parse as JSON for the ledger/metrics
            wire_raw_body = json.loads(raw_text)
        except json.JSONDecodeError:
            # If it's HTML (504/502 error), log it as a raw string so you can read it!
            wire_raw_body = {
                "error": "Non-JSON response received from server",
                "http_status": raw_response.http_response.status_code,
                "raw_body": raw_text[:5000] # Capture the first 5k chars of the HTML error
            }

        # Use the status code to help debug the 10-minute hangs
        status_code = raw_response.http_response.status_code
        if status_code != 200:
            print_warning(f"OpenRouter returned Status {status_code}. Content: {raw_text[:200]}", level=2)
            
        # ASk the OpenRouter /generation API for the ledger receipt
        generation_id = wire_headers.get("x-generation-id")
        openrouter_generation_data = {}
        if generation_id:
            try:
                gen_url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
                time.sleep(5) # allow OpenRouter ledger to update
                gen_resp = requests.get(gen_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=5.0)
                if gen_resp.status_code == 200:
                    openrouter_generation_data = gen_resp.json().get("data", {})
            except Exception as e:
                openrouter_generation_data = {"error": f"Failed to fetch ledger: {e}"}

        duration_s = time.monotonic() - start_time
        message_object = completion.choices[0].message

        if not message_object:
            print_warning(f"API call returned empty message.", level=3)
            return None, {"error": "empty_response", "model": safe_name}

        # --- METRICS ---
        input_tokens = completion.usage.prompt_tokens
        output_tokens = completion.usage.completion_tokens
        tps = (output_tokens / duration_s) if duration_s > 0 else 0
        
        model_costs = cost_mapping.get(model_id, cost_mapping.get('default', {}))
        input_cost = (input_tokens / 1_000_000) * model_costs.get('input_cost_per_mtok', 0)
        output_cost = (output_tokens / 1_000_000) * model_costs.get('output_cost_per_mtok', 0)
        
        metrics = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_second": round(tps, 2),
            "actual_cost_usd": round(input_cost + output_cost, 6),
            "wire_payload": request_params,   
            "wire_headers": wire_headers,      
            "wire_raw_body": wire_raw_body,                    # NEW
            "openrouter_generation": openrouter_generation_data # NEW
        }

        return message_object, metrics

    except APIError as e:
        print_failure(f"Routing payload call failed: {e.message}", level=1)
        raise e
    except Exception as e:
        print_failure(f"Unexpected error: {e}", level=1)
        raise e