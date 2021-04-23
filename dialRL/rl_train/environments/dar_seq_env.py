import numpy as np

import gym
from gym import spaces
import drawSvg as draw
import tempfile
# import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.image import imsave
from icecream import ic

from dialRL.dataset import tabu_parse_info, tabu_parse_best
from dialRL.dataset import DarPInstance
from dialRL.rl_train.reward_functions import *
from dialRL.utils import instance2world, indice2image_coordonates, distance, instance2Image_rep, GAP_function, float_equality, coord2int, time2int
from dialRL.rl_train.environments import DarEnv

class DarSeqEnv(DarEnv):
    """Custom Environment that follows gym interface"""

    def __init__(self, size, target_population, driver_population, reward_function, rep_type='block', dataset=None, test_env=False, time_end=1400, timeless=False, max_step=10, verbose=0):

        self.timeless = timeless
        self.rep_type = rep_type
        self.dataset = dataset
        self.reward_function = reward_function
        self.test_env = test_env
        self.max_step = max_step
        self.verbose = verbose
        if self.dataset :
            self.best_cost = tabu_parse_best(self.dataset)
            if self.test_env :
                super(DarSeqEnv, self).__init__(size, target_population, driver_population, time_end=time_end, max_step=self.max_step)
                self.extremas, self.target_population, self.driver_population, self.time_end, self.depot_position, self.size = tabu_parse_info(self.dataset)
            else :
                # Get info from dataset, to construct artificial data with those parameters
                super(DarSeqEnv, self).__init__(size, target_population, driver_population, time_end=time_end, max_step=self.max_step)
                self.extremas, self.target_population, self.driver_population, self.time_end, self.depot_position, self.size = tabu_parse_info(self.dataset)

        else :
            self.best_cost = 1000
            super(DarSeqEnv, self).__init__(size, target_population, driver_population, time_end=1400, max_step=max_step)
            self.extremas = [-self.size, -self.size, self.size, self.size]
            x = np.random.uniform(-self.size, self.size)
            y = np.random.uniform(-self.size, self.size)
            # # TODO: Remove this
            # self.depot_position = np.array((x, y)) #, dtype=np.float16)
            self.depot_position = np.array((0.1, 0.1))

        #self.driver_population*2 + self.target_population

        choix_id_target = True
        if not choix_id_target :
            self.action_space = spaces.Box(low=[self.extremas[0], self.extremas[1]],
                                           high=[self.extremas[2], self.extremas[3]],
                                           shape=(2,),
                                           dtype=np.float32)
        else :
            self.action_space = spaces.Discrete(self.target_population + 1)

        self.max_bloc_size = max(3 + self.target_population, 11)
        max_obs_value = max(self.target_population, self.extremas[2], self.extremas[3])
        self.obs_shape = 4 + 11*self.target_population + (3 + 6)*self.driver_population
        self.observation_space = spaces.Box(low=-max_obs_value,
                                            high=max_obs_value,
                                            shape=(4 + 11*self.target_population + (3 + 6)*self.driver_population , ), #self.max_bloc_size*(1+self.target_population+self.driver_population)
                                            dtype=np.float)

        self.max_reward = int(1.5 * self.size)
        self.reward_range = (- self.max_reward, self.max_reward)
        self.time_step = 0
        self.last_time_gap = 0
        self.current_episode = 0


        if self.verbose:
            print(' -- DarP Sequential Environment : -- ')
            for item in vars(self):
                print(item, ':', vars(self)[item])


    def get_info_vector(self):
        game_info = [time2int(self.time_step),
                     self.current_player,
                     coord2int(self.depot_position[0]),
                     coord2int(self.depot_position[1])]
        return game_info

    def get_GAP(self):
        g = GAP_function(self.total_distance, self.best_cost)
        if g is None :
            return 300.
        else :
            return g

    def is_fit_solution(self):
        return int(self.targets_states()[4] == self.target_population)

    def representation(self):
        if self.rep_type=='block' :
            # Agregate  world infrmations
            world_info = self.get_info_vector()
            # print('world: ', world_info)

            # Agregate targets infrmations
            targets_info = []
            for target in self.targets:
                targets_info.append(target.get_info_vector())
            targets_info = np.concatenate(targets_info)
            # print('targets_info: ', targets_info)

            drivers_info = []
            for driver in self.drivers:
                drivers_info.append(driver.get_info_vector())
            drivers_info = np.concatenate(drivers_info)
            # print('drivers_info: ', drivers_info)

            world = np.concatenate([world_info, targets_info, drivers_info])
            return world

        elif self.rep_type=='trans':
            # Depot (2dim), targets (T x 4dim), drivers (D x 2dim)
            positions = [self.depot_position,
                         [np.concatenate([target.pickup, target.dropoff]) for target in self.targets],
                         [driver.position for driver in self.drivers]]
            world = list(map(float, [self.time_step,
                     self.current_player,
                     self.depot_position[0],
                     self.depot_position[1]]))
            targets = [list(map(float, [target.identity,
                       target.pickup[0],
                       target.pickup[1],
                       target.dropoff[0],
                       target.dropoff[1],
                       target.start_fork[0],
                       target.start_fork[1],
                       target.end_fork[0],
                       target.end_fork[1],
                       target.weight,
                       target.state])) for target in self.targets]
            drivers = [list(map(float, [driver.identity,
                        driver.position[0],
                        driver.position[1],
                        driver.max_capacity])) +
                       [float(lo.identity) for lo in driver.loaded] for driver in self.drivers]
            return world, targets, drivers, positions

        elif self.rep_type=='trans2':
            # Depot (2dim), targets (T x 4dim), drivers (D x 2dim)
            positions = [self.depot_position,
                         [np.concatenate([target.pickup, target.dropoff]) for target in self.targets],
                         [driver.position for driver in self.drivers]]
            world = list(map(float, [self.current_player,
                                     self.current_player]))

            targets = [list(map(float, [target.identity,
                       target.state])) for target in self.targets]
            drivers = [list(map(float, [driver.identity])) +
                       [float(lo.identity) for lo in driver.loaded] for driver in self.drivers]
            return world, targets, drivers, positions

        elif self.rep_type=='trans25':
            # Depot (2dim), targets (T x 4dim), drivers (D x 2dim)
            positions = [self.depot_position,
                         [np.concatenate([target.pickup, target.dropoff]) for target in self.targets],
                         [driver.position for driver in self.drivers]]
            world = list(map(float, [self.current_player,
                                     self.current_player]))

            targets = [list(map(float, [target.identity + self.driver_population,
                       target.state])) for target in self.targets]

            drivers = [list(map(float, [driver.identity])) +
                       [float(lo.identity) for lo in driver.loaded] for driver in self.drivers]
            return world, targets, drivers, positions

        elif self.rep_type=='trans3':
            # Depot (2dim), targets (T x 4dim), drivers (D x 2dim)
            positions = [self.depot_position,
                         [np.concatenate([target.pickup, target.dropoff]) for target in self.targets],
                         [driver.position for driver in self.drivers]]

            times = [self.time_step,
                    [np.concatenate([target.start_fork, target.end_fork]) for target in self.targets]]

            world = list(map(float, [self.current_player,
                                     self.current_player]))
            targets = [list(map(float, [target.identity,
                       target.state])) for target in self.targets]
            drivers = [list(map(float, [driver.identity])) +
                       [float(lo.identity) for lo in driver.loaded] for driver in self.drivers]
            return world, targets, drivers, positions, times

        else :
            dic = {'world': {'time': self.time_step,
                             'player': self.current_player,
                             'depot': self.depot_position},
                   'targets': [{'id': target.identity,
                               'pickup': target.pickup,
                               'dropoff': target.dropoff,
                               'start': target.start_fork,
                               'end': target.end_fork,
                               'weight': target.weight,
                               'state': target.state} for target in self.targets ],
                   'drivers': [{'id': driver.identity,
                                'position': driver.position,
                                'capacity': driver.max_capacity,
                                'loaded': [lo.identity for lo in driver.loaded]} for driver in self.drivers] }
            return dic



    def get_image_representation(self):
        image = instance2Image_rep(self.targets, self.drivers, self.size, time_step=self.time_step)
        return image


    def reset(self):
        self.instance = DarPInstance(size=self.size,
                                    population=self.target_population,
                                    drivers=self.driver_population,
                                    depot_position=self.depot_position,
                                    extremas=self.extremas,
                                    time_end=self.time_end,
                                    verbose=False)
        if self.test_env and self.dataset:
            self.instance.dataset_generation(self.dataset)
        else :
            self.instance.random_generation(timeless=self.timeless)

        # print('* Reset - Instance image : ', self.instance.image)
        self.targets = self.instance.targets.copy()
        self.drivers = self.instance.drivers.copy()

        # It is important to let time step at target forks as well,
            #in order to let possibility for driver to wake up after waiting
        self.target_times = []
        for target in self.targets :
            self.target_times.append(target.start_fork[0])
            self.target_times.append(target.start_fork[1])
            self.target_times.append(target.end_fork[0])
            self.target_times.append(target.end_fork[1])

        self.next_players = [i for i in range(2, self.driver_population+1)]
        self.current_player = 1
        # distance is -1 if wrong aiming. 0 if there is no start of game yet and x if aimed corectly
        self.time_step = 0
        self.distance = 0
        self.total_distance = 0
        self.current_step = 0
        self.cumulative_reward = 0
        self.world = self.representation()
        self.last_aim = None
        self.last_cell = None
        self.short_log = ''
        return self._next_observation()


    def del_target(self, position):
        filter_fun = lambda x : x[0] == position[0] and x[1] == position[1]
        indices = [i for i in range(len(self.targets)) if filter_fun(self.targets[i])]
        for indice in indices:
            del self.targets[indice]


    def targets_states(self):
        count = [0, 0, 0, 0, 0]
        for target in self.targets:
            count[target.state + 2] += 1
        return count


    def _next_observation(self):
        self.world = self.representation()
        obs = self.world
        return obs


    def _take_action(self, action):
        """ Action: destination point as an indice of the map vactor. (Ex: 1548 over 2500)
        """
        aiming_driver = self.drivers[self.current_player - 1]
        current_pos = aiming_driver.position

        #In case we aim an empty box
        if action == 0 :
            self.distance = 0
            self.short_log = 'Just do nothing'
            aiming_driver.set_target(None, self.time_step)

        elif action > 0 and action <= self.target_population :
            aimed_target = self.targets[action - 1]
            self.last_aim = aimed_target.identity

            if aimed_target.state == 2 :
                self.distance = -3
                self.short_log = 'Aimed target already delivered'

            elif aimed_target.state == -2:
                result = aiming_driver.set_target(aimed_target, self.time_step)
                # Managed to load the target
                if result :
                    self.distance = distance(aiming_driver.position, aiming_driver.destination)
                    self.short_log = 'Aimed right, going for pick up !'
                else :
                    self.distance = -4
                    self.short_log = 'Aimed free target but couldn"t load target (driver full, or wrong time window)'

            elif aimed_target.state == 0:
                result = aiming_driver.set_target(aimed_target, self.time_step)
                if result :
                    self.distance = distance(aiming_driver.position, aiming_driver.destination)
                    self.short_log = 'Aimed right, and goiong for dropoff !'

                else :
                    self.distance = -5
                    self.short_log = 'Aimed right BUT driver doesnt contain that target'
            else :
                self.distance = -6
                self.short_log = 'That target is already been taken care of'

        else :
            self.distance = -2
            self.short_log = 'Other wrong doing ? TODO'


    def reward(self, distance):
        return self.max_reward - distance #Linear distance
        #int(1.5 * self.size * (1 / distance))


    def update_time_step(self):
        # Should other types of events be added here ?
            # Such as the end of the game event
        events_in = []
        for driver in self.drivers:
            if driver.destination is not None :
                events_in.append(self.time_step + distance(driver.position, driver.destination))
        events_in = events_in + self.target_times
        events_in = [t for t in events_in if t>self.time_step]
        self.last_time_gap = min(events_in) - self.time_step
        self.time_step = min(events_in)


    def update_drivers_positions(self):
        if self.last_time_gap > 0:
            for driver in self.drivers :
                if driver.destination is not None :
                    d = distance(driver.position, driver.destination)
                    if float_equality(self.last_time_gap, d, eps=0.001):
                        # Driver arraving to destination
                        driver.move(driver.destination)
                        if driver.order == 'picking':
                            result = driver.load(driver.target, self.time_step)
                            if not result :
                                raise "Error while loading the target, it is intended to be pickupable"

                        elif driver.order == 'dropping':
                            result = driver.unload(driver.target, self.time_step)
                            if not result :
                                raise "Error while unloading the target, it is intended to be droppable"

                        # reset the driver on waiting list
                        driver.set_target(None, self.time_step)
                        # self.next_players.append(driver.identity)

                    elif self.last_time_gap < d:
                        # lx + (1-l)x with l=d'/d
                        d = distance(driver.position, driver.destination)
                        lam = self.last_time_gap / d
                        new_pos = (1. - lam) * np.array(driver.position) + (lam * np.array(driver.destination))
                        if not float_equality(distance(new_pos, driver.position), self.last_time_gap, eps=0.001):
                            raise 'Distance float problem ? Here the distance to new position is different to time passing !'
                        driver.move(new_pos)

                    else :
                        raise "Error in updating drivers position. distance to destination:" + \
                        str(d) + "last time gap:" + str(self.last_time_gap)


    def step(self, action):
        # Action is the selected target id to handle (Eiither pick of drop)
        self._take_action(action)
        self.current_step += 1

        # Current time step need to be updated -> Driver move as well
        if not self.next_players and self.distance >= 0:
            while len(self.next_players) == 0 :
                # If no drivers turn, activate time steps
                if False :
                    image = self.get_image_representation()
                    imsave('./data/rl_experiments/test/' + str(env.current_step) + 'a.png', image)
                self.update_time_step()
                self.update_drivers_positions()
                if False :
                    image = self.get_image_representation()
                    imsave('./data/rl_experiments/test/' + str(env.current_step) + 'b.png', image)
                for driver in self.drivers :
                    if driver.destination is None :
                        # Charge all players that may need a new destination
                        self.next_players.append(driver.identity)


        # Update current player (if last action was successfull)
        if self.distance >=0 :
            self.current_player = self.next_players.pop()
            self.total_distance += self.distance


        # # Generate reward from distance
        # if self.distance < 0:
        #     reward = -1 #-int(self.max_reward//2)
        #     done = False
        # elif self.distance > 0:
        #     reward = self.reward(self.distance)
        #     done = False
        #     self.total_distance += self.distance
        # elif self.distance == 0 :
        #     reward = -1
        #     done = False
        done = False

        if self.targets_states()[4] == self.target_population :
            done = True
        if self.current_step >= self.max_step or self.time_step >= self.time_end :
            done = True

        reward = self.reward_function.compute(self.distance, done, self)

        self.cumulative_reward += reward

        if done:
            self.current_episode += 1

        obs = self._next_observation()

        info = {
            'delivered': self.targets_states()[4],
            'GAP': self.get_GAP(),
            'fit_solution': self.is_fit_solution()
        }
        # Last element is info (dict)
        return obs, reward, done, info


    def render(self, mode='classic'):
        print('\n--------------------- [Step', self.current_step, ']')

        print('World: ')
        # print(self.world)
        print(np.shape(self.world))

        if self.distance < 0 :
            print(f'Player {self.current_player} go lost ....')
        else :
            print(f'Player {self.current_player} aimed right')

        print('Crurrent time step: ', self.time_step)
        print('Crurrent player: ', self.current_player)
        print('Next player: ', self.next_players)
        print('Last aimed to : ', self.last_aim)
        print('Targets to go: ', self.targets_states())
        print('Cumulative reward : ', self.cumulative_reward)
        print(' Cumulative distance :', self.total_distance)
        print('Additional  information : ', self.short_log)
        print('GAP to best known solution: ', GAP_function(self.total_distance, self.best_cost))
        print('Is this a fit solution ? -> ', self.is_fit_solution())
        print('---------------------\n')


if __name__ == '__main__':
    data = './data/instances/cordeau2003/tabu1.txt'
    # data = None
    rwd_fun = ConstantDistributionReward()
    env = DarSeqEnv(size=4,
                    target_population=2,
                    driver_population=2,
                    reward_function=rwd_fun,
                    time_end=1400,
                    max_step=5000,
                    dataset=data,
                    test_env=False)
    # env = DarSeqEnv(size=4, target_population=5, driver_population=2, time_end=1400, max_step=100, dataset=None)
    cumulative_reward = 0
    observation = env.reset()
    env.render()
    for t in range(5000):
        action = env.action_space.sample()
        observation, reward, done, info = env.step(action)
        cumulative_reward += reward
        print('Cumulative reward : ', cumulative_reward, ' (', reward, ')')
        env.render()

        if done:
            print("\n ** \t Episode finished after {} time steps".format(t+1))
            break
    env.close()
