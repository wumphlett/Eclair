import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import seaborn as sns


sns.set_theme()
PALETTE = sns.color_palette("BuGn")


@FuncFormatter
def millions_formatter(x, pos):
    return f"{x / 1_000_000:,.1f}M"


@FuncFormatter
def thousands_formatter(x, pos):
    return f"{x / 1_000:,.1f}k"


def plot_hp(fp, hps):
    fig, ax = plt.subplots()

    ax = sns.lineplot(x=[p[0] for p in hps], y=[p[1] for p in hps], color="#84b677", ax=ax)

    ax.set(title="Guild Battle Boss HP per lvl", xlabel="Boss lvl", ylabel="Boss HP (Millions)")
    ax.yaxis.set_major_formatter(millions_formatter)

    fig.tight_layout()
    fig.savefig(fp)


def plot_trophy(fp, trophies):
    fig, ax = plt.subplots()

    ax = sns.lineplot(x=[p[0] for p in trophies], y=[p[1] for p in trophies], color="#84b677", ax=ax)

    ax.set(title="Guild Battle Boss Trophies per lvl", xlabel="Boss lvl", ylabel="Boss Trophies (Thousands)")
    ax.yaxis.set_major_formatter(thousands_formatter)

    fig.tight_layout()
    fig.savefig(fp)


def plot_eff(fp, effs):
    fig, ax = plt.subplots()

    ax = sns.lineplot(x=[p[0] for p in effs], y=[p[1] for p in effs], color="#84b677", ax=ax)

    ax.set(title="Guild Battle Boss Trophy/HP per lvl", xlabel="Boss lvl", ylabel="Boss Efficiency (Trophy/HP)")

    fig.tight_layout()
    fig.savefig(fp)
