class Multiset:
    """
    This class implements multisets. A multiset reprents a set that can contain the same element more than once.
    Multisets are implemented as hash tables here where the key is the actual element and the value its count.

    Attributes:
        __multiset: dict
        The actual multiset
    """
    def __init__(self, value):
        self.__multiset = dict(value)

    def __setitem__(self, key, value):
        self.__multiset[key] = value

    def __getitem__(self, key):
        return self.__multiset[key]

    def __repr__(self):
        result = "{"
        for key in self.__multiset.keys():
            result += f"({key}, {self.__multiset[key]}), "
        return result[:len(result) - 2] + "}"

    def insert(self, key):
        """
        Inserts a new item into the multiset. We have to increase the counter of the element if it already exists.
        Args:
            key: any
            The element for the multiset
        """
        if key in self.__multiset:
            self.__multiset[key] += 1
        else:
            self.__multiset[key] = 1
