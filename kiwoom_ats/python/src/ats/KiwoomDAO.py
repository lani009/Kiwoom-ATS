import logging
import threading
from typing import Dict, List

from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from PyQt5.QtTest import QTest

from ats.StockException import (NoSuchStockCodeError,
                                 NoSuchStockPositionError,
                                 StockUpperBoundNotFoundError)


class KiwoomDAO():
    __log = logging.getLogger(__name__)
    __thread_locker = threading.Lock()
    __instance = None
    __current_price_map: Dict[str, int] = dict()
    __tr_rq_single_data = None
    __tr_rq_multi_data = None
    __tr_data_cnt_limit = 0
    __market_status = -1
    __scr_no_counter = 2000
    __scr_no_map: Dict[str, str] = dict()

    def __init__(self):
        self.kiwoom_instance = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.__register_all_slots()
        self.__tr_global_eventloop = QEventLoop()

        if int(self.kiwoom_instance.dynamicCall("GetConnectState()")) == 0:
            self.__login_eventloop = QEventLoop()    # 로그인 전용 이벤트 루프
            self.kiwoom_instance.dynamicCall("CommConnect()")
            self.__login_eventloop.exec_()
        else:
            self.__log.info("이미 로그인 되어 있습니다.")

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    @classmethod
    def inject(cls, instance):
        cls.__instance = instance
        cls.instance = cls.__get_instance

    def get_stock_name(self, stock_code: str) -> str:
        '''종목명 리턴

        Parameters
        ----------
        stock_code : str
            종목 코드

        Returns
        -------
        str
            종목명
        '''
        self.__thread_locker.acquire()
        name = self.kiwoom_instance.dynamicCall(
            "GetMasterCodeName(QString)", stock_code)
        self.__thread_locker.release()
        if (name.__len__() == 0):
            raise NoSuchStockCodeError(f"{stock_code} is not valid stock code")
        return name

    def get_available_balance(self, acc_no: str) -> int:
        '''예수금

        Parameters
        ----------
        acc_no : str
            계좌번호
        '''
        self.__thread_locker.acquire()
        balance = int(self.__get_tr_data({
            "계좌번호": acc_no,
            "비밀번호": "",
            "상장폐지조회구분": "1",
            "비밀번호입력매체구분": "00"
        }, "주식 잔고 요청", "OPW00004", "0", "5000", ["예수금"], [])["single_data"]["예수금"])
        self.__thread_locker.release()
        return balance

    def get_current_price(self, stock_code: str) -> int:
        if (not self.__current_price_map.__contains__(stock_code)):
            self.__thread_locker.acquire()
            current_price: str = self.__get_tr_data({
                                "종목코드": stock_code
                            }, "현재가 요청", "OPT10003", "0", self.__generate_scr_no(stock_code), ["현재가"], [], cnt=1)["single_data"]["현재가"]
            if current_price.__len__() == 0:
                raise RuntimeError(f"{stock_code} 종목의 현재가 받아올 수 없음")
            current_price = abs(int(current_price))

            self.__current_price_map.setdefault(stock_code, current_price)
            self.__log.info(f"{stock_code} 실시간 시세 등록")
            self.kiwoom_instance.dynamicCall(
                "SetRealReg(QString, QString, QString, QString)", self.__generate_scr_no(stock_code), stock_code, "10", "1")
            self.__thread_locker.release()

        return self.__current_price_map[stock_code]

    def get_stock_state(self, stock_code: str):
        self.__thread_locker.acquire()
        val: str = self.kiwoom_instance.dynamicCall("GetMasterStockState(QString)", stock_code)
        self.__thread_locker.release()
        out_val = val.strip().split("|")[1:]
        return out_val

    def open_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        self.kiwoom_instance.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", [
                "주식 매수 주문", self.__generate_scr_no(stock_code), acc_no, 1, stock_code, qty, 0, "03", ""])
        self.__log.info(
            f"매수 주문\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}")

    def close_position(self, acc_no: str, stock_code: str, qty=0) -> None:
        if qty == 0:
            self.__thread_locker.acquire()
            holding_stock_list = self.__get_tr_data({
                "계좌번호": acc_no,
                "비밀번호": "",
                "상장폐지조회구분": "1",
                "비밀번호입력매체구분": "00"
            }, "보유 종목 요청", "OPW00004", "0", self.__generate_scr_no(stock_code), [], ["종목코드", "보유수량"])
            self.__thread_locker.release()
                          
            for stock in holding_stock_list["multi_data"]:
                if (stock["종목코드"][1:].strip() == stock_code):
                    qty = int(stock["보유수량"])
                    break
            if qty == 0:
                raise NoSuchStockPositionError(f"{acc_no} 계좌에 {stock_code} 종목 보유수량이 없습니다.")
        self.__log.info(
            f"매도 주문\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}")
        self.kiwoom_instance.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", [
                "주식 매도 주문", self.__generate_scr_no(stock_code), acc_no, 2, stock_code, qty, 0, "03", ""])

    def __get_tr_data(self, input_value: Dict[str, str], rq_name, tr_code, perv_next: str, scr_no: str,
                      rq_single_data: List[str], rq_multi_data: List[str], cnt=0):
        '''키움 API서버에 TR 데이터를 요청한다.
        Parameters
        ----------
        input_value :
            KOA Studio 기준으로, SetInputValue에 들어갈 값

        trEnum : TrCode
            KOA Studio 기준, Tr 코드

        perv_next :
            prevNext

        scr_no :
            스크린 번호

        rq_single_data :
            받아오고자 하는 싱글데이터 목록

        rq_multi_data :
            받아오고자 하는 멀티데이터 목록

        Returns
        -------
        Dict[str, Dict[str, str]]
        '''
        self.__tr_data_cnt_limit = cnt
        self.__tr_rq_single_data = rq_single_data
        self.__tr_rq_multi_data = rq_multi_data

        self.__set_input_values(input_value)   # inputvalue 대입

        self.__comm_rq_data(rq_name, tr_code, perv_next, scr_no)
        self.__tr_global_eventloop = QEventLoop()
        self.__tr_global_eventloop.exec_()
        return self.__tr_data_temp

    def __generate_scr_no(self, stock_code: str) -> str:
        if (not self.__scr_no_map.__contains__(stock_code)):
            self.__scr_no_map[stock_code] = str(self.__scr_no_counter)
            self.__scr_no_counter += 1

        return self.__scr_no_map[stock_code]

    def __comm_rq_data(self, rq_name, tr_code, n_prev_next, scr_no):
        val = self.kiwoom_instance.dynamicCall(
                "CommRqData(QString, QString, QString, QString)", rq_name, tr_code, n_prev_next, scr_no)
        val = int(val)
        if (val != 0):
            if val == -200:
                self.__log.fatal(f"RQ DATA [{val}]: 시세 과부하")
            elif val == -201:
                self.__log.fatal(f"RQ DATA [{val}]:  조회 전문작성 에러")
            self.__log.fatal(f"RQ DATA [{val}]: 에러 발생!!!")

    def __set_input_values(self, input_value: Dict[str, str]):
        '''
        SetInputVlaue() 동적 호출 iteration 용도
        '''
        for k, v in input_value.items():
            self.kiwoom_instance.dynamicCall(
                "SetInputValue(QString, QString)", k, v)

    def __on_receive_tr_data(self, scr_no, rq_name, tr_code, prev_next):
        '''
        CommRqData 처리용 슬롯
        '''
        if (tr_code == "KOA_NORMAL_BUY_KQ_ORD"):
            print(scr_no, rq_name, tr_code)
            return

        # tr데이터 중, 멀티데이터의 레코드 개수를 받아옴.
        if (self.__tr_data_cnt_limit == 0):
            n_record = self.kiwoom_instance.dynamicCall(
                "GetRepeatCnt(QString, QString)", tr_code, rq_name)
        else:
            n_record = min(self.kiwoom_instance.dynamicCall(
                "GetRepeatCnt(QString, QString)", tr_code, rq_name), self.__tr_data_cnt_limit)

        self.__tr_data_temp = dict()     # 이전에 저장되어 있던 임시 tr_data 삭제.
        self.__tr_data_temp["single_data"] = dict()     # empty dict 선언
        for s_data in self.__tr_rq_single_data:
            self.__tr_data_temp["single_data"][s_data] = self.kiwoom_instance.dynamicCall(
                "GetCommData(QString, QString, int, QString)", tr_code, rq_name, 0, s_data).strip()

        self.__tr_data_temp["multi_data"] = list()
        for i in range(n_record):
            m_data_dict_temp = dict()   # 멀티데이터에서 레코드 하나에 담길 딕셔너리 선언
            for m_data in self.__tr_rq_multi_data:
                m_data_dict_temp[m_data] = self.kiwoom_instance.dynamicCall(
                    "GetCommData(QString, QString, int, QString)", tr_code, rq_name, i, m_data).strip()
            self.__tr_data_temp["multi_data"].append(m_data_dict_temp)
        self.__tr_global_eventloop.exit()

    def __on_event_connect_slot(self, err_code):
        if (err_code == 0):
            self.__log.info("로그인 성공")
        else:
            self.__log.info("로그인 실패")

        if (self.kiwoom_instance.dynamicCall("GetLoginInfo(\"GetServerGubun\")") == "1"):
            self.__log.info("모의투자 서버 접속")
        else:
            self.__log.info("실거래 서버 접속")

        self.__login_eventloop.exit()

    def __on_receive_msg(self, scr_no, rq_name, tr_code, msg):
        self.__log.info(f"{rq_name}: {msg}")

    def __on_receive_real_data(self, stock_code, real_type, real_data):
        # self.__log.debug(f"{real_type}, {stock_code}")
        if (real_type == "주식체결"):
            self.__current_price_map[stock_code] = abs(int(self.kiwoom_instance.dynamicCall(
                "GetCommRealData(QString, int)", stock_code, 10)))
        elif (real_type == "장시작시간"):
            self.__market_status = int(self.kiwoom_instance.dynamicCall(
                "GetCommRealData(QString, int)", stock_code, 215))
            self.__log.info(f"market status: {self.__market_status}")
            if (self.__market_status == 8):
                self.__log.info("장 종료")

    def __on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        acc_no = self.kiwoom_instance.dynamicCall("GetChejanData(9201)")
        stock_code = self.kiwoom_instance.dynamicCall(
            "GetChejanData(9001)")[1:].strip()

        if (gubun == "0"):
            # self.__log.info(f"주문 체결 완료되었습니다!!!\n  계좌번호: {acc_no}, 종목코드: {stock_code}")
            pass
        elif (gubun == "1"):
            self.__log.info(
                f"주문 체결 완료되었습니다!!!\n  계좌번호: {acc_no}, 종목코드: {stock_code}")

    def __register_all_slots(self):
        self.kiwoom_instance.OnEventConnect.connect(
            self.__on_event_connect_slot)
        self.kiwoom_instance.OnReceiveRealData.connect(
            self.__on_receive_real_data)
        self.kiwoom_instance.OnReceiveTrData.connect(self.__on_receive_tr_data)
        self.kiwoom_instance.OnReceiveMsg.connect(self.__on_receive_msg)
        self.kiwoom_instance.OnReceiveChejanData.connect(
            self.__on_receive_chejan_data)
