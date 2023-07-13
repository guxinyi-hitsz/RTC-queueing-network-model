from random import random

import numpy as np
from simpy import Store

"""
    A detailed set of components to use in packet switching queueing experiments.
    Copyright 2014 Greg M. Bernstein
    https://www.grotto-networking.com/DiscreteEventPython.html
"""


class Job(object):
    '''
    A very simple class that represent a job.
    This job will run through a queue to a switch output port.
    We use a float to represent the size of the job in bytes so that
    we can compare to ideal M/M/1 queues.

    Parameter
    ---------
    time: float
        the time the job arrives at the output queue.
    size: float
        the size of the job in bytes
    id: int
        an identifier for the job
    src, dst: int
        identifiers for source and destination
    flowid: int
        a integer that identify a flow
    '''

    def __init__(self, time, size, id, src="a", dst="z", flowid=0):
        self.time = time
        self.size = size
        self.id = id
        self.src = src
        self.dst = dst
        self.flowid = flowid

    def __repr__(self):
        return "id: {}, flow: {}, time:{}, size:{}". \
            format(self.id, self.flowid, self.time, self.size)


class JobGenerator(object):
    '''
    Generates packets with given inter-arrival time distribution.
    Set the "out" member variable to the entity to receive the packet.

    Parameter:
    ----------
    sim: simpy.Environment
        the simulation environment
    uid: integer
        a integer that indentify a JobGenerator
    flowid: integer
        a integer that indentify a flow
    adist: function
        a no parameter function that returns the successive inter-arrival times of the packets
    sdist: function
        a no parameter function that returns the successive size of the packets
    initial_delay: number
        starts generation after an initial delay. Default = 0
    lifetime: number
        stops generation at the end of lifetime. Default is infinite
    '''

    def __init__(self, sim, id, adist, sdist, initial_delay=0, lifetime=float("inf"), flowid=0):
        self.sim = sim
        self.id = id
        self.flowid = flowid
        self.adist = adist
        self.sdist = sdist
        self.initial_delay = initial_delay
        self.lifetime = lifetime
        self.out = None
        self.sent = 0  # record the total number of generated jobs
        self.action = sim.process(self.run())  # start the run() method as a SimPy process

    def run(self):
        yield self.sim.timeout(self.initial_delay)
        while self.sim.now < self.lifetime:
            yield self.sim.timeout(self.adist())
            self.sent += 1
            job = Job(self.sim.now, self.sdist(), self.sent, src=self.id, flowid=self.flowid)
            self.out.put(job)


class JobSink(object):
    '''
    Receives jobs and collects delay information into the waits list. You can use this list
    to do delay statistics.

    Parameters
    ----------
    sim:simpy.Environment
        the simulation environment
    record_arrivals: boolean
        if true then arrivals will be recorded
    absolute_time:boolean
        if true then absolute arrival times will be recorded,
        otherwise the times between consecutive arrivals is recorded.
    record_waits: boolean
        if true then the waiting time experienced by each job is recorded.
    debug:boolean
        if true then the contents of each packet will be printed as it is received.
    selector: a function that takes a packet and returns a boolean
        used for selective statistics. Default none.
    '''

    def __init__(self, sim, record_arrivals=False, absolute_time=False, record_waits=True, debug=False,
                 selector=None):
        self.sim = sim
        self.store = Store(sim)
        self.rec_arrivals = record_arrivals
        self.absolute_time = absolute_time
        self.arrivals = []
        self.rec_waits = record_waits
        self.waits = []
        self.debug = debug
        self.selector = selector
        self.jobs_rec = 0
        self.bytes_rec = 0
        self.last_arrival = 0.0

    def put(self, job):
        if not self.selector or self.selector(job):
            now = self.sim.now
            if self.rec_waits:
                self.waits.append(now - job.time)
            if self.rec_arrivals:
                if self.absolute_time:
                    self.arrivals.append(now)
                else:
                    self.arrivals.append(now - self.last_arrival)

                self.last_arrival = now

            self.jobs_rec += 1
            self.bytes_rec += job.size
            if self.debug:
                print(job)


class SwitchPort(object):
    '''
    Models a switch output port with a set of Differentiated Services Rate and
    buffer size limit in bytes/jobs.

    Parameters
    ----------
    sim:simpy.Environment
        the simulation environment
    rate:list
        the service rate of the port with different classes of jobs
    qlimit:integer(or None)
        a buffer size limit in bytes or jobs for the queue(including jobs in service).
    limit_bytes:bool
        if True, the queue limit will be based on bytes.
        if False, the queue limit will be based on jobs.
    '''

    def __init__(self, sim, rate, flowids=None, qlimit=None, limit_bytes=True):
        self.sim = sim
        assert (type(rate) is list)
        self.full_rate = rate
        self.num_flow = len(rate)
        self.flow = {flowids[i]: i for i in range(self.num_flow)}
        self.flowids = flowids
        self.queue = [Store(sim) for i in range(self.num_flow)]
        self.qlmit = qlimit
        self.limit_bytes = limit_bytes
        self.busy = 0  # a flag to track if a packet is currently being sent
        self.qsize = np.zeros(self.num_flow, dtype=np.int)  # current size of the queue in bytes/packets
        self.out = None  # set the "out" to the entity to receive the packet
        self.weight = np.ones(self.num_flow) / self.num_flow  # effort to process different classes of jobs
        self.probs = [sum(self.weight[0:i + 1]) for i in self.num_flow]  # cdf
        self.action = sim.process(self.run())  # start the run() method as a SimPy process
        self.drop = 0

    def _rate(self, flowid):
        assert (flowid in self.flow)
        i = self.flow[flowid]
        return self.full_rate[i]

    def _queue(self, flowid):
        assert (flowid in self.flow)
        i = self.flow[flowid]
        return self.queue[i]

    def control(self, weight):
        assert (weight.shape[0] == self.num_flow)
        assert (weight.sum() <= 1)
        self.weight = weight
        self.probs = [sum(self.weight[0:i + 1]) for i in self.num_flow]

    def run(self):
        while True:
            rand = random()
            flowid = 0
            for i in range(self.num_flow):
                if rand < self.probs[i]:
                    flowid = self.flowids[i]
            job = (yield self._queue(flowid).get())
            if self.limit_bytes:
                self.qsize[self.flow[flowid]] -= job.size
            else:
                self.qsize[self.flow[flowid]] -= 1
            self.busy = 1
            yield self.sim.timeout(job.size / self._rate(flowid))
            self.out.put(job)
            self.busy = 0

    def put(self, job):
        if self.qlimit is None:
            flowid = job.flowid
            if self.limit_bytes:
                self.qsize[self.flow[flowid]] += job.size
            else:
                self.qsize[self.flow[flowid]] += 1
            return self._queue(flowid).put(job)
        if self.limit_bytes and self.qsize.sum() + job.size >= self.qlimit:
            self.drop += 1
            return
        elif not self.limit_bytes and self.qsize.sum() + 1 >= self.qlimit:
            self.drop += 1
            return
        else:
            flowid = job.flowid
            if self.limit_bytes:
                self.qsize[self.flow[flowid]] += job.size
            else:
                self.qsize[self.flow[flowid]] += 1
            return self._queue(flowid).put(job)

    def state(self):
        return {self.flowids[i]: self.qsize[i] for i in range(self.num_flow)}


class PortMonitor(object):
    '''
    A monitor for an SwitchPort. Looks at the number of jobs in the SwitchPort
    in service or in the queue and records that time average size. The monitor
    looks at the port at time intervals given by the distribution dist.

    Parameters
    ----------
    sim: simpy.Environment
        the simulation environment
    port: SwitchPort
        the switch port object to be monitored
    dist: function
        a no parameter function that returns the successive inter-arrival times
    count_bytes:bool
            if True, the size will be based on bytes.
            if False, the size will be based on jobs.
    '''

    def __init__(self, sim, port, dist, count_bytes=False):
        self.port = port
        self.sim = sim
        self.dist = dist
        self.count_bytes = port.limit_bytes
        self.average_size = 0
        self.sample_num = 0
        self.history = []
        self.action = sim.process(self.run())
        self.step_ends = sim.event()

    def run(self):
        while True:
            yield self.sim.timeout(self.dist())
            new_size = 0
            if self.count_bytes:
                new_size = self.port.qsize().sum()
            else:
                new_size = self.port.qsize().sum() + self.port.busy
            self.average_size = (self.average_size * self.sample_num + new_size) / (self.sample_num + 1)
            self.sample_num += 1
            self.history.append(self.average_size)

            self.step_ends.succeed()
            self.step_ends = self.sim.event()


class FlowDemux(object):
    '''
    A demultiplexing element that splits packet streams by flowid.
    Parameters
    ----------
    flowids:list
        list of flowid
    outs:list
        list of the corresponding output ports
    upgrades:list
        list of the flowid that needs to upgrade, the output job flowid will plus one.
    '''

    def __init__(self, flowids=None, outs=None, upgrades=None, default=None):
        assert (type(flowids) is list)
        self.flowids = flowids
        self.n_outs = len(flowids)
        assert (len(outs) == self.n_outs)
        self.outs = {flowids[i]: outs[i] for i in range(self.n_outs)}
        assert (len(upgrades) == self.n_outs)
        self.upgrades = {flowids[i]: upgrades[i] for i in range(self.n_outs)}
        self.default = default
        self.drop = 0

    def put(self, job):
        flowid = job.flowid
        if flowid not in self.flowids:
            if self.default:
                self.default.put(job)
            else:
                self.drop += 1
        else:
            if self.upgrades[flowid] > 0:
                job.flowid = self.upgrades[flowid]  # upgrade if need
            self.outs[flowid].put(job)
