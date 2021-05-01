import threading

from ats.ConfigParser import ConfigParser


class RunnerLocker():
    __semaphore: threading.Semaphore

    def __init__(self):
        self.__semaphore = threading.Semaphore(ConfigParser.instance().load_maximum_trading())

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    def check_locker(self):
        self.__semaphore.acquire()
        self.__semaphore.release()

    def open_locker(self):
        self.__semaphore.acquire(blocking=False)

    def close_locker(self):
        self.__semaphore.release()
