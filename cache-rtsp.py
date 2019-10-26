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
    设定地址于self.address\n
    可选择"pyav"或"opencv"解码在self.encoding_tool
    """
    def __init__(self):
        self.address = "http://ivi.bupt.edu.cn/hls/cctv1hd.m3u8"    # 
        self.encoding_tool = "pyav"
        self.last_frame = None
        self.top = 1
        self.q = multiprocessing.Queue(1)

    def write(self) -> None:
        # p = psutil.Process()
        # p.cpu_affinity([4])
        last = np.zeros(0,dtype=np.uint8)
        print('Process to write: %s' % os.getpid())
        event = threading.Event()

        def running_av():
            nonlocal last, event 
            video = av.open(self.address, mode = 'r', options = {'rtsp_transport':'tcp'})
            # video.streams.framerate = Fraction(25)
            video.streams.video[0].thread_type = 'AUTO' #多线程解码
            for frame in video.decode(video=0):

                new_fream = frame.to_ndarray(format='bgr24')
                time.sleep(0.035) # i should make a function to control it
                last = new_fream
                event.set()


        def running_cv():
            nonlocal last, event 
            cap = cv2.VideoCapture(self.address)
            while True:
                success, new_fream = cap.read()
                if success:

                    last = new_fream
                    event.set()

        if self.encoding_tool == "pyav":
            t1=threading.Thread(target=running_av)
        elif self.encoding_tool == "opencv":
            t1=threading.Thread(target=running_cv)
        else:
            print("no such encoding tool")
        t1.start()

        while True:

            event.wait()

            self.q.put(last)

            event.clear()

    def read(self) -> None: 
        # print("开始读取一帧")

        self.last_frame = self.q.get()
        # img = transform.resize(img, (270, 480))
        # img = cv2.resize(img, (0, 0), fx=0.3, fy=0.3)  
        
        return self.last_frame 

    def run(self):
        pw = multiprocessing.Process(target=self.write)
        pw.start()


if __name__ == '__main__':
    ca = Cache_frame()
    # ca.encoding_tool = "opencv"
    # ca.address = "rtsp://admin:admin@192.168.1.110:554/h264/ch40/main/av_stream"  # 海康摄像机地址格式
    t2=threading.Thread(target=ca.run)
    t2.start()

    while True:
        img = ca.read()
        img = cv2.resize(img, (0, 0), fx=0.3, fy=0.3) 
        key = cv2.waitKey(1) & 0xFF
        cv2.imshow("video", img)
        if key == ord('q'):
                break
