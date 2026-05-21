#!/usr/bin/env python3
"""
Enhanced OpenRouter Cost & Routing Updater
Fetches live model IDs, prices, and provider routing options.
# TUI Menu (default)
python update_openrouter_costs.py

# CLI Options
python update_openrouter_costs.py --find      # Find models
python update_openrouter_costs.py --update    # Update prices for configured models
python update_openrouter_costs.py --sync      # Sync all with live prices
python update_openrouter_costs.py --list      # List configured models
"""
import yaml
import requests
import re
from pathlib import Path
from typing import Optional

YAML_PATH = Path(__file__).parent.parent / "config" / "cost_mapping.yaml"

def fetch_all_models() -> dict:
    """Fetch ALL models from OpenRouter with full metadata."""
    print("Fetching model metadata from OpenRouter...")
    response = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
    if response.status_code != 200:
        print(f"Failed: {response.status_code}")
        return {}
    
    models = response.json().get("data", [])
    
    # Index by various IDs for flexible lookup
    by_id = {}
    by_name = {}
    
    for m in models:
        model_id = m.get("id", "")
        by_id[model_id] = m
        
        # Also index by human-readable name (lowercase)
        name = m.get("name", "").lower()
        if name:
            by_name[name] = m
    
    return {"by_id": by_id, "by_name": by_name}

def fetch_live_prices() -> dict:
    """Fetch pricing data."""
    models_data = fetch_all_models()
    by_id = models_data.get("by_id", {})
    
    live_prices = {}
    for model_id, model in by_id.items():
        pricing = model.get("pricing", {})
        try:
            live_prices[model_id] = {
                "input": float(pricing.get("prompt", 0)) * 1_000_000,
                "output": float(pricing.get("completion", 0)) * 1_000_000,
            }
        except (ValueError, TypeError):
            continue
    
    return live_prices

def find_model_by_provider(provider_slug: str, model_name_hint: str) -> Optional[dict]:
    """Find the exact model ID for a specific provider (including routed models)."""
    models_data = fetch_all_models()
    by_id = models_data.get("by_id", {})
    
    # Search for models matching provider and name hint
    for model_id, model in by_id.items():
        
        # Check if provider is in the model ID
        if provider_slug.lower() in model_id.lower():
            if model_name_hint.lower() in model_id.lower():
                return model
        
        # ALSO check top_provider (handles routed models like deepinfra/...)
        top_provider = model.get("top_provider", {})
        provider_name = top_provider.get("provider", "").lower()
        
        if provider_slug.lower() in provider_name:
            if model_name_hint.lower() in model_id.lower():
                return model
    
    return None

def update_yaml_with_routing(updates: dict, routing_config: dict):
    """Update YAML with both costs and routing config."""
    if not YAML_PATH.exists():
        print(f"Error: {YAML_PATH}")
        return
    
    content = YAML_PATH.read_text(encoding='utf-8')
    
    for model_id, data in updates.items():
        # Find model block and update costs
        pattern_input = r'("' + re.escape(model_id) + r'":.*?input_cost_per_mtok:\s*)[\d.]+'
        pattern_output = r'("' + re.escape(model_id) + r'":.*?output_cost_per_mtok:\s*)[\d.]+'
        
        content = re.sub(pattern_input, rf'\g<1>{data["input"]:.4f}', content, flags=re.DOTALL)
        content = re.sub(pattern_output, rf'\g<1>{data["output"]:.4f}', content, flags=re.DOTALL)
        
        # Add routing config if specified
        if model_id in routing_config:
            route = routing_config[model_id]
            # Insert routing block after the model entry
            routing_block = f"\n  # Routing: {route.get('description', 'Custom')}\n  routing:\n"
            
            if route.get('provider'):
                routing_block += f"    provider: {route['provider']}\n"
            if route.get('quantizations'):
                routing_block += f"    quantizations: {route['quantizations']}\n"
            if route.get('allow_fallbacks') is not None:
                routing_block += f"    allow_fallbacks: {route['allow_fallbacks']}\n"
            
            # Find the end of this model block and insert before it
            # This is a simplified approach - you may need to adjust based on YAML structure
    
    YAML_PATH.write_text(content, encoding='utf-8')
    print(f"[+] Updated {len(updates)} models")

def interactive_find_model():
    """Interactive mode to find exact model strings."""
    print("\n=== Interactive Model Finder ===")
    print("Enter a provider (e.g., deepinfra, meta-llama):")
    provider = input("> ").strip().lower()
    
    print("Enter a model name hint (e.g., qwen3-235b):")
    hint = input("> ").strip().lower()
    
    models_data = fetch_all_models()
    by_id = models_data.get("by_id", {})
    
    print(f"\n=== Matching Models ===")
    matches = []
    for model_id, model in by_id.items():
        if provider in model_id.lower() and hint in model_id.lower():
            matches.append((model_id, model))
    
    if not matches:
        print("No matches found.")
        return
    
    for i, (model_id, model) in enumerate(matches):
        pricing = model.get("pricing", {})
        input_c = float(pricing.get("prompt", 0)) * 1_000_000
        output_c = float(pricing.get("completion", 0)) * 1_000_000
        
        print(f"\n[{i+1}] {model_id}")
        print(f"    Name: {model.get('name')}")
        print(f"    Input: ${input_c:.4f} / Output: ${output_c:.4f} per 1M tokens")
        
        # Show available providers
        top_provider = model.get('top_provider', {})
        print(f"    Top Provider: {top_provider.get('provider', 'N/A')}")
    
    print("\nCopy the model ID you want to use.")

def run_tui_menu():
    """Interactive TUI menu."""
    while True:
        print("\n" + "=" * 50)
        print("  OpenRouter Cost Updater - Main Menu")
        print("=" * 50)
        print("  1. Find model by provider")
        print("  2. Update prices (fetch live data)")
        print("  3. Sync all YAML models with live prices")
        print("  4. List configured models")
        print("  5. Exit")
        print("-" * 50)
        
        choice = input("Select option [1-5]: ").strip()
        
        if choice == "1":
            interactive_find_model()
        elif choice == "2":
            print("\n=== Update Prices ===")
            update_all_prices()
        elif choice == "3":
            print("\n=== Sync All Models ===")
            sync_all_models()
        elif choice == "4":
            print("\n=== Configured Models ===")
            list_configured_models()
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Try 1-5.")
        
        input("\nPress Enter to continue...")


def update_all_prices():
    """Update prices for models already in the YAML."""
    if not YAML_PATH.exists():
        print(f"Error: {YAML_PATH} not found")
        return
    
    # Parse YAML to get current model IDs
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    current_models = [k for k in config.keys() if k not in ('default',)]
    if not current_models:
        print("No models found in config.")
        return
    
    print(f"Found {len(current_models)} configured models")
    print("Fetching live prices...")
    
    live_prices = fetch_live_prices()
    updates = {}
    
    for model_id in current_models:
        if model_id in live_prices:
            updates[model_id] = live_prices[model_id]
            print(f"  ✓ {model_id}")
        else:
            print(f"  ✗ {model_id} (not found in OpenRouter)")
    
    if updates:
        update_yaml_with_routing(updates, {})
    else:
        print("No updates needed.")


def sync_all_models():
    """Sync all models from YAML with live OpenRouter data."""
    if not YAML_PATH.exists():
        print(f"Error: {YAML_PATH} not found")
        return
    
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    current_models = [k for k in config.keys() if k not in ('default',)]
    
    print(f"Syncing {len(current_models)} models with live data...")
    live_prices = fetch_live_prices()
    
    updates = {}
    for model_id in current_models:
        if model_id in live_prices:
            updates[model_id] = live_prices[model_id]
    
    if updates:
        update_yaml_with_routing(updates, {})
        print(f"[+] Synced {len(updates)} models")
    else:
        print("No matching models found in OpenRouter.")


def extract_provider(model_id: str) -> str:
    """Extract provider from model ID (e.g., 'qwen/qwen3-...' -> 'qwen')."""
    if '/' in model_id:
        return model_id.split('/')[0]
    elif ':' in model_id:
        return 'ollama'  # Local model
    else:
        return 'unknown'


def list_configured_models():
    """List all models currently in the YAML with their prices and providers."""
    if not YAML_PATH.exists():
        print(f"Error: {YAML_PATH} not found")
        return
    
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"\n{'Provider':<12} {'Model ID':<42} {'Input':<10} {'Output':<10}")
    print("-" * 80)
    
    for model_id, data in config.items():
        if model_id == 'default':
            continue
        provider = extract_provider(model_id)
        input_cost = data.get('input_cost_per_mtok', 0)
        output_cost = data.get('output_cost_per_mtok', 0)
        
        # Warn about non-OpenRouter models
        marker = ""
        if provider in ('ollama', 'cerebras'):
            marker = " [LOCAL]"
        elif provider not in ('qwen', 'meta-llama', 'deepinfra', 'openrouter'):
            marker = " [CHECK]"
        
        print(f"{provider:<12} {model_id:<42} ${input_cost:<9.4f} ${output_cost:<9.4f}{marker}")
    
    print("\n⚠️  Models marked [LOCAL] cannot be updated from OpenRouter")
    print("⚠️  Models marked [CHECK] may need verification")

def main():
    """Main entry point with CLI and TUI support."""
    import sys
    
    if len(sys.argv) == 1:
        # No args - run TUI
        run_tui_menu()
        return
    
    # CLI mode
    parser = argparse.ArgumentParser(
        description="OpenRouter Cost & Routing Updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_openrouter_costs.py          # Show TUI menu
  python update_openrouter_costs.py --find    # Find models interactively
  python update_openrouter_costs.py --update  # Update prices for configured models
  python update_openrouter_costs.py --sync    # Sync all models with live data
  python update_openrouter_costs.py --list    # List configured models
        """
    )
    parser.add_argument('--find', action='store_true', help='Find model by provider')
    parser.add_argument('--update', action='store_true', help='Update prices for configured models')
    parser.add_argument('--sync', action='store_true', help='Sync all models with live prices')
    parser.add_argument('--list', action='store_true', help='List configured models')
    
    args = parser.parse_args()
    
    if args.find:
        interactive_find_model()
    elif args.update:
        update_all_prices()
    elif args.sync:
        sync_all_models()
    elif args.list:
        list_configured_models()
    else:
        parser.print_help()


if __name__ == "__main__":
    import argparse
    main()