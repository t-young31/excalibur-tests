import os
import json
import networkx as nx
from networkx.readwrite import json_graph

from typing import Tuple, Union


config = {
    'clusters': ['alaska', 'csd3'],
    'apps':      ['gromacs', 'imb'],
    'compilers': ['gcc9'],
    'mpi':       ['impi', ('ompi', ('openmpi', 'omp'))]
}


class Name:

    def __init__(self, value: Union[str, Tuple[str, Tuple]]):

        if isinstance(value, str):
            self.name = value
            self.aliases = (value,)

        else:
            self.name = value[0]
            self.aliases = value[1]

    def __str__(self):
        return self.name


class Network(nx.Graph):

    def __init__(self):
        super().__init__()
        self._config = {k: [Name(v) for v in vs] for k, vs in config.items()}

    def build(self) -> None:
        self._add_major_and_minor_nodes()
        self._add_connections()

        return None

    def save_json(self) -> None:
        """Save the json that's readable by D3"""

        data = json_graph.node_link_data(self)
        with open('assets/network.json', 'w') as f:
            json.dump(data, f, indent=2)

        return None

    def _add_major_and_minor_nodes(self) -> None:
        """Add nodes based on the global config"""

        for major_node, sub_nodes in self._config.items():
            self.add_node(major_node,
                          type='major')

            for minor_node in sub_nodes:
                self.add_node(minor_node.name,
                              type='minor',
                              aliases=minor_node.aliases)

        return None

    def _add_connections(self) -> None:
        """Add connections between nodes depending if a link exists"""

        for cluster_name in self._config['clusters']:

            folder_name = f'../perflogs/{cluster_name}'
            if not os.path.exists(folder_name):
                raise ValueError('Failed to find a directory for cluster:'
                                 f' {cluster_name}')

            folders_str = ".".join(os.listdir(folder_name))

            def add_edge(name):
                """Add an edge if there is a connection"""

                for alias in name.aliases:
                    if alias in folders_str:
                        self.add_edge(str(cluster_name), str(name))

                return None

            for compiler in self._config['compilers']:
                add_edge(compiler)

            for mpi in self._config['mpi']:
                add_edge(mpi)

        # TODO: Other connections
        return None

    def _add_attributes(self) -> None:
        """Add the required attribute"""

        for node in self.nodes:
            node['degree'] = self.neighbors(node)

        for ix, katz in nx.katz_centrality(self).items():
            self.nodes[ix]['katz'] = katz

        return None


if __name__ == '__main__':

    network = Network()
    network.build()
    network.save_json()
