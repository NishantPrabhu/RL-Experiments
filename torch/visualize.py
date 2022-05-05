
import os
import cv2
import wandb
import torch
import pickle
import argparse 
import numpy as np
import torch.optim as optim
import torch.utils.data as data
import torch.nn.functional as F

from utils import *
from networks import *
from data_utils import *
from datetime import datetime as dt
from matplotlib import pyplot as plt
from matplotlib import animation as animation


def main(args):
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    states, actions = load_data(args.data_path)
    train_size = int(len(states) * args.train_split) 
    state_shape = states[0].shape
    
    test_states, test_actions = states[train_size:], actions[train_size:]
    test_dset = ExperienceDataset(test_states, test_actions)
    
    # To preserve RAM, delete copy of states and actions
    del states, actions
    
    # Dataloaders
    loader = data.DataLoader(
        test_dset,
        batch_size=args.batch_size,
        shuffle=False,
        drop_last=True,
        num_workers=args.num_workers
    )
    
    # Model initialization
    model = ViTModel(
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        num_actions=args.num_actions,
        patch_size=args.patch_size,
        model_dim=args.model_dim,
        in_channels=state_shape[-1],
        seqlen=(state_shape[0] // args.patch_size) * (state_shape[1] // args.patch_size),
        mlp_hidden_dim=args.mlp_hidden_dim,
        attn_dropout_rate=args.attn_dropout_rate
    ).to(device)
    
    # Load checkpoint 
    if args.load is not None:
        fp = os.path.join(args.load, 'ckpt.pth')
        if os.path.exists(fp):
            state = torch.load(fp, map_location=device)
            model.load_state_dict(state['model'])
        else:
            raise FileNotFoundError(f'Could not find ckpt.pkl at {args.load}')
        expt_dir = args.load
    else:
        print("{}[WARN] No checkpoint loaded! Using random parameters!{}".format(COLORS['red'], COLORS['end']))
        expt_dir = './test'
    
    os.makedirs(os.path.join(expt_dir, 'videos'), exist_ok=True)
    
    # Generate visualization frames
    meter = AvgMeter() 
    layer_id = args.num_layers - 1
    resolution = (state_shape[1], state_shape[0])
    fig, axarr = plt.subplots(1, args.num_heads+1, figsize=(5 * (args.num_heads+1), 5))
    img_list = []
    
    for step, batch in enumerate(loader):
        states, actions = batch 
        states, actions = states.to(device), actions.to(device)
        output, attn_probs = model(states)
        acc = output.argmax(-1).eq(actions).float().mean().item()
        meter.add({'accuracy': acc})
            
        temp_list = []
        for i in range(states.shape[0]):
            for j in range(args.num_heads+1):
                
                # In first frame show the observation
                if j == 0:
                    im = axarr[j].imshow(states[i, -1, :, :], cmap='gray')
                    axarr[j].axis('off')
                    
                # Then show the attention maps for each head
                else:
                    # The prob of a layer has shape (batch_size, num_heads, 442, 442)
                    # After the operation below, we have selected i-th sample, (j-1)-th head ...
                    # ... and attn probs corresponding to CLS token for remaining 441 tokens
                    attn_prob_full = attn_probs[layer_id][i, j-1, 0, 1:].detach().cpu().numpy().reshape((21, 21))
                    attn_prob_full = cv2.resize(attn_prob_full, resolution, cv2.INTER_AREA) 
                    min_attn, max_attn = attn_prob_full.min(), attn_prob_full.max()
                    
                    im = axarr[j].imshow(attn_prob_full, cmap='plasma', vmin=min_attn, vmax=max_attn)
                    axarr[j].axis('off')
                
                temp_list.append(im)
            img_list.append(temp_list)
            
        pbar(p=(step+1)/len(loader), msg=meter.msg())         
        
    anim = animation.ArtistAnimation(fig, img_list, interval=10000, blit=True)
    anim.save(os.path.join(expt_dir, 'videos', 'attn_viz.mp4'), fps=5)
    
    
if __name__ == '__main__':
    
    ap = argparse.ArgumentParser()
    ap.add_argument('--data_path', type=str, required=True)
    ap.add_argument('--num_actions', type=int, required=True)
    ap.add_argument('--load', type=str, default=None)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--train_split', type=float, default=0.8)
    ap.add_argument('--batch_size', type=int, default=256)
    ap.add_argument('--num_workers', type=int, default=4)
    ap.add_argument('--num_heads', type=int, default=1)
    ap.add_argument('--num_layers', type=int, default=4)
    ap.add_argument('--patch_size', type=int, default=4)
    ap.add_argument('--model_dim', type=int, default=512)
    ap.add_argument('--mlp_hidden_dim', type=int, default=2048)
    ap.add_argument('--attn_dropout_rate', type=float, default=0.1)
    args = ap.parse_args()
    
    main(args)