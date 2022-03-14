"""
Strong scaling of GROMACS. Uses the benchmark simulation from
https://www.hecbiosim.ac.uk/access-hpc/benchmarks
"""
import os
import math
import reframe as rfm
import reframe.utility.sanity as sn
from abc import abstractmethod
from reframe.core.decorators import run_before, run_after

this_dir = os.path.dirname(__file__)

# TODO: Extract into installable module ---------------------------------------


def spack_env_dir(hostname):
    """
    Find the directory that holds a spack.yaml file appropriate for the
    current system (cluster).

    ---------------------------------------------------------------------------
    Args:
        hostname (str): Name of the host e.g. cosma8

    Returns:
        (str): Path to the spack env directory
    """

    dir_path = os.path.join(this_dir, '..', '..', 'spack-environments', hostname)

    if not (os.path.exists(dir_path) and os.path.isdir(dir_path)):
        raise RuntimeError('Failed to load a spack environment. Required a'
                           f'directory: {dir_path} that did not exist')

    return os.path.realpath(dir_path)


# TODO: -----------------------------------------------------------------------


class GROMACSBenchmark(rfm.RegressionTest):
    """Base class for a GROMACS benchmark"""

    valid_systems = ['*']
    valid_prog_environs = ['*']
    executable = 'gmx_mpi'
    executable_opts = ['mdrun', '-deffnm', 'benchmark']
    build_system = 'Spack'
    time_limit = '30m'
    exclusive_access = True

    sourcesdir = this_dir
    readonly_files = ['benchmark.tpr']

    reference = {
        '*': {'ns/day': (1, None, None, 's')}
    }

    @property
    @abstractmethod
    def _total_n_cores(self) -> int:
        """Total number of cores to use"""

    @property
    @abstractmethod
    def _num_omp_threads(self) -> int:
        """
        Number of omp threads to use. For example, num_cores=8,
        num_omp_threads=4 -> 2 MPI tasks each using 4 OMP threads
        """

    @run_before('compile')
    def setup_build_system(self):
        """Set a specific version of GROMACS to use"""
        self.build_system.specs = ['gromacs@2019%gcc@9.3.0^openmpi@4.1.1']
        self.build_system.environment = spack_env_dir(self.current_system.name)

    @run_after('setup')
    def set_attributes_after_setup(self):

        self.num_tasks = max(self._total_n_cores // self._num_omp_threads, 1)

        try:
            cpus_per_node = self._current_partition.processor.num_cpus
            num_nodes = math.ceil(self.num_tasks / cpus_per_node)

        except AttributeError:
            print('WARNING: Failed to determine the number of nodes required '
                  'defaulting to 1')
            num_nodes = 1

        self.num_tasks_per_node = math.ceil(self.num_tasks / num_nodes)

        if self._total_n_cores // self._num_omp_threads == 0:
            print('WARNING: Had fewer total number of cores than the default '
                  f'number of OMP threads, using {self._total_n_cores} OMP '
                  f'threads')
            self.num_cpus_per_task = self._total_n_cores
        else:
            self.num_cpus_per_task = self._num_omp_threads

        self.variables = {
            'OMP_NUM_THREADS': f'{self.num_cpus_per_task}',
        }

        self.extra_resources = {
            'mpi': {'num_slots': self.num_tasks * self.num_cpus_per_task}
        }

        self.tags |= {f'num_procs={self.num_tasks}', f'num_nodes={num_nodes}'}

    @run_before('sanity')
    def set_sanity_patterns(self):
        """Set the required string in the output for a sanity check"""
        self.sanity_patterns = sn.assert_found(
            'GROMACS reminds you', self.stderr
        )

    @run_before('performance')
    def set_perf_patterns(self):
        """Set the regex performance pattern to locate"""

        self.perf_patterns = {
            'ns/day': sn.extractsingle('Performance.+', self.stderr, 0,
                                       lambda x: float(x.split()[1]))
        }


@rfm.simple_test
class StrongScalingBenchmark(GROMACSBenchmark):

    variant = parameter([4*i for i in range(2, 7)])

    @property
    def _total_n_cores(self) -> int:
        return self.variant

    @property
    def _num_omp_threads(self) -> int:
        return 4
