from enum import Enum
from typing import List, Type, Union

from discord import app_commands


class Autocomplete:
    def __init__(self, choices: Union[Type[Enum], List[str]]):
        if type(choices) == list:
            self.choices = choices
        else:
            self.choices = [choice.value for choice in choices]

    async def call(self, interaction, current: str):
        choices = [
            app_commands.Choice(name=choice, value=choice)
            for choice in self.choices
            if current.lower() in choice.lower()
        ]
        if len(choices) <= 25:
            return choices
        return []
