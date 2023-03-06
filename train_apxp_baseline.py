# -*- coding: utf-8 -*-
"""
Author
------
JDL
Email
-----
jiadong.li at nyu.edu
Created on
----------
- Fri Jan 31 12:00:00 2023
Modifications
-------------
- Fri Mar 6 12:00:00 2023
Aims
----
- specformer model script
"""


import time
import os
import torch
from torch.utils.data import DataLoader, SubsetRandomSampler
from sklearn.model_selection import KFold
from kvxp.xpformer import XPformer2
from kvxp.data import GXP_AP_4lb
from kvxp.utils import *

##==================Model ======================================

def train_epoch(tr_loader, epoch, model, opt1, data_type='ap'):
    model.train()
    total_loss = 0.0
    start_time = time.time()
    itr=0
    for batch, data in enumerate(tr_loader):

        if data_type == 'ap':
            x = data['x'][:, n_xp:n_xp+938*8]
            x = x.reshape(-1,938,8)

        elif data_type == 'xp':
            x = data['x'][:, :n_xp]

        y = model(x)
        loss1 = cost_mse(y.view(-1,4), data['y'].view(-1,4))

        loss_value = loss1.item()
        opt1.zero_grad()
        loss1.backward()
        opt1.step()
        total_loss+=loss_value
        itr+=1

    print("epoch %d train loss:%.4f | %.4f s"%(epoch, total_loss/itr, time.time()-start_time))
    

def eval(val_loader, epoch, model, data_type='ap'):
    model.eval()
    total_val_loss=0
    itr=0
    # with torch.no_grad():
    for batch, data in enumerate(val_loader):

        if data_type == 'ap':
            x = data['x'][:, n_xp:n_xp+938*8]
            x = x.reshape(-1,938,8)

        elif data_type == 'xp':
            x = data['x'][:, :n_xp]

        y = model(x)
        loss1 = cost_mse(y.view(-1,4), data['y'].view(-1,4))
        loss_value = loss1.item()
        total_val_loss+=loss_value
        itr+=1

    print("val loss:%.4f"%(total_val_loss/itr))
    return total_val_loss/itr


if __name__ == "__main__":

    #==============================
    #========== Hyper parameters
    """
    traing params
    """
    band = "xp"
    mask_band = "ap"
    device = torch.device('cuda:0')
    BATCH_SIZE = int(2**8)
    num_epochs = 1000
    part_train = False

    """
    data params
    """
    data_dir = "/data/jdli/gaia/"
    tr_file = "ap_xp_13286.npy"
    """
    model params
    """

    # INPUT_LEN = 110
    n_xp = 110
    # n_ap = 7514
    n_ap = 7512
    n_labels = 4
    # LR = 5e-5
    LR_ = 5e-4
    loss_penal = 2
    LMBDA_PEN = 1e-10
    LMBDA_ERR = 1e-1
    
    # model_dir = f"/data/jdli/gaia/model/0220/"
    model_dir = f"/data/jdli/gaia/model/0306/"
    save_preflix = f"ap2_4l_%d_ep%d.pt"

    # Check if the directory exists
    if not os.path.exists(model_dir):
    # Create the directory
        print("make dir %s"%model_dir)
        os.makedirs(model_dir)
    else:
        print(f"save trained-model to {model_dir}")

    #=========================Data loading ================================
    gdata  = GXP_AP_4lb(
        data_dir+tr_file,
        part_train=part_train, 
        device=device,
    )
    k_folds = 5
    kfold = KFold(n_splits=k_folds, shuffle=True, random_state=42)
    #======================================================================


    print("Training Start :================")     

    for fold, (train_ids, valid_ids) in enumerate(kfold.split(gdata)):
        
        print(f'FOLD {fold}')
        print('--------------------------------')

        if fold==0:

            # model = MLP(n_xp, n_labels, hidden_size=128).to(device)
            # model = MLP(n_ap, n_labels, hidden_size=256).to(device)
            model = XPformer2(938, n_labels, device=device, input_proj=False).to(device)

            optimizer = torch.optim.Adam(
                model.parameters(), lr=LR_, weight_decay=1e-7
            )

            train_subsampler = SubsetRandomSampler(train_ids)
            valid_subsampler = SubsetRandomSampler(valid_ids)
            
            tr_loader = DataLoader(gdata, batch_size=BATCH_SIZE, sampler=train_subsampler)
            val_loader = DataLoader(gdata, batch_size=BATCH_SIZE, sampler=valid_subsampler)

            for epoch in range(num_epochs+1):
                train_epoch(tr_loader, epoch, model, optimizer)

                if epoch%5==0:
                    val_loss = eval(val_loader, epoch, model)

                if epoch%50==0: 
                    save_point = save_preflix%(fold, epoch)
                    torch.save(model.state_dict(), model_dir+save_preflix%(fold, epoch))