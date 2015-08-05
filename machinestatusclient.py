import zmq
import sys

from message_pb2 import Container
from config_pb2 import *
from types_pb2 import *

class MachineStatusClient:
    def __init__(self, context, statusUri):
        self.context = context
        self.statusUri = statusUri

        self.rx = Container()
        self.tx = Container()

        print(("connecting to '%s'" % self.statusUri))
        self.socket = context.socket(zmq.SUB)
        self.socket.connect(self.statusUri)
        self.socket.setsockopt(zmq.SUBSCRIBE, "task")

        self.commandSocket = context.socket(zmq.DEALER)
        self.commandSocket.connect(self.statusUri)

        self.send_command_msg(MT_PING)

        print("Connected")

        self.run()

    def send_command_msg(self, type):
        self.tx.type = type
        txBuffer = self.tx.SerializeToString()
        self.tx.Clear()
        self.commandSocket.send(txBuffer)

    def run(self):
        while True:
            try:
                (topic, message) = self.socket.recv_multipart()
                if topic == "task":
                    self.handleTopicTask(message)
                else:
                    print("Unrecognized topic: %s" % topic)
            except zmq.Again:
                pass

    def handleTopicTask(self, message):
        self.rx.ParseFromString(message)
        messageType = self.rx.type
        if messageType == MT_PING:
            self.handleTaskPing(self.rx)
        elif messageType == MT_EMCSTAT_FULL_UPDATE:
            self.handleTaskEmcStatFullUpdate(self.rx)
        else:
            print("Unrecognized message type: %s" % str(self.rx))

    def handleTaskPing(self, message):
        print "Ping received"
        self.send_command_msg(MT_PING_ACKNOWLEDGE)

    def handleTaskEmcStatFullUpdate(self, message):
        print "Full update received"

