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
    def __init__(self, address):
        self.q = multiprocessing.Queue(1)
        self.use_buffer = True
        self.buffer = []
        self.polynomial = None
        self.speed = 25

        self.speed_addition = 1
        self.address = address 
        self.encoding_tool = "pyav"
        self.top = 200

    def write(self) -> None:
        # p = psutil.Process()
        # p.cpu_affinity([4])
        print('Process to write: %s' % os.getpid())
        last = np.zeros(0,dtype=np.uint8)
        buffer = []
        event1 = threading.Event()

        def running_av():
            nonlocal buffer, last, t2, event1
            container = av.open(self.address, mode = 'r', options = {'rtsp_transport':'tcp'})
            container.streams.video[0].thread_type = 'AUTO' #多线程解码
            self.speed = container.streams.video[0].average_rate
            while True:
                for frame in container.decode(video=0):
                    if t2.is_alive():
                        buffer.append(frame.to_ndarray(format='bgr24'))
                    else:
                        last = frame.to_ndarray(format='bgr24')
                        event1.set()

        def running_cv():
            nonlocal buffer, last, t2, event1
            cap = cv2.VideoCapture(self.address)
            while True:
                success, new_fream = cap.read()
                if success:
                    if t2.is_alive():
                        buffer.append(new_fream)
                    else:
                        last = new_fream
                        event1.set()

        def pts_speed_func():   # 计算函数控制缓存图片量与播放速度之间的映射关系，若视频源足够稳定，则播放速度将稳定在真实值
            x = np.array([-self.top/4, 0, self.top/2, self.top, 3*self.top/2, 2*self.top, 9*self.top/4])
            y = np.array([-2*self.speed, 0, self.speed, self.speed+self.speed_addition, self.speed, 0, -2*self.speed])
            z = np.polyfit(x, y, 6)
            self.polynomial = np.poly1d(z.astype(np.float32))
            
        def sleep_time(long):   # 调用控制播放速度的函数获得到下一帧的间隔时间
            return 1/self.polynomial(long)

            # a = self.polynomial(long)     # 如果想观察缓存区图片数量与播放速度的关系，请启用这四行
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
                            if len(buffer) > self.top:
                                del buffer[0:-self.top+1]

                                self.speed_addition = self.speed_addition + 1
                                pts_speed_func()    # 当缓冲区不足以存放所有图片时，说明函数对应的最高速率不正确，所以增加速率最大值后重置速率函数
                            
                            time.sleep(sleep_time(len(buffer)))
                        except:
                            continue
                time.sleep(1)

        t2=threading.Thread(target=cache_last)
        if self.use_buffer:
            t2.start()

        if self.encoding_tool == "pyav":
            t1=threading.Thread(target=running_av)
        elif self.encoding_tool == "opencv":
            t1=threading.Thread(target=running_cv)
        else:
            print("no such encoding tool")
        t1.start()
        
        while True:
            event1.wait()
            self.q.put(last)
            event1.clear()

    def read(self) -> None: 

        return self.q.get() 

    def run(self):
        pw = multiprocessing.Process(target=self.write)
        pw.start()


if __name__ == '__main__':
    ca = Cache_frame("http://ivi.bupt.edu.cn/hls/cctv1hd.m3u8")
    # ca.encoding_tool = "opencv"

    # self.speed_addition = 25
    # ca.use_buffer = False
    ca.address = "rtsp://sd:admin12345@27.154.228.158:554/h264/ch41/main/av_stream"  # 海康摄像机地址格式

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
