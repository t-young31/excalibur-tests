import networkx as nx

config = {
    'apps':      ['gromacs', 'imb'],
    'clusters':  ['alaska', 'csd3'],
    'compilers': ['gcc9'],
    'mpi':       ['impi', ('openmpi', 'omp')]
}


def inject(network, filename, pattern='network'):

    return None


class Network(nx.Graph):

    def __init__(self):
        super().__init__()
        self.add_major_and_minor_nodes()
        self.add_connections()

    def add_major_and_minor_nodes(self) -> None:
        """Add nodes based on all the """

        for i, (major_node, sub_nodes) in enumerate(config.items()):
            self.add_node(f'{i}', name=major_node)

            for j, minor_node in enumerate(sub_nodes):
                self.add_node(f'{i}_{j}', aliases=tuple(minor_node))

        return None

    def add_connections(self) -> None:
        """Add connections between nodes depending if a link exists"""

        raise NotImplementedError


if __name__ == '__main__':

    inject(Network(), 'index.html')
