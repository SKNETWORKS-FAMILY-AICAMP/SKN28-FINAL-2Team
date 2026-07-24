from __future__ import annotations


class DisjointSet:
    """Track connected components with path compression and union by rank."""

    def __init__(self, size: int) -> None:
        if size < 0:
            raise ValueError("size must not be negative")
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, value: int) -> int:
        while self._parent[value] != value:
            self._parent[value] = self._parent[self._parent[value]]
            value = self._parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._rank[left_root] < self._rank[right_root]:
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root
        if self._rank[left_root] == self._rank[right_root]:
            self._rank[left_root] += 1
