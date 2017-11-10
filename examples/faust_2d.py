from __future__ import division, print_function

import sys
import time

import torch
from torch import nn
import torch.nn.functional as F
from torch.autograd import Variable

sys.path.insert(0, '.')
sys.path.insert(0, '..')
from torch_geometric.datasets import FAUSTPatch  # noqa
from torch_geometric.utils import DataLoader  # noqa
from torch_geometric.nn.modules import SplineGCN, Lin  # noqa

path = '~/MPI-FAUST'
train_dataset = FAUSTPatch(path, train=True, shot=True, correspondence=True)
test_dataset = FAUSTPatch(path, train=False, shot=True, correspondence=True)

train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=1, shuffle=True)


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.lin = Lin(544, 16)
        self.conv1 = SplineGCN(16, 32, dim=2, kernel_size=5)
        self.conv2 = SplineGCN(32, 64, dim=2, kernel_size=5)
        self.conv3 = SplineGCN(64, 128, dim=2, kernel_size=5)
        self.lin1 = Lin(128, 256)
        self.lin2 = Lin(256, 6890)

    def forward(self, adj, x):
        x = F.elu(self.lin(x))
        x = F.elu(self.conv1(adj, x))
        x = F.elu(self.conv2(adj, x))
        x = F.elu(self.conv3(adj, x))
        x = F.elu(self.lin1(x))
        x = F.dropout(x, training=self.training)
        x = self.lin2(x)
        return F.log_softmax(x)


model = Net()
if torch.cuda.is_available():
    model.cuda()

optimizer = torch.optim.Adam(model.parameters(), lr=0.01)


def train(epoch):
    model.train()

    if epoch == 61:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.001

    if epoch == 121:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.0001

    for batch, ((input, (adj, _), _), target) in enumerate(train_loader):
        if torch.cuda.is_available():
            input, adj, target, = input.cuda(), adj.cuda(), target.cuda()

        input, target = Variable(input), Variable(target)

        optimizer.zero_grad()
        output = model(adj, input)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()

        print('Epoch:', epoch, 'Batch:', batch, 'Loss:', loss.data[0])


def test():
    model.eval()

    acc_0 = acc_1 = acc_2 = acc_4 = acc_6 = acc_8 = acc_10 = 0

    for (input, (adj, _), _), target, distance in test_loader:
        if torch.cuda.is_available():
            input, adj = input.cuda(), adj.cuda()
            target, distance = target.cuda(), distance.cuda()

        input = Variable(input)

        output = model(adj, input)
        pred = output.data.max(1)[1]
        geodesic_error = distance[pred, target]
        acc_0 += (geodesic_error <= 0.0000002).sum()
        acc_1 += (geodesic_error <= 0.01).sum()
        acc_2 += (geodesic_error <= 0.02).sum()
        acc_4 += (geodesic_error <= 0.04).sum()
        acc_6 += (geodesic_error <= 0.06).sum()
        acc_8 += (geodesic_error <= 0.08).sum()
        acc_10 += (geodesic_error <= 0.1).sum()

    print('Accuracy 0:', acc_0 / (20 * 6890))
    print('Accuracy 1:', acc_1 / (20 * 6890))
    print('Accuracy 2:', acc_2 / (20 * 6890))
    print('Accuracy 4:', acc_4 / (20 * 6890))
    print('Accuracy 6:', acc_6 / (20 * 6890))
    print('Accuracy 8:', acc_8 / (20 * 6890))
    print('Accuracy 10:', acc_10 / (20 * 6890))


for epoch in range(1, 151):
    train(epoch)
    test()