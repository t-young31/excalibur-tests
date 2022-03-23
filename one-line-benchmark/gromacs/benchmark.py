"""
Simple scaling benchmark using GROMACS
"""
import os
import pickle
import numpy as np
import multiprocessing as mp

from typing import Optional
from scipy.stats import linregress
from subprocess import Popen, PIPE


def run_subprocess(*args, print_error=True):
    """Run a subprocess and wait for the output"""

    process = Popen(args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = [], []

    with process.stderr:
        for line in iter(process.stderr.readline, b''):
            if print_error:
                print('STDERR: %r', line.decode())
            else:
                stderr.append(line.decode())

    with process.stdout:
        for line in iter(process.stdout.readline, b''):
            stdout.append(line.decode())

    process.wait()
    return stdout, stderr


class GROMACSBenchmark:

    def __init__(self, spec, n_cores):

        self.spec = spec
        self.n_cores = n_cores
        self.stdout = None
        self.stderr = None

    def __str__(self):
        return f'GROMACS_benchmark_{self.spec}_{self.n_cores}'

    def install(self):
        """Install and load a gromacs install. This will take some time!"""

        run_subprocess('spack', 'install', self.spec)
        run_subprocess('spack', 'load', self.spec)

        return None

    def run(self):
        """Run the benchmark"""

        os.environ['OMP_NUM_THREADS'] = '2'
        n_tasks = self.n_cores//2

        self.stdout, self.stderr = run_subprocess(
            'mpirun', f'-np {n_tasks}' 'gmx_mpi', 'mdrun', '-deffnm benchmark'
        )

        return None

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

    def save(self):
        return pickle.dump(self.__dict__, open(f'{self}.p', 'wb'))

    def load(self):
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
        xs, ys = np.array(xs), np.array(ys)
        m, c, _, _, _ = linregress(xs, ys)

        return np.sqrt(np.mean(np.square(ys - m*xs + c)))

    def print_results(self) -> None:
        """Print the results of the benchmarks on each number of cores"""
        ns, perfs = [b.n_cores for b in self], [b.performance for b in self]

        print('-------------------------------------------------------------\n'
              'Raw results:\n'
              'Num cores    Performance (ns/day)')
        for total_n_cores, performance in zip(ns, perfs):
            print(f'{total_n_cores}       {performance}')

        print('---------\n'
              f'Deviation from linear: {self.deviation_from_linear(ns, perfs)}')

        # TODO: Other metrics here e.g. comparison to other nodes

        print('-------------------------------------------------------------')
        return None


if __name__ == '__main__':

    print('Starting GROMACS benchmark...')
    benchmarks = GROMACSBenchmarks('gromacs@2019%gcc@9.3.0^openmpi@4.1.1',
                                   n_cores=range(2, mp.cpu_count(), 2))
    benchmarks.run()
    benchmarks.print_results()
