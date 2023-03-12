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
- Fri Feb 14 12:00:00 2023
Aims
----
- KVXP training script
"""

import time
import os
import numpy as np
import torch
from torch.utils.data import DataLoader, SubsetRandomSampler
from sklearn.model_selection import KFold
from kvxp.xpformer import XPAPformer, XPAPformerConv, XPAPformerConv2
from kvxp.data import XPAP4l
from kvxp.utils import *


#==============================
#========== Hyper parameters
"""
traing params
"""

device = torch.device('cuda:0')
TOTAL_NUM = 200
BATCH_SIZE = int(2**12)
num_epochs = 500
part_train = False

"""
data params
"""
data_dir = "/data/jdli/gaia/"
# tr_file = "ap_xp_13286.npy"
# tr_file = "ap_xp_233985.npy"
# tr_file = "apspec_xp_173344.npy"
tr_file = "apspec_xp_173344.dump"
# tr_file = "apspec_xp_173344_apzero.dump"

"""
model params
"""
n_enc = 11
n_dim = 64
n_xp  = 110
n_ap  = 128
# n_cut = n_hi*n_dim + n_enc
n_outputs = 4
n_head =  8
n_layer = 8
LR_ = 1e-4
# LMBDA_PEN = 1e-10
# LMBDA_ERR = 1e-1
model_dir = "/data/jdli/gaia/model/0310_attnconv2/"
pre_trained = False
# loss_function = WeightedMSE(10.0)
loss_function = cost_mse

# tgt_mask = torch.triu(torch.ones(n_outputs, n_outputs), diagonal=1).bool().to(device)

# Check if the directory exists
if not os.path.exists(model_dir):
# Create the directory
    print("make dir %s"%model_dir)
    os.makedirs(model_dir)


#=======================Data loading===========================

gdata  = XPAP4l(data_dir+tr_file, device=device, part_train=False)
k_folds = 5
kfold = KFold(n_splits=k_folds, shuffle=True, random_state=42)

#========================= Model ==============================
def train_epoch(tr_loader, epoch):
        # model.train()
    model.train()
    total_loss = 0.0
    start_time = time.time()
    itr=0
    for _, data in enumerate(tr_loader):
        
        # x = data['x']
        y = data['y'][:,:n_outputs].view(-1,n_outputs)
        # output = model(x=x, src_mask=data['x_mask'])
        output = model(xp=data['xp'], ap=None, xp_mask=data['xp_mask'])
        # output = model(xp=data['xp'], ap=data['ap'], xp_mask=data['xp_mask'])
        # output = model(x=x)
        # loss = loss_function(output, y)
        loss = cost_mse_pen(output.view(-1,4), y, model, lbda=1e-5)
        # loss = cost_mse(output, y)

        loss_value = loss.item()
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_
        (model.parameters(), 0.5)
        optimizer.step()

        total_loss+=loss_value
        itr+=1
        del data, output

    print("epoch %d train loss:%.4f | %.4f s"%(epoch, total_loss/itr, time.time()-start_time))
    

def eval(val_loader, epoch):
    model.eval()
    total_val_loss=0
    itr=0

    with torch.no_grad():
        for batch, data in enumerate(val_loader):

            # x = data['x']
            y = data['y'][:,:n_outputs].view(-1,n_outputs)
            # output = model(x=x, src_mask=data['x_mask'])
            output = model(xp=data['xp'], ap=None, xp_mask=data['xp_mask'])
            # output = model(xp=data['xp'], ap=data['ap'], xp_mask=data['xp_mask'])
            # output = model(x=x)
            loss = cost_mse(output, y)

            total_val_loss+=loss.item()
            del data, output
            itr+=1

    print("val loss :%.4f"%(total_val_loss/itr))
    return total_val_loss/itr

#========================

print("Training Start: ")

for fold, (train_ids,valid_ids) in enumerate(kfold.split(gdata)):
    
    print(f'FOLD {fold}')
    print('--------------------------------')

    if fold==0:

        model = XPAPformerConv2(
            n_xp, n_ap, n_outputs, 
            device=device, channels=n_dim, 
        ).to(device)
        # model = CNN(n_xp, n_outputs).to(device)

        if pre_trained:
            pre_model_name = model_dir + "sp2_4l_%d_ep%d.pt"%(0,10)
            model.load_state_dict(
                remove_prefix(
                    torch.load(pre_model_name)
                )
            )
            print(f"loading pre-trained model {pre_model_name}")
        
        # freeze all self-attention layers in the TransformerEncoder
        # for name, param in model.encoder.named_parameters():
        #     if 'self_attn' in name:
        #         param.requires_grad = False

        # model = torch.compile(model)

        optimizer = torch.optim.Adam(
            model.parameters(), lr=LR_, weight_decay=1e-5
        )

        scheduler =  torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=10, verbose=True)

        train_subsampler = SubsetRandomSampler(train_ids)
        valid_subsampler = SubsetRandomSampler(valid_ids)
        
        tr_loader = DataLoader(gdata, batch_size=BATCH_SIZE, sampler=train_subsampler)
        val_loader = DataLoader(gdata, batch_size=BATCH_SIZE, sampler=valid_subsampler)

        for epoch in range(num_epochs+1):

            train_epoch(tr_loader, epoch)

            if epoch%5==0:
                val_loss = eval(val_loader, epoch)

            if epoch%50==0: 
                save_point = "xp2_4l_%d_ep%d.pt"%(fold, epoch)
                # save_point = "sp2_4l_%d_ep%d.pt"%(fold,epoch)
                torch.save(model.state_dict(), model_dir+save_point)

        del model