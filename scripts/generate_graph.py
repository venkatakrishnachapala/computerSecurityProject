from pathlib import Path
import sys

# Add project root to sys.path so modules like Data, dbfuzz can be imported
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from config_types import AppConfig, TRAVERSAL, BREAKAGE, SCANNER
from Data import load_data, print_reflection_summary, graph_reflection_summary, csv_reflection_summary

# Find the latest pickle file
output_dir = project_root / "output"
pickle_files = sorted(output_dir.glob("xss_tokens.pickle*"), key=lambda f: f.stat().st_mtime, reverse=True)

if not pickle_files:
    print("❌ No xss_tokens.pickle files found in output directory.")
    sys.exit(1)

# Use the most recent .pickle file
pickle_path = pickle_files[0]
print(f"✅ Using pickle file: {pickle_path.name}")

# Load the scan results
xss_found, tokens_found, scans, context, ids, app_config = load_data(pickle_path)

# Show stats
print(f"\n🧪 Found {len(xss_found)} XSS reflections")
print(f"🔑 Found {len(tokens_found)} token reflections")

if not xss_found and not tokens_found:
    print("⚠️ No XSS or token reflections were found — the graph will be empty.")

# Generate outputs
print_reflection_summary(context, ids, xss_found, tokens_found, scans - 1)
graph_reflection_summary(context, xss_found, tokens_found, app_config, folder=output_dir)
csv_reflection_summary(context, xss_found, tokens_found, scans - 1, app_config, folder=output_dir)
