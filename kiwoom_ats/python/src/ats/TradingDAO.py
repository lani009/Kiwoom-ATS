import sqlite3


class TradingDAO:
    __conn = None

    def __init__(self):
        self.__conn = sqlite3.connect("./resources/database/ats.db")

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    def get_unfinished_trading_data(self):
        cur = self.__conn.cursor()
        cur.execute("SELECT * FROM unfinished_trading")
        rows = cur.fetchall()

        data_list = list()
        for row in rows:
            data = {
                "stock_code": row[0],
                "B1": {"price": row[1], "qty": row[2]},
                "B2": {"price": row[3], "qty": row[4]},
                "S1": {"price": row[5], "qty": row[6]},
                "S2": {"price": row[7], "qty": row[8]},
                "S3": {"price": row[9], "qty": row[10]},
                "S4": {"price": row[11], "qty": row[12]},
                "S5": {"price": row[13], "qty": row[14]},
                "state": row[15],
            }
            data_list.append(data)
        return data_list

    def save_unfinished_trading_data(self, data):
        cur = self.__conn.cursor()
        cur.execute(
            """
            SELECT * FROM unfinished_trading WHERE unfinished_trading.stock_code = ?
        """,
            (data["stock_code"],),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO unfinished_trading VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ? ,?, ?, ?, ?, ?, ?)",
                (
                    data["stock_code"],
                    data["B1"]["price"],
                    data["B1"]["qty"],
                    data["B2"]["price"],
                    data["B2"]["qty"],
                    data["S1"]["price"],
                    data["S1"]["qty"],
                    data["S2"]["price"],
                    data["S2"]["qty"],
                    data["S3"]["price"],
                    data["S3"]["qty"],
                    data["S4"]["price"],
                    data["S4"]["qty"],
                    data["S5"]["price"],
                    data["S5"]["qty"],
                    data["state"],
                ),
            )
        else:
            cur.execute(
                """
                UPDATE unfinished_trading
                    SET
                        state = ?
                    WHERE
                        stock_code = ?
            """,
                (data["state"], data["stock_code"]),
            )
        self.__conn.commit()
        cur.close()

    def remove_trading_data(self, stock_code: str):
        cur = self.__conn.cursor()
        cur.execute(
            """
            DELETE FROM unfinished_trading WHERE stock_code = ?
        """,
            (stock_code,),
        )

        self.__conn.commit()
        cur.close()
