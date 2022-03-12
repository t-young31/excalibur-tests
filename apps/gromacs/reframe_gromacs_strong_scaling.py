"""
Strong scaling of GROMACS. Uses the benchmark simulation from
https://www.hecbiosim.ac.uk/access-hpc/benchmarks
"""
import os
import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.decorators import run_before

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

    def __init__(self,
                 num_cores:       int,
                 num_omp_threads: int = 4
                 ):
        """
        Base class for a GROMACS benchmark

        -----------------------------------------------------------------------
        Args:
            num_cores: Total number of cores to use

            num_omp_threads: Number of omp threads to use. For example,
                             num_cores=8, num_omp_threads=4 -> 2 MPI tasks each
                             using 4 OMP threads
        """
        super().__init__()

        self.num_tasks = max(num_cores//num_omp_threads, 1)
        self.num_tasks_per_node = self.num_tasks

        # print(dir(self.current_partition))
        # print(self.current_partition.num_cores)
        # TODO: How to get the maximum number of cores on this system

        if num_cores // num_omp_threads == 0:
            print('WARNING: Had fewer total number of cores than the default '
                  f'number of OMP threads, using {num_cores} OMP threads')
            self.num_cpus_per_task = num_cores
        else:
            self.num_cpus_per_task = num_omp_threads

        self.variables = {
            'OMP_NUM_THREADS': f'{self.num_cpus_per_task}',
        }

        self.extra_resources = {
            'mpi': {'num_slots': self.num_tasks * self.num_cpus_per_task}
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
            'ns/day': sn.extractsingle('Performance.+', self.stderr, 0,
                                       lambda x: float(x.split()[1]))
        }


@rfm.simple_test
class TestCase(GROMACSBenchmark):

    def __init__(self):
        super().__init__(num_cores=16)
