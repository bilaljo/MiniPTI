class Multiset:
    """
    This class implements multisets.
    """
    def __init__(self):
        self.__multiset = dict()

    def __setitem__(self, key, value):
        self.__multiset[key] = value

    def __getitem__(self, key):
        return self.__multiset[key]

    def insert(self, key):
        if key in self.__multiset:
            self.__multiset[key] += 1
        else:
            self.__multiset[key] = 1

    def __repr__(self):
        result = "{"
        for key in self.__multiset.keys():
            result += f"({key}, {self.__multiset[key]}), "
        return result[:len(result) - 2] + "}"

