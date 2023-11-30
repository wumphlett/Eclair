import pickle

from discord.ext.commands import CommandOnCooldown, Cooldown

from topping_bot.util.const import TMP_PATH


class CooldownManager:
    def __init__(self, rate: int, per: float, fp_name):
        self.rate = rate
        self.per = per

        self.fp = TMP_PATH / f"{fp_name}.pkl"
        if self.fp.exists():
            try:
                with open(self.fp, "rb") as f:
                    self.state = pickle.load(f)
            except:
                self.state = {}
        else:
            self.state = {}

    def update_rate_limit(self, key):
        if key not in self.state:
            self.state[key] = Cooldown(rate=self.rate, per=self.per)

        if retry_after := self.state[key].update_rate_limit():
            raise CommandOnCooldown(self.state[key], retry_after=retry_after, type=None)

    def reset(self):
        for cooldown in self.state.values():
            cooldown.reset()

    def save(self):
        with open(self.fp, "wb") as f:
            pickle.dump(self.state, f)


PULL_USER_1_PER_3S = CooldownManager(1, 3, "1p3")
PULL_MEMBER_5_PER_DAY = CooldownManager(5, 86_400, "5pd")
PULL_USER_50_PER_DAY = CooldownManager(50, 86_400, "50pd")
