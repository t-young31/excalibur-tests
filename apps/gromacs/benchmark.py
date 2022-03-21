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


class DiRACTest(rfm.RegressionTest):

    num_total_cores = variable(int, loggable=True)
    num_omp_threads = variable(int, loggable=True)
    num_mpi_tasks = variable(int, loggable=True)
    num_mpi_tasks_per_node = variable(int, loggable=True)
    num_nodes = variable(int, loggable=True)

    @run_after('setup')
    def set_attributes_after_setup(self):
        """Set the required MPI and OMP ranks/tasks/threads"""

        self.num_mpi_tasks = max(self.num_total_cores//self.num_omp_threads, 1)

        try:
            cpus_per_node = self._current_partition.processor.num_cpus
            if cpus_per_node is None:
                raise AttributeError('Cannot determine the number of cores PP')

            self.num_nodes = math.ceil(self.num_mpi_tasks / cpus_per_node)

        except AttributeError:
            print('WARNING: Failed to determine the number of nodes required '
                  'defaulting to 1')
            self.num_nodes = 1

        self.num_mpi_tasks_per_node = math.ceil(self.num_mpi_tasks / self.num_nodes)
        self.num_tasks_per_node = self.num_mpi_tasks_per_node

        if self.num_total_cores // self.num_omp_threads == 0:
            print('WARNING: Had fewer total number of cores than the default '
                  f'number of OMP threads, using {self.num_total_cores} OMP '
                  f'threads')
            self.num_omp_threads = self.num_total_cores

        self.num_cpus_per_task = self.num_omp_threads
        self.variables = {
            'OMP_NUM_THREADS': f'{self.num_cpus_per_task}',
        }

        self.extra_resources = {
            'mpi': {'num_slots': self.num_mpi_tasks * self.num_cpus_per_task}
        }


# TODO: -----------------------------------------------------------------------


class GROMACSBenchmark(DiRACTest):
    """Base class for a GROMACS benchmark"""

    valid_systems = ['*']
    valid_prog_environs = ['*']
    executable = 'gmx_mpi'
    executable_opts = ['mdrun', '-deffnm', 'benchmark']
    build_system = 'Spack'
    time_limit = '60m'
    exclusive_access = True

    sourcesdir = this_dir
    readonly_files = ['benchmark.tpr']

    reference = {
        '*': {'Rate': (1, None, None, 'ns/day')}
    }

    @run_before('compile')
    def setup_build_system(self):
        """Set a specific version of GROMACS to use"""
        self.build_system.specs = ['gromacs@2019%gcc@9.3.0^openmpi@4.1.1']
        self.build_system.environment = spack_env_dir(self.current_system.name)

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
            'Rate': sn.extractsingle('Performance.+', self.stderr, 0,
                                     lambda x: float(x.split()[1]))
        }


@rfm.simple_test
class StrongScalingBenchmark(GROMACSBenchmark):

    variant = parameter([4 * i for i in range(5, 6)])
    num_omp_threads = 4

    @run_before('setup')
    def set_total_num_cores(self):
        """A ReFrame parameter cannot also be a variable, thus assign
        them to be equal at the start of the setup"""
        self.num_total_cores = self.variant
