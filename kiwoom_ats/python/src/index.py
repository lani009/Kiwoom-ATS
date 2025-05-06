import datetime
import json
import logging
import logging.config
import os
import sys

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from ats.ConfigParser import ConfigParser
from ats.KiwoomDAO import KiwoomDAO
from ats.RunnerController import Controller
from ats.TradingDAO import TradingDAO


def get_market_closeing_time() -> datetime.datetime:
    market_close_time = datetime.datetime.now()
    return market_close_time.replace(hour=15, minute=20, second=0, microsecond=0)


def get_market_start_time() -> datetime.datetime:
    return datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


def is_before_market_start_time() -> bool:
    return (get_market_start_time() - datetime.datetime.now()).total_seconds() > 0


def is_after_market_close_time() -> bool:
    return (get_market_closeing_time() - datetime.datetime.now()).total_seconds() < 0


def wait_until_market_start():
    QTest.qWait(int((get_market_start_time() - datetime.datetime.now()).total_seconds() * 1000))


def wait_until_market_close():
    QTest.qWait(int((get_market_closeing_time() - datetime.datetime.now()).total_seconds() * 1000))


def get_hms(a, b):
    """
    a > b
    """
    time_delta = a - b
    hour = int(time_delta.total_seconds() // 3600)
    minute = int((time_delta.total_seconds() // 60) % 60)
    second = int(time_delta.total_seconds() - hour * 3600 - minute * 60)

    return hour, minute, second


def index():
    with open("./resources/log/logging.json") as f:
        config = json.load(f)
    logging.config.dictConfig(config)

    app = QApplication(sys.argv)

    KiwoomDAO.instance()

    controller = Controller()

    stock_list = TradingDAO.instance().get_unfinished_trading_data()

    if is_after_market_close_time():
        print("이미 장 종료되었습니다.")
        print("===== 내일 진행할 거래 =====")

    if stock_list.__len__() == 0:
        print("이전에 진행하던 거래 없음")
    else:
        print("===== 이전 거래 이어서 진행 =====")
        for stock in stock_list:
            stock["stock_name"] = KiwoomDAO.instance().get_stock_name(stock["stock_code"])
            controller.add_runner(stock)
            print(f"{stock['stock_name']}({stock['stock_code']})")
            QTest.qWait(1000)

    stock_list = ConfigParser.instance().load_stock_config()

    if stock_list.__len__() == 0:
        print("입력된 새로운 종목이 없습니다.")
    else:
        print("===== 새로운 종목 =====")
        for stock in stock_list:
            controller.add_runner(stock)
            print(f"{stock['stock_name']}({stock['stock_code']})")
            QTest.qWait(1000)

    if is_after_market_close_time():
        sys.exit()

    if controller.runner_list.__len__() == 0:
        print("에러: 실행할 종목이 아무것도 없습니다!")
        sys.exit()

    if is_before_market_start_time():
        hour, minute, second = get_hms(get_market_start_time(), datetime.datetime.now())
        print(f"\n장 시작 까지 {hour}시간 {minute}분 {second}초 남았습니다.")
        wait_until_market_start()
    print("장 시작하였습니다!\n5초 후 프로그램 가동!!!\a")
    QTest.qWait(5000)
    print("\a")
    controller.run_all()

    hour, minute, second = get_hms(get_market_closeing_time(), datetime.datetime.now())
    print(f"\n장 종료 까지 {hour}시간 {minute}분 {second}초 남았습니다.\n")
    wait_until_market_close()

    print("장 종료")
    controller.stop_and_save_all()
    app.exit()

    print("프로그램 종료")

    if ConfigParser.instance().load_is_power_off():
        print("컴퓨터 종료합니다")
        os.system("shutdown /s /t 1")
    else:
        sys.exit()


if __name__ == "__main__":
    index()
