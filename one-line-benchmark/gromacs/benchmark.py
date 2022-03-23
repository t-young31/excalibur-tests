"""
Simple scaling benchmark using GROMACS
"""
import os
import pickle
import shutil
import numpy as np
import multiprocessing as mp

from typing import Optional, Tuple
from scipy.stats import linregress
from subprocess import Popen, PIPE


def run_subprocess(*args, print_error=True) -> Tuple[list, list]:
    """Run a subprocess and wait for the output"""

    print('Running: ', " ".join(args))
    process = Popen(args, stdout=PIPE, stderr=PIPE)
    bstdout, bstderr = process.communicate()

    stdout = [l.decode().strip() for l in bstdout.split(b'\n')]
    stderr = [l.decode().strip() for l in bstderr.split(b'\n')]

    for line in stderr:
        if print_error and len(line.split()) > 0:
            print('STDERR:', line)

    return stdout, stderr


def install_compiler(spec) -> None:

    run_subprocess('spack', 'compiler', 'find')
    stdout, _ = run_subprocess('spack', 'compilers')

    for line in stdout:
        if spec in line:
            return  # Found the correct compiler!

    run_subprocess('spack', 'install', spec)
    stdout, _ = run_subprocess('spack', 'location', '-i', spec)

    compiler_dir = stdout[0]
    run_subprocess('spack', 'compiler', 'find', compiler_dir)
    run_subprocess('spack', 'load', 'gcc@9.3.0')

    return None


class GROMACSBenchmark:

    def __init__(self, spec, n_cores):

        self.spec = spec
        self.n_cores = n_cores
        self.stdout = None
        self.stderr = None

    def __str__(self) -> str:
        return f'GROMACS_benchmark_{self.spec}_{self.n_cores}'

    def install(self) -> None:
        """Install and load a gromacs install. This will take some time!"""

        run_subprocess('spack', 'compiler', 'find')
        run_subprocess('spack', 'install', '--reuse', self.spec)

        return None

    def run(self) -> None:
        """Run the benchmark"""

        if self.gmx_path is None:
            print('WARNING: Failed to run benchmark. gmx_mpi not present')
            return None

        os.environ['OMP_NUM_THREADS'] = '2'
        n_tasks = self.n_cores//2

        self.stdout, self.stderr = run_subprocess(
            self.mpi_run_path, '-np', f'{n_tasks}', f'{self.gmx_path}',
            'mdrun', '-deffnm', 'benchmark'
        )

        return None

    @property
    def gmx_path(self) -> Optional[str]:
        """Path to the spack installed version of Gromacs"""
        stdout, _ = run_subprocess('spack', 'location', '-i', self.spec)

        if len(stdout) == 0 or 'error' in stdout[0]:
            return None

        return os.path.join(stdout[0], 'bin', 'gmx_mpi')

    @property
    def mpi_run_path(self) -> str:
        stdout, _ = run_subprocess('spack', 'location', '-i', 'openmpi')
        return os.path.join(stdout[0], 'bin', 'mpirun')

    @property
    def performance(self) -> Optional[float]:

        if self.stderr is None:
            print('WARNING: Failed to extract the performance. No stderr')
            return None

        for line in self.stderr:
            if 'Performance:' in line and len(line.split()) == 3:
                return float(line.split()[1])

        print('WARNING: Failed to extract the performance from stderr')
        return None

    @property
    def cache_exists(self) -> bool:
        return os.path.exists(f"{self}.p")

    def save(self) -> None:
        if self.performance is None:
            print('WARNING: Performance metric not found. Not saving')
            return

        return pickle.dump(self.__dict__, open(f'{self}.p', 'wb'))

    def load(self) -> None:
        self.__dict__.update(pickle.load(open(f'{self}.p', 'rb')))


class GROMACSBenchmarks(list):

    def __init__(self,
                 spack_spec: str,
                 n_cores:    range):
        """Construct a set of benchmarks parameterised by the total # cores"""
        super().__init__()

        for n in n_cores:
            self.append(GROMACSBenchmark(spack_spec, n_cores=n))

    def run(self) -> None:
        """Run all the benchmarks, first installing one of the specs"""

        if len(self) == 0:
            print('WARNING: Had no benchmarks to run')
            return

        self[0].install()

        for benchmark in self:
            if benchmark.cache_exists:
                benchmark.load()

            else:
                benchmark.run()
                benchmark.save()

        return None

    @staticmethod
    def deviation_from_linear(xs, ys) -> float:
        """
        Evaluate the deviation from a linear line that these set of points make
        """

        _xs = np.array([x for x, y in zip(xs, ys) if x and y])
        _ys = np.array([y for x, y in zip(xs, ys) if x and y])

        if len(ys) == 0:
            print('WARNING: No target y values were defined')
            return -1

        m, c, _, _, _ = linregress(_xs, _ys)

        return np.sqrt(np.mean(np.square(_ys - m*_xs + c)))

    def print_results(self) -> None:
        """Print the results of the benchmarks on each number of cores"""
        ns, perfs = [b.n_cores for b in self], [b.performance for b in self]

        print('-------------------------------------------------------------\n'
              'Raw results:\n'
              'Num cores    Performance (ns/day)')
        for total_n_cores, performance in zip(ns, perfs):
            print(f'{total_n_cores:<10}       {performance}')

        print('---------\n'
              f'Deviation from linear: {self.deviation_from_linear(ns, perfs)}')

        # TODO: Other metrics here e.g. comparison to other nodes

        print('-------------------------------------------------------------')
        return None


if __name__ == '__main__':

    print('Starting GROMACS benchmark...')

    install_compiler('gcc@9.3.0')
    benchmarks = GROMACSBenchmarks('gromacs@2019%gcc@9.3.0^openmpi@4.1.1',
                                   n_cores=range(4, mp.cpu_count(), 4))
    benchmarks.run()
    benchmarks.print_results()
