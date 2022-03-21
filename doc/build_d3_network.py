import os
import json
import networkx as nx
from networkx.readwrite import json_graph

from typing import Tuple, Union, List


config = {
    'clusters':  ['csd3'],
    'apps':      ['gromacs'],
    'compilers': ['gcc9'],
    'mpi':       ['impi', ('ompi', ('openmpi', 'omp'))]
}

# Default hex values for tab colors from
# matplotlib: https://matplotlib.org/stable/gallery/color/named_colors.html
colors = ('#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
          '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')


# Long form descriptions of terms in config
descriptions = {
    'csd3':       'Cambridge Service for Data-Driven Discovery (<a href="https://www.hpc.cam.ac.uk/high-performance-computing">CSD3</a>)',
    'gromacs':    'A versatile package to perform molecular dynamics (<a href="https://www.gromacs.org/">GROMACS</a>).',
    'imb':        'Intel® MPI Benchmarks (<a href="https://www.intel.com/content/www/us/en/developer/articles/technical/intel-mpi-benchmarks.html">IMB-MPI</a>)',
    'gcc9':       'GNU Compiler Collection v9 (<a href="https://gcc.gnu.org/">GCC</a>)',
    'impi':       'Intel MPI (now <a href="https://www.intel.com/content/www/us/en/developer/tools/oneapi/mpi-library.html#gs.ttb1yo">oneAPI</a>)',
    'ompi':       '<a href="https://www.open-mpi.org/">OpenMPI</a>',
    'clusters':   'Compute clusters within the DiRAC consortium',
    'apps':       'Parallel applications',
    'compilers':  'Compilers',
    'mpi':        'Message passing interface implementations',
    'timeseries': 'Temporal relative regression of all benchmarks'
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
        """Build the network by adding nodes, edges then attributes of those"""

        self._add_time_series_node()
        self._add_major_and_minor_nodes()
        self._add_connections()
        self._add_attributes()

        return None

    def save_json(self) -> None:
        """Save the json that's readable by D3"""

        # JSON must have integer node names
        data = json_graph.node_link_data(
            nx.convert_node_labels_to_integers(self)
        )

        with open('assets/network.json', 'w') as f:
            json.dump(data, f, indent=2)

        return None

    @property
    def _major_nodes(self) -> List[str]:
        return list(self._config.keys())

    def _add_time_series_node(self) -> None:
        """Add a single node of the time series regression plot"""
        self.add_node('timeseries', name='timeseries')

    def _add_attributes(self) -> None:
        """Add the required attribute"""

        for node in self.nodes:
            self.nodes[node]['degree'] = len(list(self.neighbors(node)))

            if str(node) in descriptions:
                self.nodes[node]['desc'] = f'<p class="tiny">{descriptions[str(node)]}</p>'
            else:
                self.nodes[node]['desc'] = 'none'

        for ix, katz in nx.katz_centrality(self).items():
            self.nodes[ix]['katz'] = katz

        for (u, v) in self.edges:
            if u in self._major_nodes or v in self._major_nodes:
                self.edges[u, v]['type'] = 'major'
            else:
                self.edges[u, v]['type'] = 'minor'

        return None

    def _add_major_and_minor_nodes(self) -> None:
        """Add nodes based on the global config"""
        major_node_idx = 0

        for major_node, sub_nodes in self._config.items():

            self.add_node(major_node,
                          type='major',
                          name=str(major_node),
                          color=colors[major_node_idx])

            for minor_node in sub_nodes:

                self.add_node(minor_node.name,
                              name=str(minor_node),
                              type='minor',
                              aliases=minor_node.aliases,
                              color=colors[major_node_idx])

            major_node_idx += 1

        return None

    def _add_connections(self) -> None:
        """Add connections between nodes depending if a link exists"""

        self._add_major_to_minor_connections()
        self._add_cluster_connections()
        self._add_app_connections()

        # TODO: Other connections
        return None

    def _add_major_to_minor_connections(self) -> None:
        """Add connections for minor nodes from major categories"""

        for major_node, sub_nodes in self._config.items():
            for minor_node in sub_nodes:
                self.add_edge(str(major_node), str(minor_node))

        return None

    def _add_edge(self, u, v, folders_str):
        """Add an edge if there is a connection"""

        for alias in v.aliases:
            if alias in folders_str:
                self.add_edge(str(u), str(v))

        return None

    def _add_cluster_connections(self) -> None:
        """Add connections between specific cluster and compilers/mpi """

        for cluster_name in self._config['clusters']:

            folder_name = f'../perflogs/{cluster_name}'
            if not os.path.exists(folder_name):
                raise ValueError('Failed to find a directory for cluster:'
                                 f' {cluster_name}')

            folders_str = ".".join(os.listdir(folder_name))

            for compiler in self._config['compilers']:
                self._add_edge(cluster_name, compiler, folders_str)

            for mpi in self._config['mpi']:
                self._add_edge(cluster_name, mpi, folders_str)

        return None

    def _add_app_connections(self) -> None:
        """Add connections between specific application and compilers/mpi"""

        for app_name in self._config['apps']:
            folders_str = ''

            for cluster_name in self._config['clusters']:
                folder_name = f'../perflogs/{cluster_name}'
                folders_str += ".".join(os.listdir(folder_name))

            for compiler in self._config['compilers']:
                self._add_edge(app_name, compiler, folders_str)

            for mpi in self._config['mpi']:
                self._add_edge(app_name, mpi, folders_str)

        return None


if __name__ == '__main__':

    network = Network()
    network.build()
    network.save_json()
