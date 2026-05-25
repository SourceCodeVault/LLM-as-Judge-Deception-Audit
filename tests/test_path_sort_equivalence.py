import tempfile
from pathlib import Path

def verify_sorting():
    print("🔍 Starting Deterministic Sort Verification...\n")
    
    # Create a temporary mock project root
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        
        # Define some dummy files to simulate the Apollo dataset structure
        file_paths = [
            "data/raw/ApolloResearch/results/response_184.json",
            "data/raw/ApolloResearch/results/response_002.json",
            "data/raw/ApolloResearch/results/response_056.json",
            "data/raw/ApolloResearch/deception/response_010.json",
            "data/raw/ApolloResearch/misalignment/response_099.json"
        ]
        
        # Create the physical mock files on disk
        for fp in file_paths:
            full_path = project_root / fp
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.touch()
            
        print(f"📁 Created mock project root at: {project_root}")
        print("-" * 60)

        # ---------------------------------------------------------
        # SCENARIO A: The Old Way (Absolute Paths via .resolve())
        # ---------------------------------------------------------
        absolute_list = [(str(f.resolve()), f.name) for f in project_root.rglob("*.json")]
        # Sort exactly as select_pilot.py does: .sort(key=lambda x: x[0])
        absolute_list.sort(key=lambda x: x[0])
        
        # Extract just the filenames to see the final order
        order_absolute = [item[1] for item in absolute_list]

        # ---------------------------------------------------------
        # SCENARIO B: The New Way (Relative Paths via .relative_to())
        # ---------------------------------------------------------
        relative_list = [(str(f.relative_to(project_root)), f.name) for f in project_root.rglob("*.json")]
        # Sort exactly as select_pilot.py does
        relative_list.sort(key=lambda x: x[0])
        
        # Extract just the filenames to see the final order
        order_relative = [item[1] for item in relative_list]

        # ---------------------------------------------------------
        # RESULTS
        # ---------------------------------------------------------
        print("\n1️⃣ Order using Absolute Paths (.resolve()):")
        for name in order_absolute:
            print(f"   - {name}")
            
        print("\n2️⃣ Order using Relative Paths (.relative_to()):")
        for name in order_relative:
            print(f"   - {name}")

        print("\n" + "=" * 60)
        if order_absolute == order_relative:
            print("✅ SUCCESS: The sorting order is MATHEMATICALLY IDENTICAL.")
            print("   Your random sampling will draw the exact same files.")
        else:
            print("❌ FAILED: The orders are different.")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    verify_sorting()