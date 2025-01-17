
from train_setup import TrainSetup
import argparse


model_config = {
    # name of the model/experiment in general (choose descriptive name, the .pt file will have the same name and store the parameters of the model)
    "model-name": "chinese_vs_else",

    # path to the dataset folder (must contain "matrix_name_list.pickle" and "nationality_classes.json" and be stored in "../datasets/preprocessed_datasets/")
    "dataset-name": "chinese_and_else",
    
    # percentage of the test and validation set (separately)
    "test-size": 0.2,

    # name of the optimizer (changing "optimizer" in this config won't make a difference, the optimizer has to be changed in the "train_setup.py" by hand)
    "optimizer": "Adam",

    # name of the loss function (changing "loss-function" in this config won't make a difference, the loss function has to be changed in the "train_setup.py" by hand)
    "loss-function": "NLLLoss",

    # amount of epochs
    "epochs": 4,

    # batch size
    "batch-size": 512,

    # cnn parameters (idx 0: amount of layers, idx 1: kernel size, idx 2: list of feature map dimensions)
    "cnn-parameters": [1, 3, [256]],
    
    # hidden size of the LSTM
    "hidden-size": 200, 

    # amount of layers inside the LSTM
    "rnn-layers": 2,

    # learning-rate parameters (idx 0: current lr, idx 1: decay rate, idx 2: decay intervall in iterations), 
    # change current lr (idx 0) when resuming the training to the learning rate of the last checkpoint (last two values don't have to be changed)
    "lr-schedule": [0.001, 0.95, 100],

    # dropout change of the LSTM output
    "dropout-chance": 0.3,

    # embedding size ("embedding-size" x 1)
    "embedding-size": 200,

    # augmentation chance (name part switching will slow down the training process when set high)
    "augmentation": 0.2,

    # when resume is true: replace the first element of "lr-schedule" (the current lr) with the learning rate of the last checkpoint
    "resume": False
}

# DATASET CREATION:
#   - go into "preprocessing.py" and specify (in the "preprocess()" function call at the end of the file) which nationalities 
#     you want to use and what the name of the dataset should be

#   - run "python preprocessing.py", this will create a folder "datasets/preprocessed_datasets/<your-chosen-dataset-name>" in which
#     there are two files called "dataset.pickle" and "nationalities.json"


# TRAINING AND TESTING:

#   - in the config above change "model-name" to the name of this model/run/experiment 
#     (a descriptive name, e.g. "5_european_nat_and_else", it can also be the name as your dataset name)

#   - in the config above change "dataset-name" to the name of the dataset you want to use

#   - run (this file) "python train_model.py"

#   - when you break the training and want to start continue: copy the last learning-rate in the console (looks like this for example: "lr: 0.00095213")
#     and replace it with the first argument of "lr-schedule" in the config above, and set "resume" to "True"! 
#     (if you can't get the last learning-rate value you should start the training from the beginning)

#   - when you just want to test the model, comment out "train_setup.train()" and run this file

# train and test
train_setup = TrainSetup(model_config)
# train_setup.train()
train_setup.test(print_amount=50, plot_confusion_matrix=True, plot_scores=False)
