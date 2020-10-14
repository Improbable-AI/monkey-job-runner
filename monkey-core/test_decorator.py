import functools
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor


class Examp():

    item = 0
    lock = threading.Lock()
    run_thread = None
    executor = ThreadPoolExecutor(max_workers=1)

    def threaded(fn):
        def wrapper(*args, **kwargs):
            self = args[0]
            future = Future()

            def run_thread(r_fn, r_future, *r_args, **r_kwargs):
                try:
                    # print("run_thread args", r_fn, r_future, *r_args,
                    #       **r_kwargs)
                    result = r_fn(*r_args, **r_kwargs)
                    r_future.set_result(result)
                except Exception as e:
                    print("Exception received")
                    if r_future.cancelled() == False:
                        r_future.set_exception(e)

            with self.lock:
                thread = threading.Thread(target=run_thread,
                                          args=(
                                              fn,
                                              future,
                                          ) + (args),
                                          kwargs=kwargs)
                thread.start()
                print("running stuff")

            def callback(c_future):
                print("Callback created: ", c_future)
                print("Callback thread: ", thread)
                if c_future.cancelled():
                    print("Killing thread")
                    thread.raise_exception()

            future.add_done_callback(callback)
            return future

        return wrapper

    # def threaded(fn):
    #     def wrapper(*args, **kwargs):
    #         self = args[0]

    #         with self.lock:
    #             future = self.executor.submit(fn, *args, **kwargs)
    #             print("running stuff")
    #         return future

    #     return wrapper

    # def runner(func):
    #     @functools.wraps(func)
    #     def wrapper(self, *args, **kwargs):
    #         with self.lock:
    #             print("Item: ", self.item)
    #             print("Acquired lock")
    #             # func(*args, **kwargs)
    #             thread = threading.Thread(target=func,
    #                                       args=args,
    #                                       kwargs=kwargs)
    #             self.run_thread = thread
    #             print("Finished running")
    #         thread.start()

    #     return wrapper

    def __init__(self, item=6):
        self.item = item

    @threaded
    def run_8(self, stime=8):

        print("start run_8 for ", stime)
        print(self)
        print(self.item)
        time.sleep(stime)
        print("finished run_8 for ", stime)
        return stime

    @threaded
    def run_2(self, stime=2):
        print("run_2 args", self, stime)
        print("start run_2 for ", stime)
        time.sleep(stime)
        self.item += 4
        print("finished run_2 for ", stime)
        return stime


e = Examp()


def run1():
    print("result", e.run_2(10).result())


def run2():
    time.sleep(1)
    r = e.run_2(stime=5)
    return r


r = e.run_2(stime=5)
print(e.item)
print(r)
time.sleep(2)
can = r.cancel()
print("Cancelled: ", can)
print("Results: ", r.result())
print(e.item)

time.sleep(12)
# tr = threading.Thread(target=run1)
# tr.start()
# # time.sleep(1)
# print("Post start", e.run_thread)
# print(tr.result())
# time.sleep(4)
