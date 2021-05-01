class NoSuchStockCodeError(Exception):
    # 입력받은 주식 코드가 코스닥, 코스피 상에 존재하지 않음.
    pass

class StockHaltWarning(Exception):
    # 해당 주식이 거래정지 됨.
    pass

class NoSuchStockPositionError(Exception):
    # 해당 주식을 보유하고 있지 않음.
    pass
