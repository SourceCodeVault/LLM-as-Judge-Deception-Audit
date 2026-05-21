from pathlib import Path

input_file = "tainted_cases.txt"  # Change to your actual filename
output_file = "tainted_cases_cleaned.txt"

cleaned_signatures = set()

if Path(input_file).exists():
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().replace("\\", "/")
            if "insider-trading-main/" in line:
                # Extract everything starting from insider-trading-main/
                sub_path = line.split("insider-trading-main/")[-1]
                cleaned_signatures.add(f"insider-trading-main/{sub_path}")

    # Save the sorted, unique entries
    with open(output_file, "w", encoding="utf-8") as f:
        for signature in sorted(cleaned_signatures):
            f.write(signature + "\n")
            
    print(f"Done! Cleaned file saved to {output_file}")
else:
    print(f"Error: {input_file} not found.")