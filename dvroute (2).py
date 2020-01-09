import socket
import sys
import time
import threading
import copy


class RepeatTimer(threading.Thread):
    """
   thread that will call a function every interval seconds
   """

    def __init__(self, interval, target):
        threading.Thread.__init__(self)
        self.target = target
        self.interval = interval
        self.daemon = True
        self.__flag = threading.Event()  # 用于暂停线程的标识
        self.__flag.set()  # 设置为True
        self.__running = threading.Event()  # 用于停止线程的标识
        self.__running.set()  # 将running设置为True

    def run(self):
        while self.__running.isSet():
            self.__flag.wait()  # 为True时立即返回, 为False时阻塞直到内部的标识位为True后返回
            self.target()
            time.sleep(self.interval)

    def pause(self):
        self.__flag.clear()  # 设置为False, 让线程阻塞

    def resume(self):
        self.__flag.set()  # 设置为True, 让线程停止阻塞

    def stop(self):
        self.__flag.set()  # 将线程从暂停状态恢复, 如何已经暂停的话
        self.__running.clear()  # 设置为False


# 获取程序运行参数
def parse_argv():
    # 获得参数列表
    s = sys.argv[1:]
    length = len(s)
    # 没有参数没有端口或邻居信息不完整
    if length <= 0 or (length - 1) % 3 != 0:
        print("error: parameters must be :"
              "python dvroute.py <listening-port> <ip-address1 port1 distance1> <ip-address2 port2 distance2> ……")
        return False

    parsed1 = {}  # 字典
    port = s.pop(0)
    # 获得监听端口号
    try:
        parsed1['port'] = int(port)
    except ValueError:
        print("error: port values must be integers. {0} is not an int.".format(port))
        return False

    # {'port': xxx, 'neighbors':[addr1,addr2,addr3],  'costs':[cost1,cost2,cost3]}
    parsed1['neighbors'] = []
    parsed1['costs'] = []
    while len(s):
        ip = s.pop(0)
        port = s.pop(0)
        try:
            port = int(port)
            parsed1['neighbors'].append((ip, port))
        except ValueError:
            print("error: port values must be integers. {0} is not an int.".format(port))
            return False
        distance = s.pop(0)
        try:
            distance = float(distance)
            parsed1['costs'].append(distance)
        except ValueError:
            print("error: link distance values must be numbers. {0} is not a number.".format(distance))
            return False
    return parsed1


# 接收到路由信息后，更新路由表
def update_costs(data, addr):
    # 获得与相邻路由器的距离
    dis = neighbors[addr][0]
    # 遍历接收到的路由表
    for address in data.keys():
        if address == host_addr:
            # 如果该路由项的目的地址是自己（一定存在这样的一项，否则不可能接收到路由信息）
            # 则忽略该路由项
            continue
        else:
            # 更新其他路由距离
            if address not in routing.keys():
                # 原来的路由表中没有目的网络address
                # 则计算距离加入路由表
                routing[address] = [dis + data[address][0], addr]
            else:
                if routing[address][1] == addr:
                    # 下一跳地址是addr
                    # 则计算距离更新路由表
                    routing[address][0] = dis + data[address][0]
                else:
                    # 到目的网络address,但下一跳地址不是addr
                    if data[address][0] + dis < routing[address][0]:
                        # 下一跳跳转addr是距离更近的一条链路
                        # 则计算距离更新路由表
                        routing[address] = [data[address][0] + dis, addr]
        # if routing[address][0] == float('inf'):
        #    routing[address][1] = None

		
# 接收路由信息
def recv_costs():
    while True:
        try:
            data, addr = skt.recvfrom(4096)
            data = eval(data.decode('utf-8'))
            if isinstance(data, dict):
                # 接收到的是字典，是路由信息，需要更新路由表
                if addr not in neighbors.keys():
                    # 对于不在邻居列表中的路由器发来的消息不做处理（考虑链路被断开情况）
                    continue
                # for ad in data.keys():
                    # 将极大数转换回float'inf'
                    # if data[ad][0] == 99999:
                        # data[ad][0] = float('inf')					
					
                # 调用更新函数，更新路由表
                update_costs(data, addr)
                # 更新 相邻路由器表 的 最后更新时间
                neighbors[addr][1] = time.time()
            else:
                # 接收到的是列表，是命令，调用修改链路函数
                # 命令
                r_cmd = data[0]
                # 命令参数
                r_parsed = data[1]
                if r_cmd == 'linkdown':
                    linkdown(r_parsed)
                elif r_cmd == 'linkup':
                    linkup(r_parsed)
                else:
                    linkchange(r_parsed)
        except ConnectionError:
            # print(skt.gettimeout())
            # print("远程主机强迫关闭了一个现有的连接。")
            pass


# 发送路由信息
def send_costs():
    for address in neighbors.keys():
        # 字典转换为字节流
        skt.sendto(str(routing).encode('utf-8'), address)
        # print("发送给", address)
        # print(routing)

		
		
		
		
		
		
		
		
		

# 每三秒钟检查一次邻居路由器的更新时间
def check_neighbors():
    while True:
        # 获得现在的时间
        now_time = time.time()
        # 遍历相邻路由器表
        for address in list(neighbors.keys()):
            if now_time - neighbors[address][1] > 6 * Interval:
                # 某一个路由器的上次更新时间 距现在的时间 比较远
                # 则从相邻路由器表中删除这一项
                neighbors.pop(address)
                # 遍历路由表
                for add in list(routing.keys()):
                    # 如果路由表中的某一目的网络的下一跳地址就是address
                    # 则需要删除该路由项
                    if routing[add][1] == address:
                        routing.pop(add)
        # 休眠三秒
        time.sleep(3)


# 链路断开
def linkdown(parsed):
    # 用空格分隔开几个参数
    parsed = parsed.split()
    length = len(parsed)
    # 没有参数没有端口或邻居信息不完整
    if length != 2:
        print("error: parameters must be :<neighbor-ip> <port> ")
        return False

    ip = parsed[0]
    port = parsed[1]
    try:
        port = int(port)
    except ValueError:
        print("error: port values must be integers. {0} is not an int.".format(port))
        return False

    ad_temp = (ip, port)
    if ad_temp in neighbors.keys():
        neighbors.pop(ad_temp)
        for address in list(routing.keys()):
            # 如果路由表中的某一目的网络的下一跳地址就是ad_temp
            # 则需要删除该路由项
            if routing[address][1] == ad_temp:
                routing.pop(address)#routing[address] = [float('inf'), None]
        print("{0} has been removed from neighbors.".format(ad_temp))
        return ["linkdown", str(host_addr[0]) + ' ' + str(host_addr[1]), ad_temp]
    else:
        # 相邻路由器表中没有操作地址
        print("there is no {0} in neighbors.".format(ad_temp))
        return False


# 链路改变
def linkchange(parsed):
    parsed = parsed.split()
    length = len(parsed)
    # 没有参数没有端口或邻居信息不完整
    if length != 3:
        print("error: parameters must be :<neighbor-ip> <port> <link-cost> ")
        return False

    ip = parsed[0]
    port = parsed[1]
    distance = parsed[2]
    try:
        port = int(port)
    except ValueError:
        print("error: port values must be integers. {0} is not an int.".format(port))
        return False
    try:
        distance = float(distance)
    except ValueError:
        print("error: link distance values must be numbers. {0} is not a number.".format(distance))
        return False

    ad_temp = (ip, port)
    if ad_temp in neighbors.keys():
        neighbors[ad_temp] = [distance, time.time()]
        # 作比较，若原来路由路径的下一跳地址就是ad_temp（即直接到达），则修改路由表
        if routing[ad_temp][1] == ad_temp:
            # 修改路由表字典，{ 目标地址：[距离，下一跳地址]}
            routing[ad_temp] = [distance, ad_temp]
        elif routing[ad_temp][0] >= distance:
            # 若原来路由路径的下一跳地址不是ad_temp（即间接到达），则比较距离，若距离更小则更新
            # 修改路由表字典，{ 目标地址：[距离，下一跳地址]}
            routing[ad_temp] = [distance, ad_temp]
        print("the cost of {0} has been changed.".format(ad_temp))
        return ["linkchange", str(host_addr[0]) + ' ' + str(host_addr[1]) + ' ' + str(distance), ad_temp]
    else:
        print("there is no {0} in neighbors.".format(ad_temp))
        return False


# 链路新建
def linkup(parsed):
    parsed = parsed.split()
    length = len(parsed)
    # 没有参数没有端口或邻居信息不完整
    if length != 3:
        print("error: parameters must be :<neighbor-ip> <port> <link-cost>")
        return False

    ip = parsed[0]
    port = parsed[1]
    distance = parsed[2]
    try:
        port = int(port)
    except ValueError:
        print("error: port values must be integers. {0} is not an int.".format(port))
        return False
    try:
        distance = float(distance)
    except ValueError:
        print("error: link distance values must be numbers. {0} is not a number.".format(distance))
        return False

    ad_temp = (ip, port)
    if ad_temp in neighbors.keys():
        print("{0} has been in neighbors.".format(ad_temp))
        return False
    else:
        neighbors[ad_temp] = [distance, time.time()]
        if ad_temp not in routing.keys():
            # 原本路由表中没有ad_temp
            routing[ad_temp] = [distance, ad_temp]
        else:
            # 比较距离，若距离更小则更新
            if routing[ad_temp][0] >= distance:
                # 修改路由表字典，{ 目标地址：[距离，下一跳地址]}
                routing[ad_temp] = [distance, ad_temp]
        print("{0} has been set up.".format(ad_temp))
        return ["linkup", str(host_addr[0]) + ' ' + str(host_addr[1]) + ' ' + str(distance), ad_temp]


# 打印路由信息
def showrt():
    print("+----------------------------+-------+----------------------------+")
    print("|          目的地址          |  距离 |          下一跳地址         |")
    print("+----------------------------+-------+----------------------------+")
    # 遍历路由表，格式化输出
    for address in routing.keys():
        print("|{destination:^28}|{cost:^7}|{next:^28}|".format(
            destination=str(address),
            cost=routing[address][0],
            next=str(routing[address][1])))
    print("+----------------------------+-------+----------------------------+")
    # for address in neighbors.keys():
    #     print(address, "\t", neighbors[address][0], "\t", neighbors[address][1])


if __name__ == '__main__':
    # 确认参数正确
    parsed = parse_argv()
    if parsed == False:
        sys.exit(1)
    # print(parsed)

    # 不同的程序对应的localhost不同，需要在程序内手动修改
    localhost = '127.0.0.1'
    # 间隔时间
    Interval = 30
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host_addr = (localhost, parsed['port'])
    skt.bind(host_addr)
    # skt.setblocking(True)
    print('UDP Server on %s:%s...' % (host_addr[0], host_addr[1]))

    # 相邻路由器，{ 相邻路由器地址：[距离，最近更新时间] }
    neighbors = {}
    for i in range(len(parsed['neighbors'])):
        neighbors[parsed['neighbors'][i]] = [parsed['costs'][i], time.time()]  # + timeout * 3

    # 路由表字典，{ 目标地址：[距离，下一跳地址]}
    routing = {host_addr: [0, host_addr]}
    # routing = {}
    for i in range(len(parsed['neighbors'])):
        # 路由表字典，{ 目标地址：[距离，下一跳地址]}
        routing[parsed['neighbors'][i]] = [parsed['costs'][i], parsed['neighbors'][i]]
    # print(routing)

    # 定时发送路由表信息
    ts = RepeatTimer(interval=Interval, target=send_costs)
    # 时刻接收路由表信息
    tr = threading.Thread(target=recv_costs, daemon=True)  # 守护线程，当主线程结束时，停止接收子线程
    # 定时打印路由表信息
    t_showrt = RepeatTimer(interval=Interval, target=showrt)
    # 定时检查路由表信息
    t_check = threading.Thread(target=check_neighbors, daemon=True)  # 守护线程，当主线程结束时，停止检查
    ts.start()
    tr.start()
    t_showrt.start()
    t_check.start()

    cmds = ('linkdown', 'linkup', 'linkchange')
    while True:
        cmd = input()
        # print(cmd)
        if cmd in cmds:
            # 暂停打印路由信息
            t_showrt.pause()
            if cmd == 'linkdown':
                parsed = input("link down : ")
                ad_other = linkdown(parsed)
            elif cmd == 'linkup':
                parsed = input("link up : ")
                ad_other = linkup(parsed)
            else:
                parsed = input("link change : ")
                ad_other = linkchange(parsed)
            if ad_other != False:
                # 发送给另一个路由器，改变另一方的路由表
                skt.sendto(str([cmd, ad_other[1]]).encode('utf-8'), ad_other[2])
            # 恢复打印路由信息
            t_showrt.stopped = False
            t_showrt.resume()
        if cmd == 'close':
            break
    skt.close()
