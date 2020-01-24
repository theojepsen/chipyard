
import unittest
from scapy.all import *
from LNIC_headers import LNIC
import Throughput_headers as Throughput
import NN_headers as NN
import Othello_headers as Othello
import NBody_headers as NBody
import struct
import pandas as pd
import os
import numpy as np

TEST_IFACE = "tap0"
TIMEOUT_SEC = 3 # seconds

NIC_MAC = "08:11:22:33:44:08"
MY_MAC = "08:55:66:77:88:08"

NIC_IP = "10.0.0.1"
MY_IP = "10.1.2.3"

DST_CONTEXT = 0
MY_CONTEXT = 0x1234

LOG_DIR = '/vagrant/logs'

NUM_SAMPLES = 5

def lnic_req(lnic_dst = DST_CONTEXT):
    return Ether(dst=NIC_MAC, src=MY_MAC) / \
            IP(src=MY_IP, dst=NIC_IP) / \
            LNIC(src=MY_CONTEXT, dst=lnic_dst)

def write_csv(dname, fname, df):
    log_dir = os.path.join(LOG_DIR, dname)
    if not os.path.exists(log_dir):
      os.makedirs(log_dir)
    with open(os.path.join(log_dir, fname), 'w') as f:
        f.write(df.to_csv(index=False))

class Loopback(unittest.TestCase):
    def do_loopback(self, pkt_len):
        msg_len = pkt_len - len(lnic_req()) # bytes
        payload = Raw('\x00'*msg_len)
        req = lnic_req() / payload
        # send request / receive response
        resp = srp1(req, iface=TEST_IFACE, timeout=TIMEOUT_SEC)
        self.assertIsNotNone(resp)
        self.assertEqual(resp[LNIC].dst, MY_CONTEXT)
        resp_data = resp[LNIC].payload
        self.assertEqual(len(resp_data), len(payload))
        latency = struct.unpack('!Q', str(resp_data)[-8:])[0]
        return latency
    def test_single(self):
        pkt_len = 64 # bytes
        latency = self.do_loopback(pkt_len)
        print 'Latency = {} cycles'.format(latency)
    def test_pkt_length(self):
        pkt_len = range(64, 64*20, 64)
        length = []
        latency = []
        for l in pkt_len:
            for i in range(NUM_SAMPLES):
                print 'Testing pkt_len = {} bytes'.format(l)
                length.append(l)
                latency.append(self.do_loopback(l))
        # record latencies
        df = pd.DataFrame({'pkt_len':length, 'latency':latency})
        write_csv('loopback', 'pkt_len_latency.csv', df)

class ThroughputTest(unittest.TestCase):
    def setUp(self):
        bind_layers(LNIC, Throughput.Throughput)

    def start_rx_msg(self, num_msgs):
        return lnic_req() / Throughput.Throughput() / Throughput.StartRx(num_msgs=num_msgs) / Raw('\x00'*8)

    def start_tx_msg(self, num_msgs, msg_size):
        return lnic_req() / Throughput.Throughput() / Throughput.StartTx(num_msgs=num_msgs, msg_size=msg_size) / Raw('\x00'*8)

    def data_msg(self):
        return lnic_req() / Throughput.Throughput(msg_type=Throughput.DATA_TYPE)

    def do_rx_test(self, num_pkts, pkt_len):
        # test RX throughput - how fast can the application receive msgs?
        pkts = []
        pkts += [self.start_rx_msg(num_pkts)]
        for i in range(num_pkts):
            pkts += [self.data_msg() / Raw('\x00'*(pkt_len - len(self.data_msg())))]
        # start sniffing for DONE msg
        sniffer = AsyncSniffer(iface=TEST_IFACE, lfilter=lambda x: x.haslayer(LNIC) and x[LNIC].dst == MY_CONTEXT,
                    count=1, timeout=10)
        sniffer.start()
        # send in pkts
        sendp(pkts, iface=TEST_IFACE)
        # wait for DONE msg
        sniffer.join()
        self.assertEqual(1, len(sniffer.results))
        done_msg = sniffer.results[0]
        total_latency = struct.unpack('!Q', str(done_msg)[-8:])[0]
        throughput = len(pkts)/float(total_latency)
        return throughput # pkts/cycle
    def do_tx_test(self, num_pkts, pkt_len):
        # test TX throughput - how fast can the application generate pkts?
        pkts = []
        msg_len = pkt_len - len(lnic_req())
        pkts += [self.start_tx_msg(num_pkts, msg_len)]
        # start sniffing for generated DATA msgs
        sniffer = AsyncSniffer(iface=TEST_IFACE, lfilter=lambda x: x.haslayer(LNIC) and x[LNIC].dst == MY_CONTEXT,
                    count=num_pkts, timeout=10)
        sniffer.start()
        # send in START msg
        sendp(pkts, iface=TEST_IFACE)
        # wait for all generated DATA msgs
        sniffer.join()
        self.assertEqual(num_pkts, len(sniffer.results))
        final_msg = sniffer.results[-1]
        total_latency = struct.unpack('!Q', str(final_msg)[-8:])[0]
        throughput = num_pkts/float(total_latency)
        return throughput # pkts/cycle
    def test_rx_throughput(self):
        pkt_len = 64 # bytes
        num_pkts = 200
        throughput = self.do_rx_test(num_pkts, pkt_len)
        print 'RX Throughput = {} pkts/cycle ({} bytes/cycle)'.format(throughput, throughput*pkt_len)
    def test_tx_throughput(self):
        pkt_len = 64 # bytes
        num_pkts = 200
        throughput = self.do_tx_test(num_pkts, pkt_len)
        print 'RX Throughput = {} pkts/cycle ({} bytes/cycle)'.format(throughput, throughput*pkt_len)

class Stream(unittest.TestCase):
    def do_loopback(self, pkt_len):
        msg_len = pkt_len - len(lnic_req()) # bytes
        payload = Raw('\x00'*msg_len)
        req = lnic_req() / payload
        # send request / receive response
        resp = srp1(req, iface=TEST_IFACE, timeout=TIMEOUT_SEC)
        self.assertIsNotNone(resp)
        self.assertEqual(resp[LNIC].dst, MY_CONTEXT)
        resp_data = resp[LNIC].payload
        self.assertEqual(len(resp_data), len(payload))
        latency = struct.unpack('!Q', str(resp_data)[-8:])[0]
        return latency
    def test_single(self):
        pkt_len = 64*2 # bytes
        latency = self.do_loopback(pkt_len)
        print 'Latency = {} cycles'.format(latency)
    def test_pkt_length(self):
        pkt_len = range(64, 64*15, 64)
        length = []
        latency = []
        for l in pkt_len:
            for i in range(NUM_SAMPLES):
              print 'Testing pkt_len = {} bytes'.format(l)
              length.append(l)
              latency.append(self.do_loopback(l))
        # record latencies
        df = pd.DataFrame({'pkt_len':length, 'latency':latency})
        write_csv('stream', 'pkt_len_latency.csv', df)

class NNInference(unittest.TestCase):
    def setUp(self):
        bind_layers(LNIC, NN.NN)

    @staticmethod
    def config_msg(num_edges):
        return lnic_req() / NN.NN() / NN.Config(num_edges=num_edges)

    @staticmethod
    def weight_msg(index, weight):
        return lnic_req() / NN.NN() / NN.Weight(index=index, weight=weight)

    @staticmethod
    def data_msg(index, data):
        return lnic_req() / NN.NN() / NN.Data(index=index, data=data)

    def do_test(self, num_edges):
        inputs = []
        inputs.append(NNInference.config_msg(num_edges))
        # weight = 1 for all edges
        inputs += [NNInference.weight_msg(i, 1) for i in range(num_edges)]
        # data = index+1
        inputs += [NNInference.data_msg(i, i+1) for i in range(num_edges)]
        # send inputs get response
        resp = srp1(inputs, iface=TEST_IFACE, timeout=TIMEOUT_SEC)
        # check response
        self.assertIsNotNone(resp)
        self.assertTrue(resp.haslayer(NN.Data))
        self.assertEqual(resp[NN.Data].index, 0)
        self.assertEqual(resp[NN.Data].data, sum([i+1 for i in range(num_edges)]))
        # return latency
        return resp[NN.Data].timestamp

    def test_basic(self):
        latency = self.do_test(3)
        print 'Latency = {} cycles'.format(latency)

    def test_num_edges(self):
        num_edges = range(2, 21)
        edges = []
        latency = []
        for n in num_edges:
            for i in range(NUM_SAMPLES):
                edges.append(n)
                latency.append(self.do_test(n))
        # record latencies
        df = pd.DataFrame({'num_edges':edges, 'latency':latency})
        write_csv('nn', 'num_edges_latency.csv', df)

class OthelloTest(unittest.TestCase):
    def setUp(self):
        bind_layers(LNIC, Othello.Othello)

    @staticmethod
    def map_msg(board, max_depth, cur_depth, src_host_id, src_msg_ptr):
        return lnic_req() / Othello.Othello() / \
                Othello.Map(board=board, max_depth=max_depth, cur_depth=cur_depth, src_host_id=src_host_id, src_msg_ptr=src_msg_ptr)

    @staticmethod
    def reduce_msg(target_host_id, target_msg_ptr, minimax_val):
        return lnic_req() / Othello.Othello() / \
                Othello.Reduce(target_host_id=target_host_id, target_msg_ptr=target_msg_ptr, minimax_val=minimax_val)

    def do_internal_node_test(self, fanout):
        # send in initial map msg and receive outgoing map messages
        parent_id = 10
        parent_msg_ptr = 0x1234
        responses = srp(OthelloTest.map_msg(board=fanout, max_depth=2, cur_depth=1, src_host_id=parent_id, src_msg_ptr=parent_msg_ptr),
                iface=TEST_IFACE, timeout=TIMEOUT_SEC, multi=True)
        # check responses / build reduce msgs
        self.assertEqual(len(responses[0]), fanout)
        reduce_msgs = []
        map_latency = None
        for _, p in responses[0]:
            self.assertTrue(p.haslayer(Othello.Map))
            self.assertEqual(p[Othello.Map].cur_depth, 2)
            reduce_msgs.append(OthelloTest.reduce_msg(
                target_host_id=p[Othello.Map].src_host_id,
                target_msg_ptr=p[Othello.Map].src_msg_ptr,
                minimax_val=1))
            map_latency = p[Othello.Map].timestamp
        # send in reduce messages and receive final reduce msg
        resp = srp1(reduce_msgs, iface=TEST_IFACE, timeout=TIMEOUT_SEC)
        # check reduce msg responses
        self.assertIsNotNone(resp)
        self.assertTrue(resp.haslayer(Othello.Reduce))
        self.assertEqual(resp[Othello.Reduce].target_host_id, parent_id)
        self.assertEqual(resp[Othello.Reduce].target_msg_ptr, parent_msg_ptr)
        self.assertEqual(resp[Othello.Reduce].minimax_val, 1)
        reduce_latency = resp[Othello.Reduce].timestamp
        return map_latency, reduce_latency

    def test_internal_node_basic(self):
        map_latency, reduce_latency = self.do_internal_node_test(3)
        print 'Map Latency = {} cycles'.format(map_latency)
        print 'Reduce Latency = {} cycles'.format(reduce_latency)

    def test_fanout(self):
        fanout_vals = range(2, 10)
        fanout = []
        map_latency = []
        reduce_latency = []
        for n in fanout_vals:
            for i in range(NUM_SAMPLES):
                fanout.append(n)
                mlat, rlat = self.do_internal_node_test(n)
                map_latency.append(mlat)
                reduce_latency.append(rlat)
        # record latencies
        df = pd.DataFrame({'fanout':fanout, 'map_latency':map_latency, 'reduce_latency':reduce_latency})
        write_csv('othello', 'fanout_latency.csv', df)

class NBodyTest(unittest.TestCase):
    G = 667e2
    def setUp(self):
        bind_layers(LNIC, NBody.NBody)

    def config_msg(self, xcom, ycom, num_msgs):
        return lnic_req() / NBody.NBody() / NBody.Config(xcom=xcom, ycom=ycom, num_msgs=num_msgs)

    def traversal_req(self, xpos, ypos):
        return lnic_req() / NBody.NBody() / NBody.TraversalReq(xpos=xpos, ypos=ypos)

    def do_test(self, num_msgs):
        inputs = []
        xcom = 50
        ycom = 50
        xpos = 0
        ypos = 0
        inputs.append(self.config_msg(xcom, ycom, num_msgs))
        # generate traversal req msgs
        inputs += [self.traversal_req(xpos, ypos) for i in range(num_msgs)]
        # start sniffing for responses
        sniffer = AsyncSniffer(iface=TEST_IFACE, lfilter=lambda x: x.haslayer(LNIC) and x[LNIC].dst == MY_CONTEXT,
                    count=1, timeout=10)
        sniffer.start()
        # send inputs get response
        sendp(inputs, iface=TEST_IFACE)
        # wait for all responses
        sniffer.join()
        # check response
        self.assertTrue(len(sniffer.results) > 0)
        resp = sniffer.results[0]
        self.assertTrue(resp.haslayer(NBody.TraversalResp))
        # compute expected force
        dist = np.sqrt((xcom - xpos)**2 + (ycom - ypos)**2)
        expected_force = NBodyTest.G / dist**2
        self.assertAlmostEqual(resp[NBody.TraversalResp].force, expected_force, delta=1)
        # return latency
        return resp[NBody.TraversalResp].timestamp

    def test_basic(self):
        latency = self.do_test(3)
        print 'Latency = {} cycles'.format(latency)

    def test_num_edges(self):
        num_msgs = range(10, 101, 10)
        msgs = []
        latency = []
        for n in num_msgs:
            #for i in range(NUM_SAMPLES):
            msgs.append(n)
            latency.append(self.do_test(n))
        # record latencies
        df = pd.DataFrame({'num_msgs':msgs, 'latency':latency})
        write_csv('nbody', 'num_msgs_latency.csv', df)

class Multithread(unittest.TestCase):
    def test_basic(self):
        pkt_len = 64 # bytes
        msg_len = pkt_len - len(lnic_req()) # bytes
        payload = Raw('\x00'*msg_len)
        sendp(lnic_req(1) / payload, iface=TEST_IFACE)
        sendp(lnic_req(0) / payload, iface=TEST_IFACE)
        self.assertTrue(True)

