import json
from enum import Enum
from logging import warning
from typing import Any, Optional
import pandas as pd

from Database import ColInfo, Database, KeyInfo
from Helper import write_msg

Columns = list[str]
Pos = tuple[int, int]

class DbId(object):
    def __init__(self, database: str, table: str, column: str, position: Pos, step: int, old: list, new: list, attack_type: str = "Unknown") -> None:
        self.database = database
        self.table = table
        self.column = column
        self.position = tuple(position)
        self.step = step
        self.old = old[::]
        self.new = new[::]
        self.attack_type = attack_type

    def __str__(self) -> str:
        return f'{self.table}.{self.column}'

    def pos(self) -> str:
        return f'{self.database}.{self.table}.{self.column}[{self.position[0]}][{self.position[1]}]'

    def details(self) -> str:
        return f"""
            {self.pos()}
            original row: {self.old}
            fuzzed row: {self.new}
            change: '{self.old[self.position[1]]}' => '{self.new[self.position[1]]}'
            attack_type: {self.attack_type}
            """

# ID context tracking
ids = [-1]
context = {-1: DbId("", "", "", (-1, -1), -1, [], [], "Unknown")}

# ─── Load Payloads from CSV ───────────────────────────────────────────
CSV_PATH = "C:/Users/HP/OneDrive/Documents/computerSecurityProject/Generated_Test_Payloads.csv"
payload_df = pd.read_csv(CSV_PATH)

if "payload" not in payload_df.columns or "attack_type" not in payload_df.columns:
    raise KeyError(f"'payload' and 'attack_type' columns must be present in {CSV_PATH}")

payloads = payload_df[["payload", "attack_type"]].dropna().values.tolist()
payload_index = 0

# Counters for vulnerability statistics
vulnerability_stats = {
    "Reflected XSS": {"tested": 0, "successful": 0},
    "Stored XSS": {"tested": 0, "successful": 0},
    "HTML Injection": {"tested": 0, "successful": 0},
    "SQL Injection": {"tested": 0, "successful": 0},
}

# Fuzzable column threshold
PAYLOAD_LENGTH = 1

def is_fuzzable_col(c: ColInfo) -> bool:
    column, column_type, column_size, column_values = c
    column_size = Database.sql_string_type_size(column_type, column_size)
    is_string = Database.is_type_string(column_type)
    ok_size = column_size is not None and column_size >= PAYLOAD_LENGTH
    not_enum_or_set = column_type not in {'enum', 'set'}

    if not (is_string and ok_size and not_enum_or_set):
        print(f"[DEBUG] Skipping column '{column}' (type={column_type}, size={column_size})")

    return is_string and ok_size and not_enum_or_set

def get_payload() -> tuple[str, str]:
    global payload_index
    if payload_index >= len(payloads):
        raise IndexError("Ran out of payloads in CSV!")
    p, ptype = payloads[payload_index]
    payload_index += 1
    return p.strip(), ptype.strip()

def update_payload(db: Database, table: str, row: tuple,
                   columns: Columns, col_info: list[ColInfo], key_info: list[KeyInfo],
                   pos: Pos, scan: int,
                   advanced: bool = True, primary: bool = False) -> tuple:
    _, c_i = pos
    try:
        payload, payload_type = get_payload()
    except IndexError:
        write_msg("No more payloads available.")
        return row

    new = list(row)
    new[c_i] = payload

    vulnerability_stats[payload_type]["tested"] += 1

    if db.update_row(table, row, tuple(new), columns, col_info, key_info, primary=primary) != 1:
        write_msg(f'old: {row}')
        write_msg(f'new: {new}')
        write_msg('failure!')
        warning(f"failed to update {db}.{table} row at {pos} from {row} to {new}")
        return row
    else:
        pid = payload_index - 1
        context[pid] = DbId(
            database=db.config.database,
            table=table,
            column=columns[c_i],
            position=pos,
            step=scan,
            old=list(row),
            new=list(new),
            attack_type=payload_type
        )
        write_msg(f'success! payload {pid}')

        if any(x in payload.lower() for x in ["<script>", "xss", "alert", "onerror"]):
            vulnerability_stats[payload_type]["successful"] += 1

        return tuple(new)

# ─── Stats Tracker (optional external injection) ───────────────────────
stats = None

def set_stats_tracker(external_stats):
    global stats
    stats = external_stats

def print_vulnerability_summary():
    print("\n==== Vulnerability Statistics Summary ====")
    for attack, data in vulnerability_stats.items():
        tested = data["tested"]
        success = data["successful"]
        success_rate = (success / tested) * 100 if tested else 0
        print(f"- {attack}: Tested={tested}, Successful={success}, Success Rate={success_rate:.2f}%")
    print("==========================================\n")
