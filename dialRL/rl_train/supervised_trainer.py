import logging
import os
import imageio
import time
import json
import numpy as np
import math
import copy

# from stable_baselines.common.policies import MlpPolicy, MlpLstmPolicy
# from stable_baselines.common import make_vec_env
# from stable_baselines import PPO2
# from stable_baselines.common.callbacks import EvalCallback
# from stable_baselines.common.evaluation import evaluate_policy
# from stable_baselines.common.vec_env import DummyVecEnv
from clearml import Task
from icecream import ic
import drawSvg as draw
import seaborn as sn
import gym

from moviepy.editor import *
from matplotlib.image import imsave
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')


from torch.utils.data import DataLoader, SubsetRandomSampler, Dataset, ConcatDataset
from torch.distributions.categorical import Categorical
import torch
import torch.nn as nn
from torch.nn.functional import softmax
from torch.optim.lr_scheduler import MultiStepLR, ReduceLROnPlateau
import torch.optim as optim
from sklearn.metrics import confusion_matrix, f1_score

from dialRL.models import *
from dialRL.utils.reward_functions import *
from dialRL.environments import DarEnv, DarPixelEnv, DarSeqEnv
from dialRL.utils import get_device, trans25_coord2int, objdict, SupervisionDataset
# from dialRL.rl_train.callback import MonitorCallback
from dialRL.strategies import NNStrategy, NNStrategyV2
from dialRL.dataset import RFGenerator
from dialRL.dataset import DataFileGenerator

from dialRL.strategies.external.darp_rf.run_rf_algo import run_rf_algo



torch.autograd.set_detect_anomaly(True)
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # FATAL
# logging.getLogger('tensorflow').setLevel(logging.FATAL)
#
# tf.enable_eager_execution()




class SupervisedTrainer():
    def __init__(self, flags, sacred=None):
        ''' Inintialisation of the trainner:
                Entends to load all the correct set up, ready to train
        '''

        # Incorporate arguments to the object parameters
        for key in flags:
            setattr(self, key, flags[key])

        # Create saving experient dir
        if False :#self.sacred :
            self.path_name = '/'.join([self.sacred.experiment_info['base_dir'], self.file_dir, str(self.sacred._id)])
        else :
            self.path_name = self.rootdir + '/data/rl_experiments/' + self.alias + time.strftime("%d-%H-%M") + '_typ' + str(self.typ)
            print(' ** Saving train path: ', self.path_name)
            if not os.path.exists(self.path_name):
                os.makedirs(self.path_name, exist_ok=True)
            else :
                print(' Already such a path.. adding random seed')
                self.path_name = self.path_name + '#' + str(torch.randint(0, 10000, [1]).item())
                os.makedirs(self.path_name, exist_ok=True)

        # Save parameters
        with open(self.path_name + '/parameters.json', 'w') as f:
            json.dump(vars(self), f)

        self.sacred = sacred

        self.device = get_device()

        #### RL elements

        self.encoder_bn = False
        self.decoder_bn = False
        self.classifier_type = 1

        reward_function = globals()[self.reward_function]()
        if self.typ==15:
            self.rep_type = '15'
        elif self.typ==16:
            self.rep_type = '16'
        elif self.typ==17:
            self.rep_type = '17'
            self.model='Trans17'
        elif self.typ in [18, 19]:
            self.rep_type = '17'
            self.model='Trans17'
        elif self.typ in [20, 21, 22]:
            self.encoder_bn=True
            self.rep_type = '17'
            self.model='Trans17'
            self.emb_typ = self.typ - 3
        elif self.typ in [23, 24, 25]:
            self.encoder_bn=True
            self.decoder_bn=True
            self.rep_type = '17'
            self.model='Trans17'
            self.emb_typ = self.typ - 6
        elif self.typ in [26]:
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = self.typ
        elif self.typ in [27]:
            # 2 layer + 0 output
            self.classifier_type = 2
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [28]:
            # 2 layer + mixing dimentions
            self.classifier_type = 3
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [29]:
            # On layer + 0 dim as output
            self.classifier_type = 4
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [30]:
            # On layer + mixer layer
            self.classifier_type = 5
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [31]:
            # 1 layer + driver output
            self.classifier_type = 6
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [32]:
            # 1 layer + driver output (but with a shift that should be better)
            self.classifier_type = 7
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [33]:
            # 1 layer with all infformation concatenated
            self.classifier_type = 8
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [34]:
            # one Autotransformer + 1 layer with all infformation concatenated
            self.classifier_type = 9
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [35]:
            # 1 layer with 4 last vectors of transformer concatenated
            self.classifier_type = 10
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [36]:
            # 4 last encoder vectors + flatten in 1 layer
            self.classifier_type = 11
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [37]:
            # 32 but with batch norm in encoder
            self.classifier_type = 7
            self.encoder_bn=True
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26
        elif self.typ in [38]:
            # Adding the last 4 layers, concatenated as in 33
            self.classifier_type = 12
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '16'
            self.model='Trans18'
            self.emb_typ = 26

        # Pre Train module now
        elif self.typ in [40]:
            # Take as 38 ?
            self.classifier_type = 12
            self.emb_typ = 40
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '18'
            self.unfreezing_strat=1
            self.model='Trans19'
        elif self.typ in [41]:
            # Take as 38 + Unfreeze all
            self.classifier_type = 12
            self.emb_typ = 40
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '18'
            self.unfreezing_strat = 2
            self.model='Trans19'
        elif self.typ in [42]:
            # Take as 34
            self.classifier_type = 9
            self.emb_typ = 40
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '18'
            self.unfreezing_strat = 1
            self.model='Trans19'
        elif self.typ in [43]:
            # Take as 34 + unfreeze all
            self.classifier_type = 9
            self.emb_typ = 40
            self.encoder_bn=False
            self.decoder_bn=False
            self.rep_type = '18'
            self.unfreezing_strat = 2
            self.model='Trans19'


        else :
            raise "Find your own typ men"

        ## TODO: Add globals()[self.env]
        self.env = DarSeqEnv(size=self.image_size,
                          target_population=self.nb_target,
                          driver_population=self.nb_drivers,
                          reward_function=reward_function,
                          rep_type=self.rep_type,
                          max_step=self.max_step,
                          test_env=False,
                          timeless=self.timeless,
                          dataset=self.dataset,
                          verbose=self.verbose)

        # self.eval_env = DummyVecEnv([lambda : DarSeqEnv(size=self.image_size,
        self.eval_env = DarSeqEnv(size=self.image_size,
                                  target_population=self.nb_target,
                                  driver_population=self.nb_drivers,
                                  reward_function=reward_function,
                                  rep_type=self.rep_type,
                                  max_step=self.max_step,
                                  timeless=self.timeless,
                                  test_env=True,
                                  dataset=self.dataset)
                          # dataset=self.dataset) for i in range(1)])
        # DATASET EVAL
        self.dataset_instance_folder = self.rootdir + '/data/instances/cordeau2006/'
        self.inst_name = 'a' + str(self.nb_drivers) + '-' + str(self.nb_target)
        data_instance = self.dataset_instance_folder + self.inst_name + '.txt'
        reward_function = globals()[self.reward_function]()
        self.dataset_env = DarSeqEnv(size=self.image_size, target_population=self.nb_target, driver_population=self.nb_drivers,
                                  rep_type=self.rep_type, reward_function=reward_function, test_env=True, dataset=data_instance)
        # Get the best known solution from .txt instanaces
        with open(self.dataset_instance_folder + 'gschwind_results.txt') as f:
            for line in f :
                inst, bks = line.split(' ')
                if inst == self.inst_name :
                    self.dataset_env.best_cost = float(bks)
                    break;
            f.close()

        self.best_eval_metric = [0, 1000, 300, 300] # accuracy + loss + dataset GAP + online GAP
        self.train_rounds = 40
        self.partial_data_state=0
        self.nb_target = self.env.target_population
        self.nb_drivers = self.env.driver_population
        self.image_size = self.env.size
        self.max_time=int(self.env.time_end)

        if self.pretrain:
            self.supervision_function = 'nn'

        if self.supervision_function == 'nn':
            self.supervision = NNStrategy(reward_function=self.reward_function,
                                      env=self.env)
        elif self.supervision_function == 'nnV2':
            self.supervision = NNStrategyV2(reward_function=self.reward_function,
                                      env=self.env)
        elif self.supervision_function == 'rf':
            self.supervision = RFGenerator(params=objdict(vars(self)))
        else :
            raise ValueError('Could not find the supervision function demanded: '+ self.supervision_function)

        # Model Choice
        if self.model=='MlpPolicy':
            self.model = MlpPolicy
        elif self.model=='MlpLstmPolicy':
            self.model = MlpLstmPolicy
        elif self.model=='Trans1':
            self.model = globals()[self.model](src_vocab_size=1000,
                                                 trg_vocab_size=self.nb_target + 1,
                                                 max_length=self.nb_drivers+1,
                                                 src_pad_idx=self.image_size,
                                                 trg_pad_idx=self.image_size,
                                                 dropout=self.dropout,
                                                 device=self.device).to(self.device).double()
        elif self.model=='Trans2':
            self.model = globals()[self.model](src_vocab_size=1000,
                                                 trg_vocab_size=self.nb_target + 1,
                                                 max_length=self.nb_drivers+1,
                                                 src_pad_idx=self.image_size,
                                                 trg_pad_idx=self.image_size,
                                                 dropout=self.dropout,
                                                 num_layer=self.num_layer,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 extremas=self.env.extremas,
                                                 device=self.device).to(self.device).double()
        elif self.model=='Trans25':
            self.model = globals()[self.model](src_vocab_size=1000,
                                                 trg_vocab_size=1000,
                                                 max_length=10,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 dropout=self.dropout,
                                                 num_layer=self.num_layer,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 extremas=self.env.extremas,
                                                 device=self.device).to(self.device).double()
        elif self.model=='Trans27':
            self.model = globals()[self.model](src_vocab_size=50000,
                                                 trg_vocab_size=self.nb_target + 1,
                                                 max_length=10,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 dropout=self.dropout,
                                                 extremas=self.env.extremas,
                                                 num_layers=self.num_layers,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 device=self.device,
                                                 typ=self.typ).to(self.device).double()
        elif self.model=='Trans28':
            self.model = globals()[self.model](src_vocab_size=50000,
                                                 trg_vocab_size=self.vocab_size + 1,
                                                 max_length=self.nb_target*2 + self.nb_drivers + 1,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 embed_size=self.embed_size,
                                                 dropout=self.dropout,
                                                 extremas=self.env.extremas,
                                                 device=self.device,
                                                 num_layers=self.num_layers,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 typ=self.emb_typ,
                                                 max_time=int(self.env.time_end)).to(self.device).double()
        elif self.model=='Trans17':
            self.model = globals()[self.model](src_vocab_size=50000,
                                                 trg_vocab_size=self.vocab_size + 1,
                                                 max_length=self.nb_target*2 + self.nb_drivers + 1,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 embed_size=self.embed_size,
                                                 dropout=self.dropout,
                                                 extremas=self.env.extremas,
                                                 device=self.device,
                                                 num_layers=self.num_layers,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 typ=self.emb_typ,
                                                 max_time=int(self.env.time_end),
                                                 encoder_bn=self.encoder_bn,
                                                 decoder_bn=self.decoder_bn).to(self.device).double()
        elif self.model=='Trans18':
            self.model = globals()[self.model](src_vocab_size=50000,
                                                 trg_vocab_size=self.vocab_size + 1,
                                                 max_length=self.nb_target*2 + self.nb_drivers + 1,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 embed_size=self.embed_size,
                                                 dropout=self.dropout,
                                                 extremas=self.env.extremas,
                                                 device=self.device,
                                                 num_layers=self.num_layers,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 typ=self.emb_typ,
                                                 max_time=int(self.env.time_end),
                                                 classifier_type=self.classifier_type,
                                                 encoder_bn=self.encoder_bn,
                                                 decoder_bn=self.decoder_bn).to(self.device).double()
        elif self.model=='Trans19':
            self.model = globals()[self.model](src_vocab_size=50000,
                                                 trg_vocab_size=self.vocab_size + 1,
                                                 max_length=self.nb_target*2 + self.nb_drivers + 1,
                                                 src_pad_idx=-1,
                                                 trg_pad_idx=-1,
                                                 embed_size=self.embed_size,
                                                 dropout=self.dropout,
                                                 extremas=self.env.extremas,
                                                 device=self.device,
                                                 num_layers=self.num_layers,
                                                 heads=self.heads,
                                                 forward_expansion=self.forward_expansion,
                                                 typ=self.emb_typ,
                                                 max_time=int(self.env.time_end),
                                                 classifier_type=self.classifier_type,
                                                 encoder_bn=self.encoder_bn,
                                                 decoder_bn=self.decoder_bn,
                                                 max_capacity=self.env.max_capacity,
                                                 image_size=self.image_size,
                                                 pretrain=self.pretrain,
                                                 unfreezing_strat=self.unfreezing_strat).to(self.device).double()
        else :
            raise "self.model in PPOTrainer is not found"

        # loss
        if self.criterion == 'MSE':
            self.criterion = nn.MSELoss()
        elif self.criterion == 'l1':
            self.criterion = nn.L1Loss()
        elif self.criterion == 'crossentropy':
            self.criterion = nn.CrossEntropyLoss()
        else :
            raise "Not found criterion"
        if self.pretrain :
            self.dist_criterion = nn.L1Loss()
            self.class_criterion = nn.CrossEntropyLoss()

        # ic(self.model.parameters())
        # for pa in self.model.parameters():
        #     ic(pa)
        # for chi in self.model.named_children():
        #     ic(chi)
        # exit()

        # optimizer
        if self.optimizer == 'Adam':
            self.optimizer = optim.Adam(self.model.parameters(), lr=self.lr)
        elif self.optimizer == 'SGD':
            self.optimizer = optim.SGD(self.model.parameters(), lr=self.lr, momentum=0.95)
        else :
            raise "Not found optimizer"

        # Scheduler
        if self.scheduler == 'plateau' :
            self.scheduler = ReduceLROnPlateau(self.optimizer, mode='min', patience=self.patience, factor=self.gamma)
        elif self.scheduler == 'step':
            self.scheduler = MultiStepLR(self.optimizer, milestones=self.milestones, gamma=self.gamma)

        # Checkpoint
        if self.checkpoint_dir :
            print(' -- -- -- -- -- Loading  -- -- -- -- -- --')
            if self.typ >= 40 :
                self.model.load_state_dict(torch.load(self.rootdir + '/data/rl_experiments/' + self.checkpoint_dir).state_dict(), strict=False)
            else:
                self.model.load_state_dict(torch.load(self.rootdir + '/data/rl_experiments/' + self.checkpoint_dir).state_dict())
            print(' -- The model weights has been loaded ! --')
            print(' -----------------------------------------')

        if self.rl < 10000:
            self.baseline_model = copy.deepcopy(self.model)

        # number of elements passed throgh the model for each epoch
        self.testing_size = self.batch_size * (10000 // self.batch_size)    #About 10k
        self.training_size = self.batch_size * (100000 // self.batch_size)   #About 100k

        # self.monitor = MonitorCallback(eval_env=self.eval_env,
        #                               check_freq=self.monitor_freq,
        #                               save_example_freq=self.example_freq,
        #                               log_dir=self.path_name,
        #                               n_eval_episodes=self.eval_episodes,
        #                               verbose=self.verbose,
        #                               sacred=self.sacred)
        self.current_epoch = 0


        print(' *// What is this train about //* ')
        for item in vars(self):
            if item == "model":
                vars(self)[item].summary()
            else :
                print(item, ':', vars(self)[item])


    def save_example(self, observations, rewards, number, time_step):
        noms = []
        dir = self.path_name + '/example/' + str(time_step) + '/ex_number' + str(number)
        if dir is not None:
            os.makedirs(dir, exist_ok=True)

            for i, obs in enumerate(observations):
                save_name = dir + '/' + str(i) + '_r=' + str(rewards[i]) + '.png'  #[np.array(img) for i, img in enumerate(images)
                # if self.env.__class__.__name__ == 'DummyVecEnv':
                #     image = self.norm_image(obs[0], scale=1)
                # else :
                #     image = self.norm_image(obs, scale=1)
                image = obs
                # print('SHae after image', np.shape(image))
                imsave(save_name, image)
                noms.append(save_name)

        # Save the imges as video
        video_name = dir + 'r=' + str(np.sum(rewards)) + '.mp4'
        clips = [ImageClip(m).set_duration(0.2)
              for m in noms]

        concat_clip = concatenate_videoclips(clips, method="compose")
        concat_clip.write_videofile(video_name, fps=24, verbose=None, logger=None)

        if self.sacred :
            self.sacred.get_logger().report_media('video', 'Res_' + str(number) + '_Rwd=' + str(np.sum(rewards)),
                                                  iteration=time_step,
                                                  local_path=video_name)
        del concat_clip
        del clips

    def save_svg_example(self, observations, rewards, number, time_step):
        dir = self.path_name + '/example/' + str(time_step) + '/ex_number' + str(number)
        video_name = dir + '/Strat_res.mp4'
        if dir is not None:
            os.makedirs(dir, exist_ok=True)

        with draw.animate_video(video_name, align_right=True, align_bottom=True) as anim:
            # Add each frame to the animation
            for i, s in enumerate(observations):
                anim.draw_frame(s)
                if i==len(observations)-1 or i==0:
                    for i in range(5):
                        anim.draw_frame(s)

        if self.sacred :
            self.sacred.get_logger().report_media('Gif', 'Res_' + str(number) + '_Rwd=' + str(np.sum(rewards)),
                                                  iteration=time_step,
                                                  local_path=video_name)


    def generate_supervision_data(self):
        print('\t ** Generation Started **')
        number_batch = self.data_size // self.batch_size
        size = number_batch * self.batch_size
        if self.datadir:
            data_directory = self.datadir
        else :
            data_directory = self.rootdir + '/data/supervision_data/'

        data = []
        if self.dataset:
            self.eval_episodes = 1
            data_type = self.dataset.split('/')[-1].split('.')[0]
            saving_name = data_directory + data_type + '_s{s}_tless{tt}_fun{sf}_typ{ty}/'.format(s=str(self.data_size),
                                                                                                                tt=str(self.timeless),
                                                                                                                sf=str(self.supervision_function),
                                                                                                                ty=str(self.rep_type))
        else :
            saving_name = data_directory + 's{s}_t{t}_d{d}_i{i}_tless{tt}_fun{sf}_typ{ty}/'.format(s=str(self.data_size),
                                                                                                              t=str(self.nb_target),
                                                                                                              d=str(self.nb_drivers),
                                                                                                              i=str(self.image_size),
                                                                                                              tt=str(self.timeless),
                                                                                                              sf=str(self.supervision_function),
                                                                                                              ty=str(self.rep_type))

        action_counter = np.zeros(self.vocab_size + 1)
        self.data_part = 0

        def load_dataset():
            return [saving_name + file for file in os.listdir(saving_name)]
            # files_names = os.listdir(saving_name)
            # datasets = []
            # for file in files_names:
            #     print('Datafile folder:', saving_name)
            #     print(file)
            #     datasets.append(torch.load(saving_name + file))
            # return ConcatDataset(datasets)

        def partial_name(size):
            name = saving_name + '/dataset_elementN' + str(self.data_part) + '_size' + str(size) + '.pt'
            self.data_part += 1
            return name

        if os.path.isdir(saving_name) :
            print('This data is already out there !')
            dataset = load_dataset()
            # for data in dataset:
            #     o, a = data
            #     action_counter[a] += 1
            # self.criterion.weight = torch.from_numpy(action_counter).to(self.device)
            return dataset
        else :
            os.makedirs(saving_name)

        done = True
        last_save_size = 0
        sub_data = []
        sub_action_counter = np.zeros(self.vocab_size + 1)
        observation = self.env.reset()

        # Generate a Memory batch
        for element in range(size):

            if done :
                if self.env.is_fit_solution():
                    data = data + sub_data
                    action_counter = action_counter + sub_action_counter
                elif self.pretrain:
                    # Might wana subsample thiiiis
                    data = data + sub_data
                    action_counter = action_counter + sub_action_counter
                else :
                    print('/!\ Found a non feasable solution. It is not saved')

                if sys.getsizeof(data) > 100000: #200k bytes.
                    last_save_size += len(data)
                    train_data = SupervisionDataset(data, augment=self.augmentation, typ=self.typ)
                    name = partial_name(len(data))
                    torch.save(train_data, name)
                    data = []
                    print('Saving data status')

                observation = self.env.reset()
                sub_data = []
                sub_action_counter = np.zeros(self.vocab_size + 1)


            supervised_action = self.supervision.action_choice()
            supervised_action = torch.tensor([supervised_action]).type(torch.LongTensor).to(self.device)

            sub_data.append([observation, supervised_action])
            observation, reward, done, info = self.env.step(supervised_action)

            sub_action_counter[supervised_action-1] += 1

            if element % 1000 == 0:
                print('Generating data... [{i}/{ii}] memorry:{m}'.format(i=last_save_size + len(data), ii=self.data_size, m=sys.getsizeof(data)))

        train_data = SupervisionDataset(data, augment=self.augmentation, typ=self.typ)
        name = partial_name(len(data))
        torch.save(train_data, name)

        print('Done Generating !')
        self.criterion.weight = torch.from_numpy(action_counter).to(self.device)
        data = load_dataset()
        return data

    def pretrain_log(self, name, time_distance, pick_distance, drop_distance, correct_loaded, correct_available, total):
        if self.sacred :
            self.sacred.get_logger().report_scalar(title=name,
                series='Time distance', value=time_distance/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=name,
                series='Pick distance', value=pick_distance/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=name,
                series='Drop distance', value=drop_distance/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=name,
                series='Acc /% Loaded', value=100*correct_loaded/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=name,
                series='Acc /% available', value=100*correct_available/total, iteration=self.current_epoch)

    def pretrain_loss(self, output, prior_kwlg):
        out_time, out_pick, out_drop, out_loaded, out_available = output
        d_stuff, t_stuff = prior_kwlg
        d_stuff = torch.stack([torch.stack(elmt) for elmt in d_stuff]).to(self.device).permute(2, 0, 1)
        t_stuff = torch.stack([torch.stack(elmt) for elmt in t_stuff]).to(self.device).permute(2, 0, 1)
        prior_time, prior_loaded = d_stuff[:,:,0], d_stuff[:,:,1]
        prior_available, prior_pick, prior_drop = t_stuff[:,:,0], t_stuff[:,:,1], t_stuff[:,:,2]

        # The divisions are a ruff way to normalise the losses values
        time_distance = self.dist_criterion(out_time, prior_time)
        l1 = time_distance / self.max_time
        pick_distance = self.dist_criterion(out_pick, prior_pick)
        l2 = pick_distance / (2*self.image_size)
        drop_distance = self.dist_criterion(out_drop, prior_drop)
        l3 = drop_distance / (2*self.image_size)
        correct_loaded = 0
        l4 = 0
        for i in range(out_loaded.shape[1]):
            l4 += self.class_criterion(out_loaded[:,i], prior_loaded[:,i].long())
            correct_loaded += np.sum((out_loaded[:,i].argmax(-1) == prior_loaded[:,i].long()).cpu().numpy())
        l4 = l4 / (out_loaded.shape[1]*out_loaded.shape[-1])
        correct_loaded = correct_loaded / out_loaded.shape[1]

        correct_available = 0
        l5 = 0
        for i in range(out_available.shape[1]):
            l5 += self.class_criterion(out_available[:,i], prior_available[:,i].long())
            correct_available += np.sum((out_available[:,i].argmax(-1) == prior_available[:,i].long()).cpu().numpy())
        l5 = l5 / (out_available.shape[1]*out_available.shape[-1])
        correct_available = correct_available / out_available.shape[1]

        final_loss = l1 + l2 + l3 + l4 +l5

        # ic(l1, l2, l3, l4, l5)
        return final_loss, time_distance, pick_distance, drop_distance, correct_loaded, correct_available


    def train(self, dataloader):
        max_test_accuracy = 0
        running_loss = 0
        total = 0
        correct = nearest_accuracy = pointing_accuracy = 0
        mean_time_distance, mean_pick_distance, mean_drop_distance, mean_correct_loaded, mean_correct_available = 0, 0, 0, 0, 0

        self.model.train()
        for i, data in enumerate(dataloader):
            # set the parameter gradients to zero
            self.optimizer.zero_grad()

            observation, supervised_action = data

            if self.typ >= 40 :
                world, targets, drivers, positions, time_constraints, prior_kwlg = observation
            else :
                world, targets, drivers, positions, time_constraints = observation
            info_block = [world, targets, drivers]
            # Current player as trg elmt
            if self.typ in [17, 18, 19]:
                target_tensor = world
            else :
                target_tensor = world[1].unsqueeze(-1).type(torch.LongTensor).to(self.device)
            # target_tensor = torch.tensor([0 for _ in range(self.batch_size)]).unsqueeze(-1).type(torch.LongTensor).to(self.device)
            # coord_int = trans25_coord2int(positions[1][supervised_action])
            model_action = self.model(info_block,
                                      target_tensor,
                                      positions=positions,
                                      times=time_constraints)
            # Typ > 40: model action (time, int)xd , (bool, dist, dist)xt

            supervised_action = supervised_action.to(self.device)

            if self.pretrain :
                loss, time_distance, pick_distance, drop_distance, correct_loaded, correct_available = self.pretrain_loss(model_action, prior_kwlg)
                total += supervised_action.size(0)
                running_loss += loss.item()
                mean_time_distance += time_distance
                mean_pick_distance += pick_distance
                mean_drop_distance += drop_distance
                mean_correct_loaded += correct_loaded
                mean_correct_available += correct_available
                correct += (correct_available + correct_loaded)/2
            else :
                loss = self.criterion(model_action.squeeze(1), supervised_action.squeeze(-1))
                total += supervised_action.size(0)
                correct += np.sum((model_action.squeeze(1).argmax(-1) == supervised_action.squeeze(-1)).cpu().numpy())
                running_loss += loss.item()

            loss.backward()
            # update the gradients
            self.optimizer.step()

            if i == self.train_rounds:
                break

        acc = 100 * correct/total
        print('-> Réussite: ', acc, '%')
        print('-> Loss:', 100*running_loss/total)
        self.scheduler.step(running_loss)
        if self.pretrain :
            self.pretrain_log('Pretrain train',
                              mean_time_distance,
                              mean_pick_distance,
                              mean_drop_distance,
                              mean_correct_loaded,
                              mean_correct_available,
                              total)

        if self.sacred :
            self.sacred.get_logger().report_scalar(title='Train stats',
                series='train loss', value=100*running_loss/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title='Train stats',
                series='Train accuracy', value=acc, iteration=self.current_epoch)


    def generate_rl_data(self):
        print(" - Generate ...")
        size = self.batch_size
        rl_actions = []
        baseline_actions = []
        rl_rewards = []
        baseline_rewards = []
        cathegorical_choices = []
        final_data = []
        step = 0
        get_optimal_baseline = True
        file_gen = DataFileGenerator(env=self.env, out_dir=self.rootdir + '/dialRL/strategies/data/DARP_cordeau/', data_size=1)

        # Generate a Memory batch
        self.model.train()
        self.baseline_model.eval()
        # Number of episodes
        while step < size:

            instance_file_name = file_gen.generate_file(tmp_name='rl_instance')[0]
            reward_function = globals()[self.reward_function]()
            self.env = DarSeqEnv(size=self.image_size, target_population=self.nb_target, driver_population=self.nb_drivers,
                                rep_type=self.rep_type, reward_function=reward_function, test_env=True, dataset=instance_file_name)
            self.eval_env = DarSeqEnv(size=self.image_size, target_population=self.nb_target, driver_population=self.nb_drivers,
                                      rep_type=self.rep_type, reward_function=reward_function, test_env=True, dataset=instance_file_name)

            done = rl_done = baseline_done = False
            baseline_observation = self.eval_env.reset()
            rl_observation = self.env.reset()

            if get_optimal_baseline:
                baseline_done = True
                solution_file = ''
                fail_counter = 0
                while not solution_file :
                    if not self.verbose:
                        sys.stdout = open('test_file.out', 'w')
                    try :
                        rf_time = time.time()
                        solution_file, supervision_perf, l_bound = run_rf_algo('0')
                        rf_time = time.time() - rf_time
                        if not self.verbose :
                            sys.stdout = sys.__stdout__
                        if l_bound is None :
                            print('Wrong solution ?')
                            solution_file = ''
                    except:
                        if not self.verbose :
                            sys.stdout = sys.__stdout__
                        fail_counter += 1
                        print('ERROR in RUN RF ALGO. PASSING THROUGH', fail_counter)
                baseline_rewards = [l_bound]


            # Run a full episode
            while not done :
                # Pass in learning model
                if not rl_done:
                    world, targets, drivers, positions, time_contraints = rl_observation
                    w_t = [torch.tensor([winfo],  dtype=torch.float64) for winfo in world]
                    t_t = [[torch.tensor([tinfo], dtype=torch.float64 ) for tinfo in target] for target in targets]
                    d_t = [[torch.tensor([dinfo],  dtype=torch.float64) for dinfo in driver] for driver in drivers]
                    info_block = [w_t, t_t, d_t]

                    positions = [torch.tensor([positions[0]], dtype=torch.float64),
                                 [torch.tensor([position], dtype=torch.float64) for position in positions[1]],
                                 [torch.tensor([position], dtype=torch.float64) for position in positions[2]]]

                    time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                                     [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]],
                                     [torch.tensor([time], dtype=torch.float64) for time in time_contraints[2]]]

                    if self.typ in [17, 18, 19]:
                        target_tensor = torch.tensor(world).unsqueeze(-1).type(torch.LongTensor).to(self.device)
                    else :
                        target_tensor = torch.tensor([world[1]]).unsqueeze(-1).type(torch.LongTensor).to(self.device)
                    rl_action = self.model(info_block,
                                              target_tensor,
                                              positions=positions,
                                              times=time_contraints)
                    bernouie_action = Categorical(softmax(rl_action)).sample()

                    rl_observation, rl_reward, rl_done, info = self.env.step(bernouie_action)
                    rl_actions.append(rl_action)
                    cathegorical_choices.append(bernouie_action)
                    rl_rewards.append(rl_reward)

                # Pass in Baseline
                if not baseline_done and not get_optimal_baseline:
                    world, targets, drivers, positions, time_contraints = baseline_observation
                    w_t = [torch.tensor([winfo],  dtype=torch.float64) for winfo in world]
                    t_t = [[torch.tensor([tinfo], dtype=torch.float64 ) for tinfo in target] for target in targets]
                    d_t = [[torch.tensor([dinfo],  dtype=torch.float64) for dinfo in driver] for driver in drivers]
                    info_block = [w_t, t_t, d_t]

                    positions = [torch.tensor([positions[0]], dtype=torch.float64),
                                 [torch.tensor([position], dtype=torch.float64) for position in positions[1]],
                                 [torch.tensor([position], dtype=torch.float64) for position in positions[2]]]

                    time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                                     [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]],
                                     [torch.tensor([time], dtype=torch.float64) for time in time_contraints[2]]]

                    if self.typ in [17, 18, 19]:
                        target_tensor = torch.tensor(world).unsqueeze(-1).type(torch.LongTensor).to(self.device)
                    else :
                        target_tensor = torch.tensor([world[1]]).unsqueeze(-1).type(torch.LongTensor).to(self.device)
                    baseline_action = self.baseline_model(info_block,
                                              target_tensor,
                                              positions=positions,
                                              times=time_contraints)

                    baseline_observation, baseline_reward, baseline_done, info = self.eval_env.step(baseline_action.squeeze(1).argmax(-1))
                    baseline_rewards.append(baseline_reward)
                    baseline_actions.append(baseline_action)

                done = rl_done and baseline_done

            # Done with episode
            cathegorical_choices = torch.stack(cathegorical_choices).squeeze()
            sumLogProbOfActions = torch.log(softmax(torch.stack(rl_actions).squeeze(1)).gather(1, cathegorical_choices.unsqueeze(-1))).double()
            sumLogProbOfActions = sumLogProbOfActions.squeeze().sum(0)
            rl_rewards = torch.tensor(rl_rewards).sum(-1).to(self.device).double()
            baseline_rewards = torch.tensor(baseline_rewards).sum(-1).to(self.device).double()

            final_data.append([rl_rewards, baseline_rewards, sumLogProbOfActions])
            rl_actions = []
            baseline_actions = []
            baseline_rewards = []
            cathegorical_choices = []
            rl_rewards = []
            step += 1
            print('Number of memoriesed episodes [{s} / {ss}]'.format(s=step, ss=size))

        # Enough data has been collected
        train_data = SupervisionDataset(final_data, typ=self.typ, augment=False)
        return train_data


    def rl_train(self):
        max_test_accuracy = 0
        running_loss = 0
        running_baseline = 0
        running_reward = 0
        total = 0
        correct = nearest_accuracy = pointing_accuracy = 0

        dataset = self.generate_rl_data()
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=self.shuffle)

        self.model.train()
        self.baseline_model.eval()
        for i, data in enumerate(dataloader):
            rl_reward, baseline_reward, sumLogProbOfActions = data

            # loss = - torch.mean(reward.to(self.device) * softmax(model_action).log().sum(-1).to(self.device))

            #loop:
            #   idx = torch.argmax(prob_next_node, dim=1)
            #   ProbOfChoices = prob_next_node[zero_to_bsz, idx]
            #   sumLogProbOfActions.append( torch.log(ProbOfChoices) )
            # sumLogProbOfActions = torch.stack(sumLogProbOfActions,dim=1).sum(dim=1)

            # Obj: minimiser la distance  == maximiser la (-distance)=Reward
            # dp - dm = positif -> minimiser
            # - (dp - dm) = dm - dp = negatif -> maximiser
            loss = torch.mean((baseline_reward - rl_reward) * sumLogProbOfActions )

            ic(rl_reward, baseline_reward, sumLogProbOfActions)
            ic(loss)

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            running_reward += torch.mean(rl_reward).cpu().item()
            running_baseline += torch.mean(baseline_reward).cpu().item()
            total += rl_reward.size(0)
            running_loss += loss.item()

        acc = 100 * correct/total
        print('-> Loss:', 100*running_loss/total)
        self.scheduler.step(running_loss)

        if self.sacred :
            self.sacred.get_logger().report_scalar(title='RL stats',
                series='RL train loss', value=running_loss/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title='RL stats',
                series='Baseline reward', value=running_baseline/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title='RL stats',
                series='Training reward', value=running_reward/total, iteration=self.current_epoch)

    def load_partial_data(self):
        if len(self.dataset_names) > 10:
            part_size = len(self.dataset_names) // 20
            files_names = self.dataset_names[self.partial_data_state*part_size:(self.partial_data_state+1)*part_size - 1]
            ic(len(files_names))
        else :
            files_names = self.dataset_names
        datasets = []
        for file in files_names:
            print('Datafile folder:', file)
            datasets.append(torch.load(file))
        self.partial_data_state += 1
        self.partial_data_state = self.partial_data_state % 10
        return ConcatDataset(datasets)

    def updating_data(self):
        if self.current_epoch == 0 :
            # First time (generate) and get files names of the data
            if self.supervision_function == 'rf':
                self.dataset_names = self.supervision.generate_dataset()
            elif self.pretrain :
                self.dataset_names = self.generate_supervision_data()
            else :
                self.dataset_names = self.generate_supervision_data()

        ic(len(self.dataset_names))
        # Load a 10th of the data
        dataset = self.load_partial_data()

        # Take care of the loaded dataset part to
        if self.supervision_function == 'rf':
            if self.balanced_dataset == 1 :
                action_counter = np.zeros(self.vocab_size + 1)
                data_list = []
                for i in range(self.vocab_size + 1):
                    data_list.append([])
                for data in dataset:
                    o, a = data
                    action_counter[a] += 1
                    data_list[a].append(data)

                min_nb = int(min(action_counter[action_counter > 0]))
                fin_data = []
                for i in range(len(action_counter)):
                    if action_counter[i] > 0:
                        fin_data = fin_data + data_list[i][:min_nb]

                dataset = SupervisionDataset(fin_data, augment=self.augmentation, typ=self.typ)

            elif self.balanced_dataset == 2 :
                # Over sampling method
                action_counter = np.zeros(self.vocab_size + 1)
                data_list = []
                for i in range(self.vocab_size + 1):
                    data_list.append([])
                for data in dataset:
                    o, a = data
                    action_counter[a] += 1
                    data_list[a].append(data)

                min_nb = int(min(action_counter[action_counter > 0]))
                max_nb = int(max(action_counter[action_counter > 0]))
                fin_data = []
                for i in range(len(action_counter)):
                    if action_counter[i] < max_nb and action_counter[i] > 0:
                        for j in range(int(max_nb/min_nb)) :
                            fin_data = fin_data + data_list[i]
                ic(len(fin_data))
                ic(len(fin_data)/max_nb)
                ic(len(action_counter))
                dataset = SupervisionDataset(fin_data, augment=self.augmentation, typ=self.typ)

            # If not balanced, weight the cross entropy respectivly to min_size/size
            else :
                action_counter = np.zeros(self.vocab_size + 1)
                for data in dataset:
                    o, a = data
                    action_counter[a] += 1
                min_nb = int(min(action_counter[action_counter > 0]))
                max_nb = int(max(action_counter[action_counter > 0]))
                action_counter[action_counter == 0] = min_nb
                ic(min_nb/max_nb)
                ic(max_nb/action_counter)
                weights = max_nb/action_counter
                if self.balanced_dataset == 3 :
                    weights[0] = 0.5
                elif self.balanced_dataset == 4 :
                    weights[0] = 0.9
                self.criterion.weight = torch.from_numpy(max_nb/action_counter).to(self.device)
                dataset = SupervisionDataset(dataset, augment=self.augmentation, typ=self.typ)

            # Divide the dataset into a validation and a training set.
            dataset_size = len(dataset)
            indices = list(range(dataset_size))
            split = int(np.floor(0.1 * dataset_size))
            # if self.shuffle and False :
            #     np.random.shuffle(indices)
            train_indices, val_indices = indices[split:], indices[:split]
            if self.shuffle :
                np.random.shuffle(train_indices)
                np.random.shuffle(val_indices)

            # Creating PT data samplers and loaders:
            train_sampler = SubsetRandomSampler(train_indices)
            valid_sampler = SubsetRandomSampler(val_indices)

            supervision_data = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size,
                                                       sampler=train_sampler)
            validation_data = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size,
                                                        sampler=valid_sampler)
        elif self.pretrain :
            dataset_size = len(dataset)
            indices = list(range(dataset_size))
            split = int(np.floor(0.1 * dataset_size))
            train_indices, val_indices = indices[split:], indices[:split]
            if self.shuffle :
                np.random.shuffle(train_indices)
                np.random.shuffle(val_indices)
            train_sampler = SubsetRandomSampler(train_indices)
            valid_sampler = SubsetRandomSampler(val_indices)
            supervision_data = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size,
                                                       sampler=train_sampler)
            validation_data = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size,
                                                        sampler=valid_sampler)
        else :
            for data in dataset:
                o, a = data
                action_counter[a] += 1
            self.criterion.weight = torch.from_numpy(action_counter).to(self.device)
            supervision_data = DataLoader(dataset, batch_size=self.batch_size, shuffle=self.shuffle)
            validation_data = DataLoader([], batch_size=self.batch_size, shuffle=self.shuffle)

        return supervision_data,  validation_data




    def run(self):
        """
            Just the main training loop
            (Eventually generate data)
            Train and evaluate
        """
        round_counter = 1e6 // (self.train_rounds -1)
        print('\t ** Learning START ! **')
        for epoch in range(self.epochs):
            self.current_epoch = epoch

            # Train
            if self.rl <= epoch:
                self.supervision_function = ''
                self.rl_train()
            else :
                # Every million visits update the dataset
                if round_counter * self.batch_size * self.train_rounds > self.data_size // 20:
                    if 'supervision_data' in locals():
                        del supervision_data
                        del validation_data
                    supervision_data, validation_data = self.updating_data()
                    round_counter = 0
                self.train(supervision_data)

            # Evaluate
            if self.supervision_function == 'rf':
                if self.pretrain:
                    self.offline_evaluation(validation_data, saving=True)
                else :
                    self.offline_evaluation(validation_data, saving=True)
                    self.online_evaluation(full_test=True, supervision=False, saving=False)
                    self.dataset_evaluation()
            else :
                if self.pretrain:
                    self.offline_evaluation(validation_data, saving=True)
                elif self.rl <= epoch:
                    self.dataset_evaluation()
                else :
                    self.online_evaluation()
                    if self.dataset:
                        self.online_evaluation(full_test=False)

            round_counter +=1

        print('\t ** Learning DONE ! **')



    def offline_evaluation(self, dataloader, full_test=True, saving=True):
        """
            Use a dataloader as a validation set to verify the models ability to find the supervision strategy.
            As there is no online interaction with out ennvironement. The nomber of data metrics is minimal.
        """
        max_test_accuracy = 0
        running_loss = 0
        total = 0
        correct = nearest_accuracy = pointing_accuracy = 0
        mean_time_distance, mean_pick_distance, mean_drop_distance, mean_correct_loaded, mean_correct_available = 0, 0, 0, 0, 0

        y_pred, y_sup = [], []
        if full_test :
            eval_name = 'Offline Test'
        else :
            eval_name = 'Supervised Test stats'


        self.model.eval()
        for i, data in enumerate(dataloader):
            observation, supervised_action = data

            if self.emb_typ >= 40 :
                world, targets, drivers, positions, time_constraints, prior_kwlg = observation
            else :
                world, targets, drivers, positions, time_constraints = observation

            info_block = [world, targets, drivers]
            # Current player as trg elmt
            # target_tensor = world[1].unsqueeze(-1).type(torch.LongTensor).to(self.device)
            # target_tensor = torch.tensor([0 for _ in range(self.batch_size)]).unsqueeze(-1).type(torch.LongTensor).to(self.device)
            # coord_int = trans25_coord2int(positions[1][supervised_action])
            if self.typ in [17, 18, 19]:
                target_tensor = world
            else :
                target_tensor = world[1].unsqueeze(-1).type(torch.LongTensor).to(self.device)

            model_action = self.model(info_block,
                                      target_tensor,
                                      positions=positions,
                                      times=time_constraints)


            # model_action = model_action[:,0]
            supervised_action = supervised_action.to(self.device)

            if self.pretrain :
                loss, time_distance, pick_distance, drop_distance, correct_loaded, correct_available = self.pretrain_loss(model_action, prior_kwlg)
                total += supervised_action.size(0)
                running_loss += loss.item()
                mean_time_distance += time_distance
                mean_pick_distance += pick_distance
                mean_drop_distance += drop_distance
                mean_correct_loaded += correct_loaded
                mean_correct_available += correct_available
                correct += (correct_available + correct_loaded)/2
                y_pred = y_pred + [0]
                y_sup = y_sup + [0]
            else :
                loss = self.criterion(model_action.squeeze(1), supervised_action.squeeze(-1))
                total += supervised_action.size(0)
                correct += np.sum((model_action.squeeze(1).argmax(-1) == supervised_action.squeeze(-1)).cpu().numpy())
                running_loss += loss.item()

                y_pred = y_pred +model_action.squeeze(1).argmax(dim=-1).flatten().tolist()
                y_sup = y_sup + supervised_action.squeeze(-1).tolist()

            # Limit train passage to 20 rounds
            if i == 20:
                break

        if self.pretrain :
            self.pretrain_log('Pretrain test',
                              mean_time_distance,
                              mean_pick_distance,
                              mean_drop_distance,
                              mean_correct_loaded,
                              mean_correct_available,
                              total)

        eval_acc = 100 * correct/total
        eval_loss = running_loss/total

        cf_matrix = confusion_matrix(y_sup, y_pred)
        #Calculate metrics for each label, and find their average weighted by support (the number of true instances for each label).
        f1_metric = f1_score(y_sup, y_pred, average='weighted')
        #Calculate metrics globally by counting the total true positives, false negatives and false positives.
        f1_metric1 = f1_score(y_sup, y_pred, average='micro')
        #Calculate metrics for each label, and find their unweighted mean. This does not take label imbalance into account.
        f1_metric2 = f1_score(y_sup, y_pred, average='macro')

        print('\t-->' + eval_name + 'Réussite: ', eval_acc, '%')
        print('\t-->' + eval_name + 'F1 :', f1_metric)
        print('\t-->' + eval_name + 'Loss:', running_loss/total)

        # Model saving. Condition: Better accuracy and better loss
        if saving and full_test and (eval_acc > self.best_eval_metric[0] or ( eval_acc == self.best_eval_metric[0] and eval_loss <= self.best_eval_metric[1] )):
            self.best_eval_metric[0] = eval_acc
            self.best_eval_metric[1] = eval_loss
            if self.checkpoint_type == 'best':
                model_name = self.path_name + '/models/best_offline_model.pt'
            else :
                model_name = self.path_name + '/models/model_offline' + str(self.current_epoch) + '.pt'
            os.makedirs(self.path_name + '/models/', exist_ok=True)
            print('\t New Best Accuracy Model <3')
            print('\tSaving as:', model_name)
            torch.save(self.model, model_name)

            dir = self.path_name + '/example/'
            os.makedirs(dir, exist_ok=True)
            save_name = dir + '/cf_matrix.png'
            conf_img = sn.heatmap(cf_matrix, annot=True)
            plt.savefig(save_name)
            plt.clf()
            self.sacred.get_logger().report_media('Image', 'Confusion Matrix',
                                              iteration=self.current_epoch,
                                              local_path=save_name)

        # Statistics on clearml saving
        if self.sacred :
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='reussite %', value=eval_acc, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Loss', value=running_loss/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='F1 score weighted', value=f1_metric, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='F1 score micro', value=f1_metric1, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='F1 score macro', value=f1_metric2, iteration=self.current_epoch)
            # self.sacred.get_logger().report_scalar(title=eval_name,
            #     series='Fit solution %', value=100*fit_sol/self.eval_episodes, iteration=self.current_epoch)
            # self.sacred.get_logger().report_scalar(title=eval_name,
            #     series='Average delivered', value=delivered/self.eval_episodes, iteration=self.current_epoch)
            # self.sacred.get_logger().report_scalar(title=eval_name,
            #     series='Average gap', value=gap/self.eval_episodes, iteration=self.current_epoch)
            # self.sacred.get_logger().report_scalar(title=eval_name,
            #     series='Step Reward', value=total_reward/total, iteration=self.current_epoch)

    def dataset_evaluation(self):
        print('\t** ON DATASET :', self.inst_name, '**')
        eval_name = 'Dataset Test'
        done = False
        observation = self.dataset_env.reset()
        total_reward = 0
        while not done:
            if self.emb_typ >= 40 :
                world, targets, drivers, positions, time_contraints, prior_kwlg = observation
                time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                             [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]]]
            else :
                world, targets, drivers, positions, time_contraints = observation
                time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                             [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]],
                             [torch.tensor([time], dtype=torch.float64) for time in time_contraints[2]]]

            positions = [torch.tensor([positions[0]], dtype=torch.float64),
                         [torch.tensor([position], dtype=torch.float64) for position in positions[1]],
                         [torch.tensor([position], dtype=torch.float64) for position in positions[2]]]

            w_t = [torch.tensor([winfo],  dtype=torch.float64) for winfo in world]
            t_t = [[torch.tensor([tinfo], dtype=torch.float64 ) for tinfo in target] for target in targets]
            d_t = [[torch.tensor([dinfo],  dtype=torch.float64) for dinfo in driver] for driver in drivers]
            info_block = [w_t, t_t, d_t]

            target_tensor = torch.tensor([world[1]]).unsqueeze(-1).type(torch.LongTensor).to(self.device)

            model_action = self.model(info_block,
                                      target_tensor,
                                      positions=positions,
                                      times=time_contraints)

            if self.typ >25:
                chosen_action = model_action.argmax(-1).cpu().item()
            else :
                chosen_action = model_action[:, 0].argmax(-1).cpu().item()

            observation, reward, done, info = self.dataset_env.step(chosen_action)
            total_reward += reward

        if info['fit_solution'] and info['GAP'] < self.best_eval_metric[2] :
            print('/-- NEW BEST GAP SOLUTION --\\')
            print('/-- GAP:', info['GAP'])
            self.best_eval_metric[2] = info['GAP']
            if self.checkpoint_type == 'best':
                model_name = self.path_name + '/models/best_GAP_model.pt'
            else :
                model_name = self.path_name + '/models/GAP_model_' + str(self.current_epoch) + '.pt'
            print('\tSaving as:', model_name)
            os.makedirs(self.path_name + '/models/', exist_ok=True)
            torch.save(self.model, model_name)

        print('/- Fit solution:', info['fit_solution'])
        print('/- with ',info['delivered'], 'deliveries')
        if info['fit_solution'] :
            print('/- GAP to optimal solution: ', info['GAP'], '(counts only if fit solution)')
        print('/- Optim Total distance:', self.dataset_env.best_cost)
        print('/- Model Total distance:', self.dataset_env.total_distance)

        if self.sacred :
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Fit solution', value=info['fit_solution'], iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Delivered', value=info['delivered'], iteration=self.current_epoch)
            if info['fit_solution'] > 0:
                self.sacred.get_logger().report_scalar(title=eval_name,
                    series='Average gap', value=info['GAP'], iteration=self.current_epoch)
            else :
                self.sacred.get_logger().report_scalar(title=eval_name,
                    series='Average gap', value=300, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Total Reward', value=total_reward, iteration=self.current_epoch)


    def online_evaluation(self, full_test=True, supervision=True, saving=True):
        """
            Online evaluation of the model according to the supervision method.
            As it is online, we  can maximise the testing informtion about the model.
        """
        correct = total = running_loss = total_reward = 0
        delivered = 0
        gap = 0
        fit_sol = 0
        self.supervision.env = self.eval_env
        if full_test :
            eval_name = 'Test stats'
        else :
            eval_name = 'Supervised Test stats'

        self.model.eval()
        for eval_step in range(self.eval_episodes):

            # Generate solution and evironement instance.
            if self.supervision_function == 'rf' :
                file_gen = DataFileGenerator(env=self.eval_env, out_dir=self.rootdir + '/dialRL/strategies/data/DARP_cordeau/', data_size=1)
                instance_file_name = file_gen.generate_file(tmp_name='eval_instance')[0]
                reward_function = globals()[self.reward_function]()
                self.eval_env = DarSeqEnv(size=self.image_size, target_population=self.nb_target, driver_population=self.nb_drivers,
                                          rep_type=self.rep_type, reward_function=reward_function, test_env=True, dataset=instance_file_name)

            done = False
            observation = self.eval_env.reset()

            if self.example_format == 'svg':
                to_save = [self.eval_env.get_svg_representation() if full_test else 0]
            else :
                to_save = [self.eval_env.get_image_representation() if full_test else 0]
            save_rewards = [0]
            last_time = 0

            while not done:
                if self.emb_typ >= 40 :
                    world, targets, drivers, positions, time_contraints, prior_kwlg = observation
                    time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                                 [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]]]
                else :
                    world, targets, drivers, positions, time_contraints = observation
                    time_contraints = [torch.tensor([time_contraints[0]], dtype=torch.float64),
                                 [torch.tensor([time], dtype=torch.float64) for time in time_contraints[1]],
                                 [torch.tensor([time], dtype=torch.float64) for time in time_contraints[2]]]

                positions = [torch.tensor([positions[0]], dtype=torch.float64),
                             [torch.tensor([position], dtype=torch.float64) for position in positions[1]],
                             [torch.tensor([position], dtype=torch.float64) for position in positions[2]]]

                w_t = [torch.tensor([winfo],  dtype=torch.float64) for winfo in world]
                t_t = [[torch.tensor([tinfo], dtype=torch.float64 ) for tinfo in target] for target in targets]
                d_t = [[torch.tensor([dinfo],  dtype=torch.float64) for dinfo in driver] for driver in drivers]
                info_block = [w_t, t_t, d_t]

                if self.typ in [17, 18, 19]:
                    target_tensor = w_t
                else :
                    target_tensor = torch.tensor([world[1]]).unsqueeze(-1).type(torch.LongTensor).to(self.device)

                model_action = self.model(info_block,
                                          target_tensor,
                                          positions=positions,
                                          times=time_contraints)

                if supervision :
                    supervised_action = self.supervision.action_choice()
                    supervised_action = torch.tensor([supervised_action]).type(torch.LongTensor).to(self.device)

                if self.typ >25:
                    chosen_action = model_action.argmax(-1).cpu().item()
                else :
                    chosen_action = model_action[:, 0].argmax(-1).cpu().item()

                if full_test :
                    observation, reward, done, info = self.eval_env.step(chosen_action)
                elif supervision :
                    observation, reward, done, info = self.eval_env.step(supervised_action)

                # self.eval_env.render()
                if supervision :
                    loss = self.criterion(model_action[:,0], supervised_action)
                    running_loss += loss.item()
                    correct += (chosen_action == supervised_action).cpu().numpy()[0]
                else :
                    correct += 0
                    running_loss += 0
                    loss = 0

                total_reward += reward
                total += 1

                if self.eval_env.time_step > last_time and full_test:
                    last_time = self.eval_env.time_step
                    if self.example_format == 'svg':
                        to_save.append(self.eval_env.get_svg_representation())
                    else :
                        to_save.append(self.eval_env.get_image_representation())
                    save_rewards.append(reward)
            # Env is done

            if self.supervision_function == 'rf' :
                if info['fit_solution']:
                    # Get a solution from the supervision
                    solution_file = ''
                    while not solution_file :
                        if not self.verbose:
                            sys.stdout = open('test_file.out', 'w')
                        try :
                            rf_time = time.time()
                            solution_file, supervision_perf, l_bound = run_rf_algo('0')
                            rf_time = time.time() - rf_time
                            if not self.verbose :
                                sys.stdout = sys.__stdout__
                            if l_bound is None :
                                print('Wrong solution ?')
                                solution_file = ''
                        except:
                            if not self.verbose :
                                sys.stdout = sys.__stdout__
                            print('ERROR in RUN RF ALGO. PASSING THROUGH')
                    gap += self.eval_env.get_GAP(best_cost=l_bound)
            else :
                # If not rf supervision
                gap += info['GAP']

            fit_sol += info['fit_solution'] #self.eval_env.is_fit_solution()
            delivered += info['delivered']

        # To spare time, only the last example is saved
        eval_acc = 100 * correct/total
        eval_loss = running_loss/total

        print('\t-->' + eval_name + 'Réussite: ', eval_acc, '%')
        print('\t-->' + eval_name + 'Loss:', running_loss/total)
        print('\t-->' + eval_name + 'Fit solution: ', 100*fit_sol/self.eval_episodes, '%')
        print('\t-->' + eval_name + 'Average delivered', delivered/self.eval_episodes)
        print('\t-->' + eval_name + 'Step Reward ', total_reward/total)

        # Model saving. Condition: Better accuracy and better loss
        if fit_sol > 0 and gap < self.best_eval_metric[3] :
            self.best_eval_metric[3] = gap
            if self.checkpoint_type == 'best':
                model_name = self.path_name + '/models/best_online_model.pt'
            else :
                model_name = self.path_name + '/models/model_online' + str(self.current_epoch) + '.pt'
            os.makedirs(self.path_name + '/models/', exist_ok=True)
            print('\t New Best online GAP Model <3')
            print('\tSaving as:', model_name)
            torch.save(self.model, model_name)

            # Saving an example
            # if self.example_format == 'svg':
            #     self.save_svg_example(to_save, save_rewards, 0, time_step=self.current_epoch)
            # else :
            #     self.save_example(to_save, save_rewards, 0, time_step=self.current_epoch)


        # Statistics on clearml saving
        if self.sacred :
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='reussite %', value=eval_acc, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Loss', value=running_loss/total, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Fit solution %', value=100*fit_sol/self.eval_episodes, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Average delivered', value=delivered/self.eval_episodes, iteration=self.current_epoch)
            if self.supervision_function == 'rf' :
                if fit_sol > 0:
                    self.sacred.get_logger().report_scalar(title=eval_name,
                        series='Average gap', value=gap/fit_sol, iteration=self.current_epoch)
                else :
                    self.sacred.get_logger().report_scalar(title=eval_name,
                        series='Average gap', value=300, iteration=self.current_epoch)
            else :
                self.sacred.get_logger().report_scalar(title=eval_name,
                    series='Average gap', value=gap/self.eval_episodes, iteration=self.current_epoch)
            self.sacred.get_logger().report_scalar(title=eval_name,
                series='Step Reward', value=total_reward/total, iteration=self.current_epoch)
