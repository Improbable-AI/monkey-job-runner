from argparse import ArgumentParser
from dataclasses import dataclass
from tqdm import tqdm
import monkey

import torch
from torch import nn, optim
import torch.nn.functional as F

from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
import torchvision as tv

@dataclass
class Config:
    num_epochs: int = 3
    hidden_size: int = 50
    optim_algo: optim.Optimizer = optim.Adam
    lr: float = 0.01
    batch_size_train: int = 64
    batch_size_test: int = 1000
    log_interval: int = 100

    def make_optimizer(self, parameters):
        return self.optim_algo(params=parameters, lr=self.lr)

class MnistNet(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 10, kernel_size=5),
            nn.MaxPool2d(kernel_size=2),
            nn.ReLU(),
            nn.Conv2d(10, 20, kernel_size=5),
            nn.MaxPool2d(kernel_size=2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(320, hidden_size),
            nn.ReLU(),
            nn.Dropout(p=0.5),
            nn.Linear(hidden_size, 10),
            nn.LogSoftmax(dim=1),
        )

    def forward(self, x):
        return self.net(x)

def train_net(net, optimizer, dataset, cfg, writer, seen):
    net.train()
    loader = DataLoader(dataset, batch_size=cfg.batch_size_train, shuffle=True)
    for idx, (X, y) in enumerate(loader):
        pred = net(X)
        loss = F.nll_loss(pred, y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        seen += X.shape[0]
        if idx % cfg.log_interval == 0:
            writer.add_scalar('loss/train', loss.item(), seen)
            writer.add_scalar('acc/train', torch.argmax(pred, dim=1).eq(y).float().mean(), seen)
    return seen

@torch.no_grad()
def test_net(net, dataset, cfg, writer, seen):
    net.eval()
    loader = DataLoader(dataset, batch_size=cfg.batch_size_test, shuffle=False)
    correct, tot_loss = 0, 0
    for X, y in loader:
        pred = net(X)
        tot_loss += F.nll_loss(pred, y, reduction='sum').item()
        correct += torch.argmax(pred, dim=1).eq(y).sum()

    writer.add_scalar('loss/test', tot_loss / len(dataset), seen)
    writer.add_scalar('acc/test', correct / len(dataset), seen)

def run(cfg, writer):
    transform = tv.transforms.Compose([
        tv.transforms.ToTensor(),
        tv.transforms.Normalize((0.1307,), (0.3081,)),
    ])
    datasets = {train: tv.datasets.MNIST(
                    'data',
                    train=train,
                    download=True,
                    transform=transform,
                ) for train in (False, True)}
    net = MnistNet(cfg.hidden_size)
    optimizer = cfg.make_optimizer(net.parameters())

    seen = 0
    for i in tqdm(range(cfg.num_epochs)):
        test_net(net, datasets[False], cfg, writer, seen)
        seen = train_net(net, optimizer, datasets[True], cfg, writer, seen)
    test_net(net, datasets[False], cfg, writer, seen)
    return net


if __name__ == '__main__':
    parser = ArgumentParser()
    for field, cls in Config.__annotations__.items():
        if cls in (bool, int, float):
            parser.add_argument('--'+field, type=cls, default=getattr(Config, field))

    monkey.init(parser.parse_args().__dict__)
    cfg = Config(**parser.parse_args().__dict__)

    writer = SummaryWriter()
    run(cfg, writer)
    writer.close()
