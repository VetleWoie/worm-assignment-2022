from matplotlib import pyplot as plt
import pandas
import numpy as np

def plot_spawn_worm():
    data = pandas.read_csv("./spawn_worm_1330.data", header=None).values
    x = data[:,0]
    y = data[:,1:]
    y_mean = np.mean(y, axis=1)
    y_std = np.std(y, axis=1)
    fig, ax = plt.subplots(1,1)
    print(len(x))
    ax.plot(x,y_mean, label = f"Avarage Time over {y.shape[1]} runs")
    ax.plot(x,y_mean+y_std, label = f"Avarage Time plus/minus standard deviation", color='green')
    ax.plot(x,y_mean-y_std, color='green')

    ax.set_xlabel("Number of nodes(n)")
    ax.set_ylabel("Time(ns)")
    ax.set_title("Time to scale system from $1\\to n$ nodes")
    ax.legend()
    plt.savefig("spawn_worms.png")

def plot_kill_worm():
    pass

if __name__ == '__main__':
    plot_spawn_worm()