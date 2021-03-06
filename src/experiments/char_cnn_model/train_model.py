""" file to train and evaluate the model """

from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
import os
import json

import torch
import torch.utils.data
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence

from model import CnnLSTM as Model
from utils import create_dataloader, show_progress, onehot_to_string, init_xavier_weights, device, char_indices_to_string
from test_metrics import validate_accuracy, create_confusion_matrix, recall, precision, f1_score, score_plot
import xman

import wandb

torch.manual_seed(0)


with open("../../datasets/preprocessed_datasets/no_else_english_once/nationality_to_number_dict.json", "r") as f: classes = json.load(f) 
total_classes = len(classes)


class Run:
    def __init__(self, model_file: str="", dataset_path: str="", epochs: int=10, lr: float=0.001, lr_schedule: tuple=None, batch_size: int=32, \
                 cnn_params: tuple=(3, 3, [32, 64, 128]), hidden_size: int=10, rnn_layers: int=1, dropout_chance: float=0.5, \
                 embedding_size: int=64, augmentation: float=0.0, continue_: bool=False):

        self.model_file = model_file
        self.dataset_path = dataset_path

        self.epochs = epochs
        self.lr = lr
        self.lr_decay_rate = lr_schedule[0]
        self.lr_decay_intervall = lr_schedule[1]

        self.batch_size = batch_size
        self.kernel_size = cnn_params[1]
        self.channels = cnn_params[2]
        self.hidden_size = hidden_size 
        self.rnn_layers = rnn_layers
        self.dropout_chance = dropout_chance
        self.embedding_size = embedding_size

        self.augmentation = augmentation

        self.train_set, self.validation_set, self.test_set = create_dataloader(dataset_path=self.dataset_path, test_size=0.05, val_size=0.05, \
                                    batch_size=batch_size, class_amount=total_classes, augmentation=self.augmentation)

        self.config = {
                        "optimizer": "Adam",
                        "loss-function": "NLLLoss",
                        "init-learning-rate": 0.0035,
                        "batch-size": self.batch_size,
                        "cnn-layers": cnn_params[0],
                        "cnn-channels": self.channels,
                        "kernel-size": self.kernel_size,
                        "hidden-size": self.hidden_size, 
                        "rnn-layers": self.rnn_layers,
                        "decay-rate": self.lr_decay_rate,
                        "decay-intervall": self.lr_decay_intervall,
                        "dropout-chance": self.dropout_chance,
                        "embedding-size": self.embedding_size,
                        "augmentation": self.augmentation
                        }

        self.continue_ = continue_

        # initialize experiment manager
        self.xmanager = xman.ExperimentManager(experiment_name="experiment9_1cnn_noelse", continue_=self.continue_)
        self.xmanager.init(optimizer="Adam", 
                            loss_function="NLLLoss", 
                            epochs=self.epochs, 
                            learning_rate=self.lr, 
                            batch_size=self.batch_size,
                            custom_parameters=self.config)

    def _validate(self, model, dataset, confusion_matrix: bool=False, plot_scores: bool=False):
        validation_dataset = dataset

        criterion = nn.NLLLoss()
        losses = []
        total_targets, total_predictions = [], []

        for names, targets, _ in tqdm(validation_dataset, desc="validating", ncols=150):
            names = names.to(device=device)
            targets = targets.to(device=device)

            predictions = model.eval()(names)
            loss = criterion(predictions, targets.squeeze())
            losses.append(loss.item())

            for i in range(predictions.size()[0]):
                target_index = targets[i].cpu().detach().numpy()[0]

                prediction = predictions[i].cpu().detach().numpy()
                prediction_index = list(prediction).index(max(prediction))

                total_targets.append(target_index)
                total_predictions.append(prediction_index)

        # calculate loss
        loss = np.mean(losses)

        # calculate accuracy
        accuracy = validate_accuracy(total_targets, total_predictions, threshold=0.4)

        # calculate precision, recall and F1 scores
        precision_scores = precision(total_targets, total_predictions, classes=total_classes)
        recall_scores = recall(total_targets, total_predictions, classes=total_classes)
        f1_scores = f1_score(precision_scores, recall_scores)

        # create confusion matrix
        if confusion_matrix:
            create_confusion_matrix(total_targets, total_predictions, classes=classes)
        
        if plot_scores:
            score_plot(precision_scores, recall_scores, f1_scores, classes)

        return loss, accuracy, (precision_scores, recall_scores, f1_scores)

    def train(self):
        wandb.init(project="name-ethnicity-classification", entity="theodorp", id="1obco9ed", resume=self.continue_, config=self.config)

        model = Model(class_amount=total_classes, hidden_size=self.hidden_size, layers=self.rnn_layers, dropout_chance=self.dropout_chance, \
                      embedding_size=self.embedding_size, kernel_size=self.kernel_size, channels=self.channels).to(device=device)

        if self.continue_:
            model.load_state_dict(torch.load(self.model_file))

        wandb.watch(model)

        criterion = nn.NLLLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr, weight_decay=1e-5)

        iterations = 0
        train_loss_history, train_accuracy_history, val_loss_history, val_accuracy_history = [], [], [], []
        for epoch in range(1, (self.epochs + 1)):

            total_train_targets, total_train_predictions = [], []
            epoch_train_loss = []
            for names, targets, _ in tqdm(self.train_set, desc="epoch", ncols=150):
                optimizer.zero_grad()

                names = names.to(device=device)
                targets = targets.to(device=device)
                predictions = model.train()(names)

                loss = criterion(predictions, targets.squeeze())
                loss.backward()
                optimizer.step()

                # log train loss
                epoch_train_loss.append(loss.item())
                
                # log targets and prediction of every iteration to compute the train accuracy later
                validated_predictions = model.eval()(names)
                for i in range(validated_predictions.size()[0]): 
                    total_train_targets.append(targets[i].cpu().detach().numpy()[0])
                    validated_prediction = validated_predictions[i].cpu().detach().numpy()
                    total_train_predictions.append(list(validated_prediction).index(max(validated_prediction)))
                
                iterations += 1

                # warm up training by increasing the learning rate
                """if iterations % 100 == 0 and optimizer.param_groups[0]["lr"] < 0.003:
                    optimizer.param_groups[0]["lr"] = optimizer.param_groups[0]["lr"] * 1.1
                    print("\n{0:f}".format(optimizer.param_groups[0]["lr"]))"""
                
                # decay
                if iterations % self.lr_decay_intervall == 0:
                    # wandb.log({"learning rate": optimizer.param_groups[0]["lr"]})
                    optimizer.param_groups[0]["lr"] = optimizer.param_groups[0]["lr"] * self.lr_decay_rate

            # calculate train loss and accuracy of last epoch
            epoch_train_loss = np.mean(epoch_train_loss)
            epoch_train_accuracy = validate_accuracy(total_train_targets, total_train_predictions, threshold=0.4)

            # calculate validation loss and accuracy of last epoch
            epoch_val_loss, epoch_val_accuracy, _ = self._validate(model, self.validation_set)

            # log training stats
            train_loss_history.append(epoch_train_loss); train_accuracy_history.append(epoch_train_accuracy)
            val_loss_history.append(epoch_val_loss); val_accuracy_history.append(epoch_val_accuracy)

            # print training stats in pretty format
            show_progress(self.epochs, epoch, epoch_train_loss, epoch_train_accuracy, epoch_val_loss, epoch_val_accuracy)
            print("\nlr: ", optimizer.param_groups[0]["lr"], "\n")

            # save checkpoint of model
            torch.save(model.state_dict(), self.model_file)

            # log with wandb
            wandb.log({"validation-accuracy": epoch_val_accuracy, "validation-loss": epoch_val_loss, "train-accuracy": epoch_train_accuracy, "train-loss": epoch_train_loss})
            os.path.join(wandb.run.dir, "model2.pt")

            # log epoch results with xman (uncomment if you have the xman libary installed)
            self.xmanager.log_epoch(model, self.lr, self.batch_size, epoch_train_accuracy, epoch_train_loss, epoch_val_accuracy, epoch_val_loss)

        # plot train-history with xman (uncomment if you have the xman libary installed)
        self.xmanager.plot_history(save=True)

    def test(self, print_: bool=True):
        model = Model(class_amount=total_classes, hidden_size=self.hidden_size, layers=self.rnn_layers, dropout_chance=0.0, \
                      embedding_size=self.embedding_size, kernel_size=self.kernel_size, channels=self.channels).to(device=device)

        model.load_state_dict(torch.load(self.model_file))

        _, accuracy, scores = self._validate(model, self.test_set, confusion_matrix=True, plot_scores=True)
        print("\n\ntest accuracy:", accuracy)

        for names, targets, non_padded_names in tqdm(self.test_set, desc="epoch", ncols=150):
            names = names.to(device=device)
            targets = targets.to(device=device)

            predictions = model.eval()(names)
            predictions, targets, names = predictions.cpu().detach().numpy(), targets.cpu().detach().numpy(), names.cpu().detach().numpy()

            try:
                for idx in range(len(names)):
                    names, prediction, target, non_padded_name = names[idx], predictions[idx], targets[idx], non_padded_names[idx]

                    # convert to one-hot target
                    amount_classes = prediction.shape[0]
                    target_empty = np.zeros((amount_classes))
                    target_empty[target] = 1
                    target = target_empty

                    # convert log-softmax to one-hot
                    prediction = list(np.exp(prediction))
                    certency = np.max(prediction)
                    
                    prediction = [1 if e == certency else 0 for e in prediction]
                    certency = round(certency * 100, 4)

                    target_class = list(target).index(1)
                    target_class = list(classes.keys())[list(classes.values()).index(target_class)]
                    
                    try:
                        # catch, if no value is above the threshold (if used)

                        predicted_class = list(prediction).index(1)
                        predicted_class = list(classes.keys())[list(classes.values()).index(predicted_class)]
                    except:
                        predicted_class = "else"
    
                    if print_:
                        names = char_indices_to_string(char_indices=non_padded_name)
    
                        print("\n______________\n")
                        print("name:", names)
        
                        print("predicted as:", predicted_class, "(" + str(certency) + "%)")
                        print("actual target:", target_class)
            except:
                pass

        precisions, recalls, f1_scores = scores
        print("\n\ntest accuracy:", accuracy)
        print("\nprecision of every class:", precisions)
        print("\nrecall of every class:", recalls)
        print("\nf1-score of every class:", f1_scores)



run = Run(model_file="models/model9.pt",
            dataset_path="../../datasets/preprocessed_datasets/no_else_english_once/matrix_name_list.pickle",
            epochs=20,
            # hyperparameters
            lr=0.0003,
            lr_schedule=(0.985, 105),
            batch_size=1000,
            hidden_size=200,
            rnn_layers=2,
            dropout_chance=0.3,
            embedding_size=200,
            # cnn_params=(3, 3, [32, 64, 128]),
            cnn_params=(1, 3, [64]),
            augmentation=0.9,
            continue_=True)


run.train()
run.test(print_=True)


