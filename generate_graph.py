import pickle
import argparse
import matplotlib.pyplot as plt
import os
import pandas as pd
from config_types import AppConfig, TRAVERSAL, BREAKAGE, SCANNER

# Load payload attack types from CSV
CSV_PATH = "Generated_Test_Payloads.csv"
payload_df = pd.read_csv(CSV_PATH)
payload_df = payload_df.reset_index().rename(columns={'index': 'payload_id'})
payload_type_map = dict(zip(payload_df['payload_id'], payload_df['attack_type']))

# Custom unpickler using actual classes
def load_pickle_data(pickle_file):
    with open(pickle_file, 'rb') as f:
        try:
            class SafeUnpickler(pickle.Unpickler):
                def find_class(self, module, name):
                    if name == 'AppConfig':
                        return AppConfig
                    if name == 'BREAKAGE':
                        return BREAKAGE
                    if name == 'SCANNER':
                        return SCANNER
                    return super().find_class(module, name)

            data = SafeUnpickler(f).load()
            xss_found = data[0]  # list of successful payload IDs
            ids = data[4]        # list of all payload IDs tested
            return xss_found, ids
        except Exception as e:
            print(f"❌ Failed to load data from {pickle_file}: {e}")
            return [], []

def compute_stats(successful_ids, all_ids):
    stats = {
        'Reflected XSS': {'tested': 0, 'successful': 0},
        'Stored XSS':    {'tested': 0, 'successful': 0},
        'HTML Injection':{'tested': 0, 'successful': 0},
        'SQL Injection': {'tested': 0, 'successful': 0},
    }
    for pid in all_ids:
        attack_type = payload_type_map.get(pid)
        if attack_type in stats:
            stats[attack_type]['tested'] += 1
    for pid in successful_ids:
        attack_type = payload_type_map.get(pid)
        if attack_type in stats:
            stats[attack_type]['successful'] += 1
    return stats

def plot_attack_stats_comparison(stats_before, stats_after):
    attack_types = list(stats_before.keys())
    tested_before = [stats_before[a]['tested'] for a in attack_types]
    success_before = [stats_before[a]['successful'] for a in attack_types]
    tested_after = [stats_after[a]['tested'] for a in attack_types]
    success_after = [stats_after[a]['successful'] for a in attack_types]

    x = range(len(attack_types))
    width = 0.2

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar([i - width for i in x], tested_before, width, label='Tested (Before)', color='skyblue')
    ax.bar(x, success_before, width, label='Successful (Before)', color='orange')
    ax.bar([i + width for i in x], success_after, width, label='Successful (After)', color='seagreen')

    ax.set_ylabel('Payloads')
    ax.set_title('Attack Statistics Comparison by Type')
    ax.set_xticks(x)
    ax.set_xticklabels(attack_types)
    ax.legend()

    plt.tight_layout()
    plt.show()

def print_report(stats_before, stats_after):
    print(f"\n📊 Attack Statistics Report:")
    for attack in stats_before:
        tested_b = stats_before[attack]['tested']
        success_b = stats_before[attack]['successful']
        rate_b = (success_b / tested_b * 100) if tested_b > 0 else 0

        tested_a = stats_after[attack]['tested']
        success_a = stats_after[attack]['successful']
        rate_a = (success_a / tested_a * 100) if tested_a > 0 else 0

        print(f"- {attack}:")
        print(f"  Tested: {tested_b} → {tested_a}")
        print(f"  Successful: {success_b} → {success_a}")
        print(f"  Success Rate: {rate_b:.2f}% → {rate_a:.2f}%")

    overall_b = sum(s['tested'] for s in stats_before.values())
    overall_s_b = sum(s['successful'] for s in stats_before.values())
    overall_a = sum(s['tested'] for s in stats_after.values())
    overall_s_a = sum(s['successful'] for s in stats_after.values())

    rate_b = (overall_s_b / overall_b * 100) if overall_b > 0 else 0
    rate_a = (overall_s_a / overall_a * 100) if overall_a > 0 else 0

    print(f"\nOverall Stats:")
    print(f"Total Attacks: {overall_b} → {overall_a}")
    print(f"Total Successful: {overall_s_b} → {overall_s_a}")
    print(f"Overall Success Rate: {rate_b:.2f}% → {rate_a:.2f}%")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', default='xss_tokens.pickle', help='Pickle file before fix')
    parser.add_argument('--after', default='xss_tokens_after_fix.pickle', help='Pickle file after fix')
    args = parser.parse_args()

    print(f"✅ Using pickle files: {args.before} and {args.after}")

    if not os.path.exists(args.before) or not os.path.exists(args.after):
        print("❌ One or both pickle files not found.")
        return

    # Load and parse data
    xss_before, ids_before = load_pickle_data(args.before)
    xss_after, ids_after = load_pickle_data(args.after)

    stats_before = compute_stats(xss_before, ids_before)
    stats_after = compute_stats(xss_after, ids_after)

    print_report(stats_before, stats_after)
    plot_attack_stats_comparison(stats_before, stats_after)

if __name__ == '__main__':
    main()
