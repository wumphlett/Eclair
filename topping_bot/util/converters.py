from discord.ext.commands import Greedy


# custom converter since Greedy has no __name__ attribute, causing issues with documentation
class IndicesConverter(Greedy):
    def __init__(self, converter):
        self.__name__ = "List[int]"
        self.converter = converter
