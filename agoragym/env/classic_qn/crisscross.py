from functools import partial
from random import expovariate
from typing import Optional
from os import path
from datetime import datetime

import numpy as np
from gym import Env
from simpy import Environment
import tensorflow as tf
from tensorflow import summary
import matplotlib.pyplot as plt
from io import BytesIO

from agoragym.env.component import JobGenerator, SwitchPort, PortMonitor, JobSink, FlowDemux
from agoragym.env.utils import RNG


class CrissCrossEnv(Env):
    '''
    Env Registration: CrissCrossQn-v0

    The Criss-Cross Network is composed of three classes jobs and two servers;
        class 1 and 2 jobs are processed at server 1 and class 3 jobs are processed
    at server 2.
        class 1 jobs arrive at server 1 with a rate of lambda_1, after a class 1 job
    completes service at server 1, it turns into a class 3 job and moves to server 2.
    Once a class 3 job completes service at server2, it exits the system.
        class 2 jobs arrive at server 1 with a rate of lambda_2, after a class 2 job
    completes service at server 1, it exits the system.

        For each class i, we let mu_i be the service rate of these jobs;

    The problem amounts to deciding whether server 1 should process class 1 or 2 jobs.
    Let C_i be the cost per unit time for holding a job of class i in the buffer. The
    goal is to find a control policy so that the total holding cost of the jobs in the
    system is minimized over the time interval [0, T].

    Observation:
        Type: Box
        xi: the total (fractional in general) number of class i jobs at time t, i=1,2,3

    Actions:
        Type: Box
        ui: the effort that the corresponding server spends processing class i jobs at current time. i=1,2
        u1/mu1+u2/mu2<=1, u3/mu3<=1

    Reward:
        Type: Continuous
        the average holding cost of three classes jobs in the system over the past time.

    Stating State:
        no jobs in the system.

    Episode Termination:
        The elapse time unit.
    '''

    def __init__(self, elapse=100, seed=None):
        self.episodes=0
        self.elapse = elapse
        self.Lambda = np.array([1.0, 0.6])
        self.Mu = np.array([2.0, 1.2, 1.0])
        self.time_unit = 5.0
        self._createnv()
        self.seed(seed)

    def _createnv(self):
        # Create simpy environment
        self.sim = Environment()
        self.clock = self.sim.now
        self.episodes += 1

        # Set up distributions
        adist1 = partial(expovariate, 1 / self.Lambda[0])
        adist2 = partial(expovariate, 1 / self.Lambda[1])
        sdist = partial(expovariate, 1.0)

        time_unit = self.time_unit

        def monitor_dist():
            return time_unit

        # Create components
        g1 = JobGenerator(self.sim, "Class1", adist1, sdist, flowid=1)
        g2 = JobGenerator(self.sim, "Class2", adist2, sdist, flowid=2)
        s1 = SwitchPort(self.sim, [self.Mu[0], self.Mu[1]], flowids=[1, 2])
        s2 = SwitchPort(self.sim, [self.Mu[2]], flowids=[3])
        s1_monitor = PortMonitor(self.sim, s1, monitor_dist, count_bytes=False)
        s2_monitor = PortMonitor(self.sim, s2, monitor_dist, count_bytes=False)
        sink1 = JobSink(self.sim,record_arrivals=True,absolute_time=True)
        sink2 = JobSink(self.sim,record_arrivals=True,absolute_time=True)
        demux1 = FlowDemux(flowids=[1, 2], outs=[s2, sink1], upgrades=[3, 0])

        # Connect topology
        g1.out = s1
        g2.out = s1
        s1.out = demux1
        s2.out = sink2

        # Choose the control object
        self.server1 = s1
        self.server2 = s2
        self.server1_monitor = s1_monitor
        self.server2_monitor = s2_monitor
        self.sink1 = sink1
        self.sink2 = sink2

    def _run_by_time_unit(self):
        self.sim.run(until=self.server1_monitor.step_ends)
        self.clock = self.sim.now

    def _set_logdir(self, abs_path):
        '''
        abs_path is the absolute path of '.../logs/'
        '''
        self.logdir = path.join(abs_path,"episodes/"+datetime.now().strftime("%Y%m%d-%H%M%S"))


    def step(self, action=None):
        '''
        Take a step by unit time in the fluid control problem.
        Args:
            action (numpy array): the same size of Mu, denotes weights of probability that
                                    the servers processing class i jobs. With the equivalent
                                    service rate is u[i] = Mu[i]*action[i].
        Returns:
            observation (object): agent's observation of the current environment
            reward (float) : amount of reward returned after previous action
            done (bool): whether the episode has ended, in which case further step() calls will return undefined results
            info (dict): contains auxiliary diagnostic information (helpful for debugging, and sometimes learning)
        '''
        if action:
            # Check stability condition
            assert (action.shape[0] == self.Mu.shape[0])
            w1, w2, w3 = action
            assert (w1 + w2 <= 1.0 and w1 + w2 > 0)
            assert (w3 <= 1.0 and w3 > 0)
            # Take action
            self.server1.control(np.array([w1, w2]))
            self.server2.control(np.array([w3]))
        # Run process
        self._run_by_time_unit()
        # Get state
        observation = self.server1.state()
        observation.update(self.server2.state())
        # Get reward
        reward = self.server1_monitor.average_size + self.server2_monitor.average_size

        done = self.clock >= self.elapse
        if done:
            self.reset()

        return observation, reward, done, {}

    def reset(self):
        '''
        1) Logs the previous episode and then delete environment.
        2) Create new SimPy environment.
        3) Start SimPy processes, return the first observation

        Should not reset the random number generators, as each new episode should
        be sampled independent of previous episodes.

        Returns:
            observation(object): the initial state
        '''
        self.render()
        del self.sim

        self._createnv()
        observation, _, _, _ = self.step()
        return observation

    def seed(self, seed: Optional[int] = None):
        if self.rng is None:
            self.rng, self.entropy = RNG(seed)

    def _plot(self):
        '''
        Returns:
            a matplotlib figure,plot history of ServerMonitor and JobSink
        '''
        figure=plt.figure(figsize=(20,20))
        rows=2
        cols=2
        plt.subplot(rows, cols, 1, title="Server1 average queue length")
        x1=np.arange(0,self.server1_monitor.sample_num*self.time_unit,self.time_unit)
        y1=np.array(self.server1_monitor.history)
        plt.plot(x1, y1)
        plt.subplot(rows, cols, 2, title="Server2 average queue length")
        x2 = np.arange(0, self.server2_monitor.sample_num * self.time_unit, self.time_unit)
        y2 = np.array(self.server2_monitor.history)
        plt.plot(x2, y2)
        plt.subplot(rows, cols, 3, title="Sink1 wait time")
        x3 = np.array(self.sink1.arrivals)
        y3 = np.array(self.sink1.waits)
        plt.plot(x3, y3)
        plt.subplot(rows, cols, 4, title="Sink2 wait time")
        x4 = np.array(self.sink2.arrivals)
        y4 = np.array(self.sink2.waits)
        plt.plot(x4, y4)
        return figure

    def _plot_to_TFimage(self,figure):
        '''
        Convert the matplotlib plot specified by 'figure' to a TF image and returns it.
        The supplied figure is destroyed after this call.
        '''
        # Save the plot to a PNG in memory
        buf=BytesIO
        plt.savefig(buf,format='png')
        # Closing the figure prevents it from being displayed directly inside the notebook
        plt.close(figure)
        buf.seek(0)
        # Convert PNG buffer to TF image
        image = tf.image.decode_png(buf.getvalue(), channels=4)
        # Add the batch dimension
        image = tf.expand_dims(image, 0)
        return image


    def render(self):
        '''
        Write logs to tensorboard.
        Automatically called by reset() method. Should not call from env outside.
        '''
        if not self.logdir:
            return
        file_writer=summary.create_file_writer(self.logdir)
        fig=self._plot()
        img=self._plot_to_TFimage(fig)
        with file_writer.as_default():
            summary.image("episode history", img, step=self.episodes)


    def close(self):
        '''
        Any necessary cleanup.
        '''
        del self.sim
        return 0
