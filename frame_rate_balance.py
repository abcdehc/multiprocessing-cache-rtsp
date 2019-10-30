import multiprocessing
import time
import av
import cv2
import threading
import numpy as np
import os
from fractions import Fraction      # Fraction(分子,分母)

class Cache_frame(object):
    """
    self.address:设定地址\n
    self.encoding_tool:可选择"pyav"或"opencv"解码\n
    self.top:缓冲区可以储存的帧数量\n
    self.speed_addition:视频自带属性默认的帧率错误(过低)时用于调整增加\n
    """
    def __init__(self):
        self.last_frame = None
        self.q = multiprocessing.Queue(1)
        self.buffer = []
        self.polynomial = None
        self.speed = 25

        self.speed_addition = 1
        self.address = "http://ivi.bupt.edu.cn/hls/cctv1hd.m3u8" 
        self.encoding_tool = "pyav"
        self.top = 400

    def write(self) -> None:
        # p = psutil.Process()
        # p.cpu_affinity([4])
        last = np.zeros(0,dtype=np.uint8)
        print('Process to write: %s' % os.getpid())
        event1 = threading.Event()
        buffer = []

        def running_av():
            nonlocal buffer ,event1 
            container = av.open(self.address, mode = 'r', options = {'rtsp_transport':'tcp'})
            container.streams.video[0].thread_type = 'AUTO' #多线程解码
            self.speed = container.streams.video[0].average_rate
            for frame in container.decode(video=0):

                buffer.append(frame.to_ndarray(format='bgr24'))

        def running_cv():
            nonlocal buffer
            cap = cv2.VideoCapture(self.address)
            while True:
                success, new_fream = cap.read()
                if success:
                    buffer.append(new_fream)

        def pts_speed_func():   # 计算函数控制缓存图片量与播放速度之间的映射关系，若视频源足够稳定，则播放速度将稳定在真实值
            x = np.array([-self.top/4, 0, self.top/2, self.top, 3*self.top/2, 2*self.top, 9*self.top/4])
            print(x)
            y = np.array([-2*self.speed, 0, self.speed, self.speed+self.speed_addition, self.speed, 0, -2*self.speed])
            print(y)
            z = np.polyfit(x, y, 6)
            print(z)
            self.polynomial = np.poly1d(z.astype(np.float32))
            print(self.polynomial)
            
        def sleep_time(long):   # 调用控制播放速度的函数获得到下一帧的间隔时间
            return 1/self.polynomial(long)
            # a = self.polynomial(long)
            # b = 1/a
            # print("buffer length:", long, "play speed:", a)
            # return b

        def cache_last():
            nonlocal buffer, last, event1

            pts_speed_func()
            while True:
                if len(buffer) > self.top/2:
                    while True:
                        try:
                            last = buffer.pop(0)
                            event1.set()
                        except:
                            continue
                        if len(buffer) > self.top:
                            del buffer[0:-self.top+1]

                            self.speed_addition = self.speed_addition + 1
                            pts_speed_func()    # 当缓冲区不足以存放所有图片时，说明函数对应的最高速率不正确，所以增加速率最大值后重置速率函数
                            
                        time.sleep(sleep_time(len(buffer)))
                time.sleep(1)

        if self.encoding_tool == "pyav":
            t1=threading.Thread(target=running_av)
        elif self.encoding_tool == "opencv":
            t1=threading.Thread(target=running_cv)
        else:
            print("no such encoding tool")
        t1.start()
        t2=threading.Thread(target=cache_last)
        t2.start()

        while True:
            event1.wait()
            self.q.put(last)
            event1.clear()

    def read(self) -> None: 
        # print("开始读取一帧")

        self.last_frame = self.q.get()

        return self.last_frame 

    def run(self):
        pw = multiprocessing.Process(target=self.write)
        pw.start()


if __name__ == '__main__':
    ca = Cache_frame()
    # ca.encoding_tool = "opencv"

    t2=threading.Thread(target=ca.run)
    t2.start()

    while True:
        img = ca.read()
        
        # img = transform.resize(img, (270, 480))
        img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5) 

        key = cv2.waitKey(1) & 0xFF
        cv2.imshow("video", img)
        if key == ord('q'):
                break