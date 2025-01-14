import os
import shutil
import numpy as np

from typing import Dict, Tuple, List, Union, Sequence, Iterator, Optional
from copy import deepcopy
from datetime import date
from abc import ABC, abstractmethod
from glob import glob
from pathlib import Path

from bokeh.plotting import figure
from bokeh.models import HoverTool, ColumnDataSource, Range1d, Band
from bokeh.palettes import Dark2_6
from bokeh.embed import components
from bokeh.io import curdoc

from scipy.interpolate import interp1d


plots = {
    # Bar plot for all clusters using openmpi builds, imb benchmark, PingPong
    # 0: ('bar', 'max_bandwidth', ('*/*openmpi*/imb/*PingPong*/*.log', '*/*omp*/imb/*PingPong*/*.log')),

    0: ('strong_scaling', 'Rate', '*/*/*/gromacs_2_ompthreads/*'),

    # 3: ('time_series_regression', '*', '*')
}

colors = {'csd3':      Dark2_6[0],
          'alaska':    Dark2_6[1],
          'myriad':    Dark2_6[2],
          'cosma8':    Dark2_6[3],
          'tesseract': Dark2_6[4],
          'tursa':     Dark2_6[5]}


def inject_all(plots_dict:        Dict[int, Tuple],
               template_filename: str
               ) -> None:
    """
    Inject all the plots defined in a dictionary

    ---------------------------------------------------------------------------
    Arguments:
        plots_dict: Dictionary keyed with the index of the plot with a value
                    defining the location of the data. Relative to the
                    perflogs folder in the root directory

        template_filename: Name of the html file to inject into. Relative to the
                       the same directory as this file
    """

    for plot_idx, (plot_type_str, metric, files_path) in plots_dict.items():

        if plot_type_str.lower() == 'bar':
            plot_type = BarPlot

        elif plot_type_str.lower() == 'strong_scaling':
            plot_type = StrongScalingPlot

        elif plot_type_str.lower() == 'time_series_regression':
            plot_type = TimeSeriesRegressionPlot

        else:
            raise ValueError(f'Unsupported plot type: {plot_type_str}')

        plot = plot_type(metric, files_path)

        plot.target = HTMLFile(template_filename)
        plot.inject_script()
        plot.inject_div_at(plot_idx)

    return None


class File:

    @staticmethod
    def _validated(filename) -> str:

        if not os.path.exists(filename):
            raise IOError(f'Cannot create a file from {filename} - it did '
                          f'not exist')

        return filename


class HTMLFile(File):

    def __init__(self, template_filename):

        self._filename = self._validated(template_filename)
        self._filename = self._filename.replace('_templates/', '')

        if (not os.path.exists(self._filename)
                and template_filename != self._filename):
            shutil.copy(template_filename, self._filename)

    @property
    def _current_file_lines(self) -> List[str]:
        return open(self._filename, 'r').readlines()

    def add_before_end_body(self, string: str):
        """Add a string before the end of the body """
        lines = self._current_file_lines

        with open(self._filename, 'w') as html_file:
            for i, line in enumerate(lines[:-1]):

                if '</body>' in lines[i+1]:
                    print(string, file=html_file, end='\n', sep='')

                print(line, file=html_file, end='', sep='')

            print(lines[-1], file=html_file)  # Print the excluded final line

        return None

    def replace(self, idx: int, string: str):
        """Replace a line with a single integer on it with a string"""

        lines = self._current_file_lines
        found_idx = False

        with open(self._filename, 'w') as html_file:
            for line in lines:

                if line.endswith(f'{idx}\n'):
                    print(string, file=html_file, sep='')
                    found_idx = True

                else:
                    print(line, file=html_file, end='', sep='')

        if not found_idx:
            raise RuntimeError(f"Replacement failed: failed to find {idx} in "
                               f"{self._filename}.")

        return None


class Benchmark:

    def __init__(self, metric: str ='*'):
        """
        Construct a benchmark

        -----------------------------------------------------------------------
        Arguments:

            metric: Metric on which the benchmark is defined. If "*" then will
                    extract based in the position line.
        """

        self.metric = metric
        self.value:           Optional[float] = None
        self.units:           Optional[str] = None
        self.date:            Optional[date] = None

        self.num_total_cores: Optional[int] = None
        self.num_omp_threads: Optional[int] = None
        self.num_nodes:       Optional[int] = None

    def set_from(self, reframe_log_line: str):
        """Set the benchmark from a reframe log line"""
        line = reframe_log_line

        self._set_metric(line)
        self.value = float(self._value_of(self.metric, line))
        self.units = str(self._value_of('units', line))
        self._set_date(line)

        self.num_total_cores = int(self._value_of('num_total_cores', line))
        self.num_omp_threads = int(self._value_of('num_omp_threads', line))
        self.num_nodes = int(self._value_of('num_nodes', line))

        return None

    def _set_date(self, line):
        first_item = line.split()[0]
        self.date = date.fromisoformat(first_item.split('T')[0])
        return None

    def _set_metric(self, line):
        """Set the performance metric from the output"""

        try:
            extracted_metric = line.split('|')[4].split('=')[0]
        except IndexError:
            raise RuntimeError(f'Failed to find any metric in: {line}')

        if self.metric != '*' and extracted_metric != self.metric:
            raise RuntimeError(f'Metric {self.metric} was not at the expected '
                               f'position in: {line}')

        self.metric = extracted_metric
        return None

    @staticmethod
    def _value_of(s, line) -> str:
        return next(x.split('=')[1] for x in line.split('|') if s in x)


class ReFrameLogFile(File):
    """
    ReFrame log file with a format:

    #--------------------------------------------------------------------------
    2020-08-19T16:20:21+01:00|.|IMB_.|max_bandwidth=3041.25|Mbytes/sec|.|.
    2020-08-19T16:20:21+01:00|.|IMB_.|min_latency=2.05|t[usec]|.|.
    2020-09-09T10:30:12+01:00|.|IMB_.|.|max_bandwidth=3039.31|Mbytes/sec|.|.
    .            .            .   .   .     .                   .        .
    #--------------------------------------------------------------------------

    where dots denote abbreviated strings
    """

    def __init__(self, filename, metric=None):

        self.filename = self._validated(filename)
        self.benchmarks = []

        if metric is not None:
            self.extract(metric)

    def __str__(self):
        return self.file_path_truncated_end

    def __repr__(self):
        return f'ReFrameLogFile({self.file_path_truncated_end})'

    @property
    def file_path_no_perflogs(self) -> str:
        return self.filename.replace('../perflogs/', '')

    @property
    def file_path_truncated_end(self) -> str:
        return f'...{self.filename[-12:-4]}'

    @property
    def directory(self) -> str:
        return ''.join(self.filename.split('/')[2:-1])

    @property
    def n_cores(self) -> int:
        """Number ot total cores used for *all* benchmarks in this file"""
        n_cores = next(b.num_total_cores for b in self.benchmarks)

        if not all(b.num_total_cores == n_cores for b in self.benchmarks):
            raise RuntimeError('Failed to determine the number of cores in '
                               'the log file. Had different values')

        return n_cores

    @property
    def has_multiple_values(self) -> bool:
        """Does this log file have multiple values of a metric"""
        return len(self.benchmarks) > 1

    def extract(self, metric: str) -> None:
        """Extract the relevant information from a ReFrame log file"""

        for line in open(self.filename, 'r'):
            benchmark = Benchmark(metric=metric)
            benchmark.set_from(line)
            self.benchmarks.append(benchmark)

        return None


class ReFrameLogFileGroup(list):

    def __init__(self, _list):
        super().__init__(_list)

    @property
    def name(self) -> str:
        """Name of this group, defined by the first different"""
        return '_'.join(self[0].file_path_no_perflogs.split('/')[:-1])

    @property
    def truncated_name(self) -> str:
        return self.name.split('_')[0]+'...'


class Plot(ABC):

    def __init__(self):
        self._script = None
        self._div = None

    @abstractmethod
    def bokeh_components(self) -> Tuple[str, str]:
        """Retrieve the script and div components of a Bokeh plot"""

    @property
    def target(self) -> HTMLFile:
        return self._target

    @target.setter
    def target(self, value: HTMLFile):
        """Setter for the target html file to inject into"""

        if not (isinstance(value, HTMLFile)):
            raise ValueError(f'Plot target must be a HTMLFile. Had {type(value)}')

        self._target = value

    def inject_script(self) -> None:
        """Inject the js script into the end of the target html file"""

        if self._target is None:
            raise RuntimeError('Cannot inject script. html file target not set')

        return self._target.add_before_end_body(self._script)

    def inject_div_at(self, idx: int) -> None:
        """Inject the html div into a defined position in the html"""

        if self._target is None:
            raise RuntimeError('Cannot inject div. html file target not set')

        return self._target.replace(idx, self._div)

    @staticmethod
    def _set_default_style(plot) -> None:
        """Set the default Bokeh style for every plot"""

        plot.axis.minor_tick_line_color = None
        plot.axis.axis_line_color = None
        plot.title.text_font_size = '20px'

        plot.background_fill_color = "#f5f5f5"
        plot.grid.grid_line_color = "white"

        plot.background_fill_alpha = 0

        for axis in (plot.xaxis, plot.yaxis):
            axis.axis_label_text_font_size = '14px'
            axis.major_label_text_font_size = '12px'

        return None


class AutoGeneratedPlot(Plot, ABC):

    def __init__(self,
                 metric:     str,
                 files_path: Union[Sequence[str], str]
                 ):
        """
        Construct a plot given a path to a set of output files.

        Example:
            >>> plot = Plot('alska/*/imb/IMB_PingPong')

        which will create a plot for all the PingPong imb benchmarks in the
        perflogs folder.

        -----------------------------------------------------------------------
        Arguments:
            metric: Name of the performance metric to look for in the reframe
                    log

            files_path: .log files that can be glob-ed. Either a single string
                        or a sqeuence (e.g. tuple)
        """
        super().__init__()

        self._metric = metric
        self._target = None
        self._log_files = []

        for path in self.file_paths_from(files_path):

            f = ReFrameLogFile(path, metric=metric)
            self._log_files.append(f)

        self._script, self._div = self.bokeh_components()

    @staticmethod
    def file_paths_from(paths: Union[Sequence[str], str]) -> Iterator:
        """Generate a set of file paths from either a single path or a
        tuple of paths"""

        for path in ((paths,) if isinstance(paths,str) else paths):
            for file_path in glob(os.path.join('..', 'perflogs', path)):
                yield file_path

    @property
    def title(self) -> str:
        """
        Generate a title of a plot, generated from the end of the file
        path(s) which store the data.
        """

        fns = [Path(f.filename) for f in self._log_files]

        if len(fns) == 0:
            raise RuntimeError('Cannot generate a title without any data files')

        first_filename = fns[0].name

        if not all(f.name == first_filename for f in fns):
            raise RuntimeError('Cannot generate a title. Some files were '
                               'not named identically')

        return Path(first_filename).stem

    @property
    def _units(self) -> str:
        """Extract the units from a ReFrame log file for a particular metric"""
        if len(self._log_files) == 0:
            raise RuntimeError('Cannot determine the units. Had no files')

        return next(b.units for b in self._log_files[0].benchmarks
                    if b.metric == self._metric)

    @property
    def n_files(self) -> int:
        """Number of data files that comprise this plot"""
        return len(self._log_files)


class BarPlot(AutoGeneratedPlot):

    def bokeh_components(self) -> Tuple[str, str]:
        """Generate script and div components for a Bokeh bar plot"""

        x = [f.file_path_no_perflogs for f in self._log_files]

        # TODO: enable extraction of more than the first value
        y = [f.values[0] for f in self._log_files]
        dates = [f.dates[0] for f in self._log_files]

        curdoc().theme = 'caliber'

        hover = HoverTool(tooltips=[('Description', '@desc'),
                                    ('Value', '@value'),
                                    ('Date', '@date')],
                          mode='vline')

        plot = figure(title=self.title,
                      width=400,
                      height=400)

        data = ColumnDataSource(data={'index': range(self.n_files),
                                      'value': y,
                                      'desc': x,
                                      'date': dates})
        plot.vbar(x='index',
                  top='value',
                  width=0.9,
                  source=data)

        plot.add_tools(hover)
        self._set_categorical_x_ticks(plot)
        plot.yaxis.axis_label = f'{self._metric} / {self._units}'

        self._set_default_style(plot)
        return components(plot)

    def _set_categorical_x_ticks(self, plot) -> None:
        """Set the labels on the x axis"""

        plot.xaxis.ticker = list(range(self.n_files))
        plot.xaxis.major_label_overrides = {
            i: f.file_path_truncated_end for i, f in enumerate(self._log_files)
        }
        plot.xaxis.minor_tick_line_color = None

        return None


class StrongScalingPlot(AutoGeneratedPlot):

    @staticmethod
    def _n_diff_chars(string1, string2):
        return sum(char1 != char2 for char1, char2 in zip(string1, string2))

    @property
    def _log_file_groups(self,
                         threshold_n_diff_chars: int = 1
                         ) -> List[ReFrameLogFileGroup]:
        """Group ReFrame log files based on the first different component to
        the file paths"""

        if len(self._log_files) == 0:
            raise RuntimeError('Cannot group log files. Had 0')

        files = deepcopy(self._log_files)
        groups = []

        for f in files:
            added = False

            for group in groups:
                if (self._n_diff_chars(f.directory, group[0].directory)
                        < threshold_n_diff_chars):
                    group.append(f)
                    added = True
                    break

            if not added:
                # The filename is not similar enough to any other groups,
                # so create a new one
                groups.append(ReFrameLogFileGroup([f]))

        return groups

    @staticmethod
    def _plot_line(plot, log_file_group, color) -> None:
        """Plot a line with markers for a group of log files"""

        fs = sorted(log_file_group, key=lambda f: f.n_cores)
        xs = [f.n_cores for f in fs]

        # TODO: What do to with multiple metrics in the same file?
        source = ColumnDataSource(
            data={'n_cores': xs,
                  'values': [f.benchmarks[-1].value for f in fs],
                  'descs': [f.file_path_no_perflogs for f in fs],
                  'date': [f.benchmarks[-1].date for f in fs],
                  'omp': [f.benchmarks[-1].num_omp_threads for f in fs],
                  'n_nodes': [f.benchmarks[-1].num_nodes for f in fs]
                  })

        plot.circle(source.data['n_cores'],
                    source.data['values'],
                    fill_color="white",
                    size=12,
                    color=color,
                    legend_label=log_file_group.truncated_name
                    )

        plot.line(x='n_cores',
                  y='values',
                  line_width=2,
                  source=source,
                  name=log_file_group.truncated_name,
                  color=color
                  )

        return None

    def bokeh_components(self) -> Tuple[str, str]:
        """Construct the bokeh div and script for a line plot, where the final
        dimension is the independent variable (x axis) on the plot"""

        plot = figure(title='',  # More descriptive title?
                      width=800,
                      height=400,
                      max_width=900)

        for group, color in zip(self._log_file_groups, Dark2_6):
            self._plot_line(plot, group, color)

        hover = HoverTool(tooltips=[('Description', '@descs'),
                                    ('Value', '@values'),
                                    ('Date', '@date'),
                                    ('# cores', '@n_cores'),
                                    ('# OMP threads', '@omp'),
                                    ('# nodes', '@n_nodes')
                                    ],
                          names=[group.truncated_name for group in self._log_file_groups],
                          mode='mouse')

        plot.add_tools(hover)
        plot.legend.location = "bottom_right"
        plot.legend.label_text_font_size = "8pt"

        plot.xaxis.axis_label = 'Number of cores'
        plot.yaxis.axis_label = f'{self._metric} / {self._units}'
        self._set_default_style(plot)

        return components(plot)


class TimeSeriesRegressionPlot(Plot):

    _cache_filename = '.regression_plot.txt'

    def __init__(self, metric='*', paths='*'):
        super().__init__()

        self.data = {}
        """
        Data has keys of cluster names and the values as a dictionary of
        {'x': <times>, 'y': <relative values>}
        """

        try:
            self.load_cached_data_from_file()

        except FileNotFoundError:
            self._extract_data()
            self._save_data()

        self._script, self._div = self.bokeh_components()

    def load_cached_data_from_file(self) -> None:
        """Try and load the x, y data from the cached file"""

        with open(self._cache_filename, 'r') as f:
            for line in f:
                k, v = line.split(':')
                xs, ys = v.split('|')

                if len(xs) == 0 or len(ys) == 0:
                    print(f'WARNING: Failed to find any data for {k}')
                    continue

                self.data[k] = {'x': [float(x) for x in xs.split(',')],
                                'y': [float(y) for y in ys.split(',')]}
        return None

    def _save_data(self) -> None:
        """Save all the extracted data"""

        with open(self._cache_filename, 'w') as cache_file:
            for k, v in self.data.items():
                xs, ys = v.values()
                xs_str = ','.join([str(x) for x in xs])
                ys_str = ','.join([str(y) for y in ys])

                print(f'{k}:{xs_str}|{ys_str}', file=cache_file)

        return None

    def _extract_data(self) -> None:
        """Extract all relative performance data"""

        for fn in os.listdir('../perflogs'):

            times, values = self._all_dates_values_from(fn)
            self.data[fn] = {'x': times, 'y': values}

        return None

    @staticmethod
    def _all_dates_values_from(folder_name) -> Tuple[list, list]:
        """From a relative folder extract all relative time information"""
        dates, rel_values = [], []

        for fn in glob(f'../perflogs/{folder_name}/**/*.log',
                       recursive=True):

            f = ReFrameLogFile(fn)

            for metric in f.metrics:
                f.extract(metric)

                if not f.has_multiple_values:
                    continue

                init_value = f.values[0]
                for d, v in zip(f.dates, f.values):
                    dates.append(d.toordinal())
                    rel_values.append(v/init_value)

                if any(v/init_value > 3 for v in f.values):
                    print('WARNING: Large rel change in:', fn)

        return dates, rel_values

    def dates(self, cluster_name) -> List[int]:
        """All the dates present in the data, sorted old->new"""
        return [x for x in sorted(self.data[cluster_name]['x'])]

    def relative_metrics(self, cluster_name) -> List[float]:
        """Relative performance metrics for a particular cluster sorted by
        the date which they were evaluated"""

        dates = self.data[cluster_name]['x']
        rel_metrics = self.data[cluster_name]['y']

        return [y for _, y in sorted(zip(dates, rel_metrics))]

    def smoothed_dates(self, cluster_name) -> np.ndarray:
        """Set of dates that correspond to a set of smoothed values"""
        dates = self.dates(cluster_name)

        return np.linspace(min(dates), max(dates), num=500, dtype=float)

    def smoothed(self, cluster_name, n=12) -> Tuple[np.ndarray, np.ndarray]:
        """Smooth the relative metrics data by block averaging and splining"""
        all_dates = self.dates(cluster_name)
        all_rel_metrics = self.relative_metrics(cluster_name)

        bins = np.linspace(min(all_dates), max(all_dates), num=n+1, dtype=float)

        dates = [[] for _ in range(n)]
        rel_metrics = [[] for _ in range(n)]

        for _date, _metric in zip(all_dates, all_rel_metrics):

            for i in range(1, len(bins)):

                if bins[i-1] < _date <= bins[i]:
                    rel_metrics[i-1].append(_metric)
                    dates[i-1].append(_date)
                    break

        avg_dates = [sum(b) / len(b) for b in dates if len(b) > 0]
        avg_rel_metrics = [sum(b) / len(b) for b in rel_metrics if len(b) > 0]

        spline = interp1d(avg_dates, avg_rel_metrics, kind='nearest')
        more_dates = np.linspace(min(avg_dates), max(avg_dates), num=200)

        return more_dates, spline(more_dates)

    def has_no_data(self, cluster_name) -> bool:
        return len(self.data[cluster_name]['x']) == 0

    def block_relative_metrics(self, cluster_name, func) -> List[float]:
        """Apply a function over a block"""
        rel_metrics = self.relative_metrics(cluster_name)
        return [func(b) for b in blocked_array(rel_metrics, 10)]

    def bokeh_components(self) -> Tuple[str, str]:

        plot = figure(  # title='Time series regression',
                      width=800,
                      height=400,
                      y_range=(0.6, 4),
                      max_width=900)

        for cluster_name in self.data.keys():

            if self.has_no_data(cluster_name):
                continue

            smooth_dates, smooth_rel_metrics = self.smoothed(cluster_name)
            plot.line(smooth_dates,
                      smooth_rel_metrics,
                      legend_label=cluster_name,
                      color=colors[cluster_name],
                      line_width=2
                      )

            source = ColumnDataSource(
                data={'x': block_average(self.dates(cluster_name), 10),
                      'lower': self.block_relative_metrics(cluster_name, func=min),
                      'upper': self.block_relative_metrics(cluster_name, func=max)}
                                      )

            band = Band(base='x',
                        lower='lower',
                        upper='upper',
                        source=source,
                        level='underlay',
                        fill_alpha=0.1,
                        line_width=0.5,
                        line_color='black',
                        fill_color=colors[cluster_name])

            plot.add_layout(band)

        plot.legend.location = "top_left"
        plot.yaxis.axis_label = 'Relative metric'

        self._set_x_ticks(plot)
        self._set_default_style(plot)

        return components(plot)

    def _set_x_ticks(self, plot) -> None:
        """Set the x range of the entire date history of the benchmark set.
        Then set the tick labels to dates"""

        min_x, max_x = 2 ** 99, 0

        for xs in (xy['x'] for xy in self.data.values() if len(xy['x']) > 0):

            if max(xs) > max_x:
                max_x = max(xs)

            if min(xs) < min_x:
                min_x = min(xs)

        plot.x_range = Range1d(min_x, max_x + 1)
        x_tick_pos = linspace(min_x, max_x, num=8)

        plot.xaxis.ticker = x_tick_pos
        plot.xaxis.major_label_overrides = {
            x: str(date.fromordinal(int(x))) for x in x_tick_pos
        }

        plot.xaxis.ticker.num_minor_ticks = 0

        return None


def linspace(start, end, num) -> List[int]:
    """Linear spaced points within a division. Like numpy.linspace"""
    delta = (end - start) / (num - 1)
    return [int(start + i*delta) for i in range(num)]


def block_average(array, block_size) -> list:
    """Block average an array"""
    return [sum(b) / len(b) for b in blocked_array(array, block_size)]


def blocked_array(array, block_size) -> List[list]:
    """Apply a function over a blocked array"""

    if len(array) == 0:
        raise ValueError(f'Cannot block average {array}. Had no items')

    block_array = []

    for i in range(len(array) // block_size):
        block = array[i*block_size:block_size * (i + 1)]
        block_array.append(block)

    # Blocked array includes the end points
    return [array[:1]] + block_array + [array[-1:]]


if __name__ == '__main__':

    inject_all(plots, '_templates/index.html')
