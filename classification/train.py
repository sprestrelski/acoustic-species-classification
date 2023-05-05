# pytorch training
import torch
import torch.nn as nn
from torch.optim import Adam
import torch.nn.functional as F
import torchaudio 

import timm

# general
import argparse
import librosa
import os
import numpy as np

# logging
import wandb
import datetime
time_now  = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') 

# other files 
from dataset import BirdCLEFDataset, get_datasets
from model import BirdCLEFModel, GeM
from tqdm import tqdm
# # cmap metrics
# import pandas as pd
from sklearn.metrics import f1_score, average_precision_score

device = 'cuda' if torch.cuda.is_available() else 'cpu'

parser = argparse.ArgumentParser()
parser.add_argument('-e', '--epochs', default=10, type=int)
parser.add_argument('-nf', '--num_fold', default=5, type=int)
parser.add_argument('-nc', '--num_classes', default=264, type=int)
parser.add_argument('-tbs', '--train_batch_size', default=128, type=int)
parser.add_argument('-vbs', '--valid_batch_size', default=128, type=int)
parser.add_argument('-sr', '--sample_rate', default=32_000, type=int)
parser.add_argument('-hl', '--hop_length', default=512, type=int)
parser.add_argument('-mt', '--max_time', default=5, type=int)
parser.add_argument('-nm', '--n_mels', default=224, type=int)
parser.add_argument('-nfft', '--n_fft', default=1024, type=int)
parser.add_argument('-s', '--seed', default=0, type=int)
parser.add_argument('-j', '--jobs', default=4, type=int)
parser.add_argument('-l', '--logging', default='True', type=str)
parser.add_argument('-lf', '--logging_freq', default=20, type=int)
parser.add_argument('-vf', '--valid_freq', default=2000, type=int)


#https://www.kaggle.com/code/imvision12/birdclef-2023-efficientnet-training


def loss_fn(outputs, labels):
    return nn.CrossEntropyLoss()(outputs, labels)
    
def train(model, data_loader, optimizer, scheduler, device, step, best_valid_cmap, epoch):
    print('size of data loader:', len(data_loader))
    model.train()

    running_loss = 0
    log_n = 0
    log_loss = 0
    correct = 0
    total = 0

    for i, (mels, labels) in enumerate(data_loader):
        optimizer.zero_grad()
        mels = mels.to(device)
        labels = labels.to(device)
        
        outputs = model(mels)
        _, preds = torch.max(outputs, 1)
        
        loss = loss_fn(outputs, labels)
        
        loss.backward()
        optimizer.step()
        
        
        if scheduler is not None:
            scheduler.step()
            
        running_loss += loss.item()
        total += labels.size(0)
        correct += preds.eq(labels).sum().item()
        log_loss += loss.item()
        log_n += 1

        if i % (CONFIG.logging_freq) == 0 or i == len(data_loader) - 1:
            wandb.log({
                "train/loss": log_loss / log_n,
                "train/accuracy": correct / total * 100.,
                "custom_step": step
            })
            print("Loss:", log_loss / log_n, "Accuracy:", correct / total * 100.)
            log_loss = 0
            log_n = 0
            correct = 0
            total = 0
        
        if step % CONFIG.valid_freq == 0:
            del mels, labels, outputs, preds # clear memory
            valid_loss, valid_map = valid(model, val_dataloader, device, step)
            print(f"Validation Loss:\t{valid_loss} \n Validation mAP:\t{valid_map}" )
            if valid_map > best_valid_cmap:
                print(f"Validation cmAP Improved - {best_valid_cmap} ---> {valid_map}")
                torch.save(model.state_dict(), f'./model_{epoch}.pt')
                print(f"Saved model checkpoint at ./model_{epoch}.pt")
                best_valid_cmap = valid_map
            model.train()
        
        step += 1

    return running_loss/len(data_loader), step, best_valid_cmap

def valid(model, data_loader, device, step, pad_n=5):
    model.eval()
    
    running_loss = 0
    pred = []
    label = []
    
    dl = tqdm(data_loader, position=0)
    for i, (mels, labels) in enumerate(dl):
        mels = mels.to(device)
        labels = labels.to(device)
        
        outputs = model(mels)
        _, preds = torch.max(outputs, 1)
        
        loss = loss_fn(outputs, labels)
            
        running_loss += loss.item()
        
        # pred.extend(preds.view(-1).cpu().detach().numpy())
        # label.extend(labels.view(-1).cpu().detach().numpy())
        pred.append(outputs.cpu().detach())
        label.append(labels.cpu().detach())
        # break
    
    # try:
    #     pd.DataFrame(label).to_csv(f"{time_now}_{epoch}_labels.csv")
    #     pd.DataFrame(pred).to_csv(f"{time_now}_{epoch}_predictions.csv")
    # except:
    #     print("L your csv(s) died") 

    pred = torch.cat(pred)
    label = torch.cat(label)

    # convert to one-hot encoding
    label = F.one_hot(label, num_classes=CONFIG.num_classes).to(device)


    # softmax predictions
    pred = F.softmax(pred, dim=-1)

    # pad predictions and labels with `pad_n` true positives
    padded_preds = torch.cat([pred, torch.ones(pad_n, pred.shape[1]).to(pred.device)])
    padded_labels = torch.cat([label, torch.ones(pad_n, label.shape[1]).to(label.device)])

    # send to cpu
    padded_preds = padded_preds.detach().cpu().numpy()
    padded_labels = padded_labels.detach().cpu().numpy()

    # print(padded_preds.shape, padded_labels.shape)

    # calculate average precision
    valid_map = average_precision_score(
        padded_labels,
        padded_preds,
        average='macro',
    )

    # # convert probs to one-hot predictions

    # # calculate f1 score
    # valid_f1 = f1_score(
    #     padded_labels,
    #     padded_preds,
    #     average='macro',
    # )
    
    
    # valid_map = average_precision_score(label, pred, average='macro')
    # valid_f1 = f1_score(label, pred, average='macro')
    print("Validation mAP:", valid_map)
    # print("Validation F1:", valid_f1)

    wandb.log({
        "valid/loss": running_loss/len(data_loader),
        "valid/cmap": valid_map,
        # "valid/f1": valid_f1,
        "custom_step": step
    })
    
    return running_loss/len(data_loader), valid_map

def mAP(label, pred):
    # one hot encoding
    y_label = label_binarize(label, classes=range(len(target_names)))
    y_pred = label_binarize(pred, classes=range(len(target_names)))
    
    # tp/fp/precision
    true_pos = ((y_label == 1) & (y_pred == 1)).sum(axis=0)
    false_pos = ((y_label == 0) & (y_pred == 1)).sum(axis=0)
    precision = true_pos / (true_pos + false_pos)
    precision = np.nan_to_num(precision)
    num_species = precision.shape[0]
    return precision.sum() / num_species

def set_seed():
    np.random.seed(CONFIG.seed)
    torch.manual_seed(CONFIG.seed)

# def padded_cmap(solution, submission, padding_factor=5):
#     solution = solution.drop(['row_id'], axis=1, errors='ignore')
#     submission = submission.drop(['row_id'], axis=1, errors='ignore')
#     new_rows = []
#     for i in range(padding_factor):
#         new_rows.append([1 for i in range(len(solution.columns))])
#     new_rows = pd.DataFrame(new_rows)
#     new_rows.columns = solution.columns
#     padded_solution = pd.concat([solution, new_rows]).reset_index(drop=True).copy()
#     padded_submission = pd.concat([submission, new_rows]).reset_index(drop=True).copy()
#     score = sklearn.metrics.average_precision_score(
#         padded_solution.values,
#         padded_submission.values,
#         average='macro',
#     )
#     return score

def init_wandb(CONFIG):
    run = wandb.init(
        project="birdclef-2023",
        name=f"EFN-{CONFIG.epochs}-{CONFIG.train_batch_size}-{CONFIG.valid_batch_size}-{CONFIG.sample_rate}-{CONFIG.hop_length}-{CONFIG.max_time}-{CONFIG.n_mels}-{CONFIG.n_fft}-{CONFIG.seed}",
        config=CONFIG,
        mode="disabled" if CONFIG.logging == False else "online"
    )
    return run

if __name__ == '__main__':
    CONFIG = parser.parse_args()
    print(CONFIG)
    CONFIG.logging = True if CONFIG.logging == 'True' else False
    run = init_wandb(CONFIG)
    set_seed()
    print("Loading Model...")
    model = BirdCLEFModel(CONFIG=CONFIG).to(device)
    optimizer = Adam(model.parameters(), lr=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, eta_min=1e-5, T_max=10)
    print("Model / Optimizer Loading Succesful :P")

    print("Loading Dataset")
    train_dataset, val_dataset = get_datasets(CONFIG=CONFIG)
    train_dataloader = torch.utils.data.DataLoader(
        train_dataset,
        CONFIG.train_batch_size,
        shuffle=True,
        num_workers=CONFIG.jobs
    )
    val_dataloader = torch.utils.data.DataLoader(
        val_dataset,
        CONFIG.valid_batch_size,
        shuffle=False,
        num_workers=CONFIG.jobs
    )
    
    print("Training")
    step = 0
    best_valid_cmap = 0

    for epoch in range(CONFIG.epochs):
        print("Epoch " + str(epoch))

        train_loss, step, best_valid_cmap = train(
            model, 
            train_dataloader,
            optimizer,
            scheduler,
            device,
            step,
            best_valid_cmap,
            epoch
        )
        valid_loss, valid_map = valid(model, val_dataloader, device, step)
        print(f"Validation Loss:\t{valid_loss} \n Validation mAP:\t{valid_map}" )
        if valid_map > best_valid_cmap:
            print(f"Validation cmAP Improved - {best_valid_cmap} ---> {valid_map}")
            torch.save(model.state_dict(), f'./model_{epoch}.pt')
            print(f"Saved model checkpoint at ./model_{epoch}.pt")
            best_valid_cmap = valid_map

    print(":o wow")