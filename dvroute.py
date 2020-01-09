import socket
import sys
import time
import threading
import copy

""" thread that will call a function every interval seconds """
class RepeatTimer(threading.Thread):

    def __init__(self, interval, target):
        threading.Thread.__init__(self)
        self.target = target
        self.interval = interval
        self.daemon = True
        self.__flag = threading.Event()  
        self.__flag.set()  # True
        self.__running = threading.Event()  
        self.__running.set()  # running--True

    def run(self):
        while self.__running.isSet():
            self.__flag.wait()  # # True--return, False--blocking until True
            self.target()
            time.sleep(self.interval)

    def pause(self):
        self.__flag.clear()  # False--set blocking

    def resume(self):
        self.__flag.set()  # True--stop blocking

    def stop(self):
        self.__flag.set()  
        self.__running.clear()  # False


''' getting the program parameters '''
def parse_argv():
    # Get the parameter list
    s = sys.argv[1:]
    length = len(s)
    # Incomplete information
    if length <= 0 or (length - 1) % 3 != 0:
        print("error: parameters must be :"
              "python dvroute.py <listening-port> <ip-address1 port1 distance1> <ip-address2 port2 distance2> ……")
        return False

    parsed1 = {}  
    port = s.pop(0)
    # Get the listening port number
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


""" recalculate inter-node path costs using bellman ford algorithm """
def update_costs(data, addr):
    # Gets the distance from the adjacent router
    dis = neighbors[addr][0]
    # Traverse the route table received
    for address in data.keys():
        if address == host_addr:
            # we don't need to update the distance to ourselves
            continue
        else:
            # iterate through neighbors and find cheapest route
            if address not in routing.keys():
                # If a node listed in costs is not in our list of nodes
                # join the routing table
                routing[address] = [dis + data[address][0], addr]
            else:
                if routing[address][1] == addr:
                    # The next hop is 'addr'
                    # update route table
                    routing[address][0] = dis + data[address][0]
                else:
                    # To the destination network 'address', but the next hop address is not 'addr'
                    if data[address][0] + dis < routing[address][0]:
                        # 'addr' is a closer link
                        # update route table 
                        routing[address] = [data[address][0] + dis, addr]
        if routing[address][0] == float('inf'):
            routing[address][1] = None

''' Receive routing information'''
def recv_costs():
    while True:
        try:
            data, addr = skt.recvfrom(4096)
            data = eval(data.decode('utf-8'))
            if isinstance(data, dict):
                # DICTIONARY is receved
				# it is routing information
				# update route table
                if addr not in neighbors.keys():
                    # Do not process messages from routers not a neighbor
					# (consider link disconnection)
                    continue
                for ad in data.keys():
                    # set float'inf'
                    if data[ad][0] == 99999:
                        data[ad][0] = float('inf')                
				
				# update route table
                update_costs(data, addr)
                # update the updated-time of the neighbers
                neighbors[addr][1] = time.time()
            else:
                # LIST is receved
				# it is a command
				# call to the modify link function
                r_cmd = data[0]
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


''' Send routing information '''
'''
def send_costs():
    for address in neighbors.keys():
        # Dictionary -> byte stream
        skt.sendto(str(routing).encode('utf-8'), address)
'''
def send_costs():
    for address in neighbors.keys():
        # Copy
        routing_poison_reverse = copy.deepcopy(routing)
            #Set the routing table to unreachable for routing items obtained from adjacent routers        for ad in routing_poison_reverse.keys():
            if routing_poison_reverse[ad][1] == address or routing_poison_reverse[ad][0] == float('inf'):
                # This routing item is obtained from the adjacent router
                # Or this route is not accessible
                # Float 'inf' converted to STR 'inf' cannot be converted back to float'inf' 
                routing_poison_reverse[ad][0] = 99999
				# so it is replaced by a large number.                routing_poison_reverse[ad][0] = 99999
        # Dictionary -> byte stream
        skt.sendto(str(routing_poison_reverse).encode('utf-8'), address)



''' Check the update time of your neighbor's router every THREE seconds '''
def check_neighbors():
    while True:
        # The present time
        now_time = time.time()
        # Traverse the adjacent router table
        for address in list(neighbors.keys()):
            if now_time - neighbors[address][1] > 6 * Interval:
                # The last update of a router was too long
                # removes it from the adjacent router table
                neighbors.pop(address)
                # Traverse
                for add in list(routing.keys()):
                    # 'Address is the next hop address of a destination network in the routing table
                    # the routing item needs to be removed
                    if routing[add][1] == address:
                        routing.pop(add)
        # sleep
        time.sleep(3)


''' disconnect the link'''
def linkdown(parsed):
    # split by the blank
    parsed = parsed.split()
    length = len(parsed)
    # incompleted information
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
            # If the next hop address of a destination network in the routing table is ad_temp
            # remove
            if routing[address][1] == ad_temp:
                routing[address] = [float('inf'), None]

        print("{0} has been removed from neighbors.".format(ad_temp))
        return ["linkdown", str(host_addr[0]) + ' ' + str(host_addr[1]), ad_temp]
    else:
        # no operation addresses in the adjacent router table
        print("there is no {0} in neighbors.".format(ad_temp))
        return False


''' change the link '''
def linkchange(parsed):
    parsed = parsed.split()
    length = len(parsed)
    # incompleted information
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
        # comparison
        # change the routing table if the next hop address of the original routing path is ad_temp
        if routing[ad_temp][1] == ad_temp:
            # Modify the routing table dictionary, {destination address: [distance, next hop address]}
            routing[ad_temp] = [distance, ad_temp]
        elif routing[ad_temp][0] >= distance:
            # Compare the distance if the next hop address of the original routing path is not ad_temp (that is, arrive indirectly)
			# update if the distance is smaller
            # {destination address: [distance, next hop address]}
            routing[ad_temp] = [distance, ad_temp]
        print("the cost of {0} has been changed.".format(ad_temp))
        return ["linkchange", str(host_addr[0]) + ' ' + str(host_addr[1]) + ' ' + str(distance), ad_temp]
    else:
        print("there is no {0} in neighbors.".format(ad_temp))
        return False


''' the new link '''
def linkup(parsed):
    parsed = parsed.split()
    length = len(parsed)
    # incompleted information
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
            # no ad_temp
            routing[ad_temp] = [distance, ad_temp]
        else:
            # Compare and update if the distance is smaller
            if routing[ad_temp][0] >= distance:
                # {destination address: [distance, next hop address]}
                routing[ad_temp] = [distance, ad_temp]
        print("{0} has been set up.".format(ad_temp))
        return ["linkup", str(host_addr[0]) + ' ' + str(host_addr[1]) + ' ' + str(distance), ad_temp]


""" display routing info: cost to destination; route to take """
def showrt():
    print(formatted_now())
    print("Distance vector list is:")
    print("+----------------------+-------+----------------------+")
    print("|     Destination      |  Cost |         Link         |")
    print("+----------------------+-------+----------------------+")

    for address in routing.keys():
        print ("|{destination:^22}|{cost:^7}|{nexthop:^22}|".format(
            destination=str(address),
            cost=routing[address][0],
            next=str(routing[address][1])))
    print("+----------------------+-------+----------------------+") # extra line

if __name__ == '__main__':
    # Verify that parameters are correct
    parsed = parse_argv()
    if parsed == False:
        sys.exit(1)
    # print(parsed)

    # Different programs have different localhost, which needs to be manually modified within the program
	# 不同的程序对应的localhost不同，需要在程序内手动修改
    localhost = '127.0.0.1'
    # time between two transmissions, interval
    Interval = 30
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host_addr = (localhost, parsed['port'])
    skt.bind(host_addr)
    # skt.setblocking(True)
    print('UDP Server on %s:%s...' % (host_addr[0], host_addr[1]))

    # Adjacent router: {adjacent router address: [distance, last update time]}
    neighbors = {}
    for i in range(len(parsed['neighbors'])):
        neighbors[parsed['neighbors'][i]] = [parsed['costs'][i], time.time()]  # + timeout * 3

    # Routing table dictionary, {destination address: [distance, next hop address]}
    routing = {host_addr: [0, host_addr]}
	
    for i in range(len(parsed['neighbors'])):
        # Routing table dictionary, {destination address: [distance, next hop address]}
        routing[parsed['neighbors'][i]] = [parsed['costs'][i], parsed['neighbors'][i]]
    # print(routing)

    # Send routing table information regularly
    ts = RepeatTimer(interval=Interval, target=send_costs)
    # Receive routing table information regularly
    tr = threading.Thread(target=recv_costs, daemon=True)  # 守护线程，当主线程结束时，停止接收子线程
    # Print routing table information regularly
    t_showrt = RepeatTimer(interval=Interval, target=showrt)
    # Periodically check routing table information
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
            # Pause printing routing information
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
                # Send it to another router and change the routing table of the other party
                skt.sendto(str([cmd, ad_other[1]]).encode('utf-8'), ad_other[2])
            # Restore printing routing information
            t_showrt.stopped = False
            t_showrt.resume()
        if cmd == 'close':
            break
    skt.close()
