import logging
import threading
import time

from ats.KiwoomDAO import KiwoomDAO
from ats.RunnerLocker import RunnerLocker
from ats.StockException import NoSuchStockPositionError


class AtsRunner(threading.Thread):
    config = None
    state = -1
    run_flag = True
    current_price: int
    logger = logging.getLogger(__name__)

    def __init__(self, config):
        super().__init__()
        self.config = config
        if "거래정지" in KiwoomDAO.instance().get_stock_state(self.config["stock_code"]):
            self.logger.info(self.__format_log_msg("거래정지 되었습니다."))
        if config.__contains__("state"):
            self.logger.info(self.__format_log_msg(f"이전 거래 데이터 불러왔습니다. state: {config['state']}"))
            self.state = config["state"]
            RunnerLocker.instance().open_locker()
        self.refresh_all_data()
        self.logger.info(self.__format_log_msg("실행 준비 완료"))

    def run(self):
        self.logger.info(self.__format_log_msg("스레드 가동"))

        try:
            self.processing_loop()
        except Exception as e:
            self.logger.exception(self.__format_log_msg("Exception 발생!!! 하기 로그 참조"))
            self.logger.exception(e)

        if self.state != -1 and self.state != 0:
            RunnerLocker.instance().close_locker()
        self.logger.info(self.__format_log_msg("스레드 종료합니다."))

    def processing_loop(self):
        while self.run_flag:
            self.refresh_all_data()
            if self.state == -1:
                # 거래 되지 않음
                RunnerLocker.instance().check_locker()
                if not self.run_flag:
                    break
                self.process_state_initial()
            elif self.state == 1:
                self.process_state_one()
            elif self.state == 2:
                self.process_state_two()
            elif self.state == 3:
                self.process_state_three()
            elif self.state == 0:
                self.run_flag = False
                RunnerLocker.instance().close_locker()
                self.logger.info(self.__format_log_msg("Locker Close 하였습니다."))
            time.sleep(0.1)

    def process_state_initial(self):
        # processing state: -1
        if self.current_price <= self.config["B1"]["price"]:
            RunnerLocker.instance().open_locker()
            self.logger.info(self.__format_log_msg("B1 매수 타점 도달하였습니다!"))
            self.open_position(self.config["B1"]["qty"])
            self.logger.info(self.__format_log_msg("Locker Open 하였습니다."))
            self.state = 1

    def process_state_one(self):
        # processing state: 1
        if self.current_price >= self.config["S1"]["price"]:
            self.logger.info(self.__format_log_msg("S1 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S1"]["qty"])
            self.state = 0
        elif self.current_price <= self.config["B2"]["price"]:
            self.logger.info(self.__format_log_msg("B2 매수 타점 도달하였습니다!"))
            self.open_position(self.config["B2"]["qty"])
            self.state = 2

    def process_state_two(self):
        # processing state: 2
        if self.current_price >= self.config["S3"]["price"]:
            self.logger.info(self.__format_log_msg("S3 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S3"]["qty"])
            self.state = 3
        elif self.current_price <= self.config["S5"]["price"]:
            self.logger.info(self.__format_log_msg("S5 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S5"]["qty"])
            self.state = 0

    def process_state_three(self):
        # processing state: 3
        if self.current_price >= self.config["S2"]["price"]:
            self.logger.info(self.__format_log_msg("S2 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S2"]["qty"])
            self.state = 0
        elif self.current_price <= self.config["S4"]["price"]:
            self.logger.info(self.__format_log_msg("S4 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S4"]["qty"])
            self.state = 0

    def open_position(self, qty):
        KiwoomDAO.instance().open_position(self.config["acc_no"], self.config["stock_code"], qty)

    def close_position(self, qty):
        try:
            KiwoomDAO.instance().close_position(self.config["acc_no"], self.config["stock_code"], qty=qty)
        except NoSuchStockPositionError:
            self.logger.info(self.__format_log_msg("매도하려고 했으나, 이미 사용자에 의해 전량 매도 되었습니다."))

    def refresh_all_data(self):
        self.current_price = KiwoomDAO.instance().get_current_price(self.config["stock_code"])

    def stop_and_save(self):
        self.run_flag = False
        self.config["state"] = self.state
        return self.config

    def __format_log_msg(self, msg):
        return f"{self.config['stock_name']}({self.config['stock_code']}): {msg}"
