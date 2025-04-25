import logging
import re
import subprocess
import sys
from typing import Any, Optional

from mysql.connector import Error, connect

from Helper import write_msg

ColInfo = tuple[str, str, int, list]
KeyInfo = tuple[str, str]


class DatabaseConfig(object):
    """Holds the configuration for a database connection"""

    def __init__(self, host: str, user: str, password: str,
                 database: str, port: int = 3306,
                 mysql: str = "mysql", mysqldump: str = "mysqldump") -> None:
        """Initialize"""

        self.host      = host
        self.user      = user
        self.password  = password
        self.database  = database
        self.port      = port
        self.mysql     = mysql
        self.mysqldump = mysqldump


class Database(object):
    """Class through which the SQL database can be accessed"""

    def __init__(self, config: DatabaseConfig) -> None:
        """Initialize a connection based on a config"""

        self.config     = config
        self.connection = self.create_server_connection()

    def create_server_connection(self) -> Any:
        """Helper method to create a connection"""
        return connect(
            host=self.config.host,
            user=self.config.user,
            passwd=self.config.password,
            database=self.config.database,
            port=self.config.port)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> int:
        """Helper method to execute a query"""

        cursor = self.connection.cursor()
        logging.debug(('dbfuzz', 'database', 'execute', 'sql', query, params))
        try:
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount
        except Error as err:
            write_msg(f"SQL error: '{err}'")
            logging.warning(f"{self.execute_query.__name__}: {err}")
            logging.debug(('dbfuzz', 'database', 'execute', 'error', query, params, str(err)))
            return -1

    def read_query(self, query: str, params: Optional[tuple] = None) -> Optional[list[tuple]]:
        """Helper method to read a query"""

        cursor = self.connection.cursor()
        logging.debug(('dbfuzz', 'database', 'read', 'sql', query, params))
        result = None
        try:
            cursor.execute(query, params)
            result = cursor.fetchall()
            return result
        except Error as err:
            write_msg(f"SQL error: '{err}'")
            logging.warning(f"{self.read_query.__name__}: {err}")
            logging.debug(('dbfuzz', 'database', 'read', 'error', query, params, str(err)))
            return None

    def read_query_(self, query: str, params: Optional[tuple] = None) -> list[tuple]:
        ret = self.read_query(query, params)
        assert ret is not None
        return ret

    def get_tables(self) -> list[str]:
        query = "SHOW TABLES"
        result = self.read_query_(query)
        return [r[0] for r in result]

    def get_columns(self, table: str) -> list[str]:
        query = f"SHOW COLUMNS FROM `{table}`"
        result = self.read_query_(query)
        return [r[0] for r in result]

    def get_columns_info(self, table: str) -> list[ColInfo]:
        query = f"SHOW COLUMNS FROM `{table}`"
        result = self.read_query_(query)
        return [(r[0], r[1], r[2] if isinstance(r[2], int) else 0, []) for r in result]

    def get_key_info(self, table: str) -> list[KeyInfo]:
        query = f"SHOW KEYS FROM `{table}`"
        result = self.read_query_(query)
        return [(r[4], r[2]) for r in result]

    def get_data(self, table: str) -> list[tuple]:
        query = f"SELECT * FROM `{table}`"
        return self.read_query_(query)

    def get_length(self, table: str) -> int:
        query = f"SELECT COUNT(*) FROM `{table}`"
        result = self.read_query_(query)
        return result[0][0] if result else 0

    def is_row_in_table(self, table: str, row: tuple, col_info: list[ColInfo], key_info: list[KeyInfo], primary: bool = False) -> bool:
        where_clause = " AND ".join([f"`{col_info[i][0]}`=%s" for i in range(len(row))])
        query = f"SELECT COUNT(*) FROM `{table}` WHERE {where_clause}"
        result = self.read_query(query, tuple(row))
        return result is not None and result[0][0] > 0

    def update_row(self, table: str, old_row: tuple, new_row: tuple,
               columns: list, col_info: list, key_info: list,
               primary: bool = False) -> int:
        """Update a row in the given table using primary keys (if available)."""

        # Construct SET clause
        set_clause = ", ".join(f"`{col}`=%s" for col in columns)

        # Determine WHERE clause using primary keys
        key_columns = []
        key_values = []

        if primary:
            for key in key_info:
                col_name, key_type = key
            if key_type == "PRIMARY" and col_name in columns:
                key_columns.append(f"`{col_name}`=%s")
                col_index = columns.index(col_name)
                key_values.append(old_row[col_index])

        # ✅ Fallback if no primary keys were matched or primary=False
        if not key_columns:
            key_columns = [f"`{col}`=%s" for col in columns]
            key_values = list(old_row)

        where_clause = " AND ".join(key_columns)

        # Final query
        query = f"UPDATE `{table}` SET {set_clause} WHERE {where_clause}"
        params = tuple(new_row) + tuple(key_values)

        return self.execute_query(query, params)

             
      

    def delete_row(self, table: str, row: tuple, col_info: list[ColInfo], key_info: list[KeyInfo], primary: bool = False) -> int:
        where_clause = " AND ".join([f"`{col_info[i][0]}`=%s" for i in range(len(row))])
        query = f"DELETE FROM `{table}` WHERE {where_clause}"
        return self.execute_query(query, tuple(row))

    def delete_all_rows(self, table: str) -> int:
        query = f"DELETE FROM `{table}`"
        return self.execute_query(query)

    def insert_row(self, table: str, row: tuple) -> bool:
        placeholders = ", ".join(["%s"] * len(row))
        query = f"INSERT INTO `{table}` VALUES ({placeholders})"
        return self.execute_query(query, tuple(row)) == 1

    def generate_row(self, col_info: list[ColInfo], j: int) -> tuple:
        row = []
        for col_name, col_type, col_size, _ in col_info:
            if 'int' in col_type:
                row.append(j)
            elif 'char' in col_type or 'text' in col_type:
                row.append(f"test{j}")
            elif 'date' in col_type or 'time' in col_type:
                row.append("2025-01-01")
            else:
                row.append(None)
        return tuple(row)

    def invalid_row_date(self, row: tuple, col_info: list[ColInfo]) -> bool:
        for i, (_, col_type, _, _) in enumerate(col_info):
            if "date" in col_type or "time" in col_type:
                val = row[i]
                if val is None:
                    return True
        return False

    @staticmethod
    def sql_string_type_size(column_type: str, column_size: int) -> int:
        if 'char' in column_type:
            return column_size
        if 'text' in column_type:
            return 65535
        return 255

    @staticmethod
    def is_type_string(column_type: str) -> bool:
        return 'char' in column_type or 'text' in column_type

    def make_backup(self) -> bytes:
        return subprocess.check_output(
            [self.config.mysqldump,
             f"--host={self.config.host}",
             f"--port={self.config.port}",
             f"--user={self.config.user}",
             f"--password={self.config.password}",
             "--protocol=tcp",
             self.config.database,
             "--skip-ssl"])

    def restore_backup(self, backup: bytes) -> subprocess.CompletedProcess:
        # ✅ SAFETY: Don't drop or create the entire database!
        # Instead, just attempt to restore data into the existing DB.
        ret = subprocess.run([self.config.mysql,
                              f"--host={self.config.host}",
                              f"--port={self.config.port}",
                              f"--user={self.config.user}",
                              f"--password={self.config.password}",
                              f"--database={self.config.database}",
                              "--protocol=tcp"],
                             stdout=subprocess.PIPE,
                             input=backup)
        self.connection = self.create_server_connection()
        return ret

    @staticmethod
    def test() -> None:
        pass  # placeholder for future tests or assertions


if __name__ == "__main__":
    Database.test()
