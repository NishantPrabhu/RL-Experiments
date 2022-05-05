
import torch
import pickle 
from torch.utils import data

__all__ = ['load_data', 'ExperienceDataset']


def load_data(path):
    with open(path, 'rb') as f:
        data = pickle.load(f)
    states = data['states']
    actions = data['actions']
    del data 
    return states, actions 


class ExperienceDataset(data.Dataset):
    
    def __init__(self, states, actions):
        super().__init__()
        self.states = states 
        self.actions = actions 
        
    def __len__(self):
        return len(self.states)
    
    def __getitem__(self, idx):
        return (
            torch.from_numpy(self.states[idx] / 255.0).permute(2, 0, 1).contiguous().float(), 
            torch.tensor(self.actions[idx]).long()
        )