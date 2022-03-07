import os
import itertools
from typing import Dict, Tuple, List, Union, Sequence, Iterator
from datetime import date
from abc import ABC, abstractmethod
from glob import glob
from pathlib import Path
from bokeh.plotting import figure
from bokeh.models import HoverTool, ColumnDataSource
from bokeh.palettes import Dark2_5 as palette
from bokeh.embed import components
from bokeh.io import curdoc


plots = {
    # Bar plot for all clusters using openmpi builds, imb benchmark, PingPong
    0: ('bar', 'max_bandwidth', ('*/*openmpi*/imb/*PingPong*/*.log',
                                 '*/*omp*/imb/*PingPong*/*.log')),

    1: ('bar', 'Gflops', ('*/*openmpi*/hpl/Hpl_single/*.log',
                          '*/*omp*/hpl/Hpl_single/*.log')),

    3: ('time_series_regression', '*', '*')
}


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

        elif plot_type_str.lower() == 'line':
            plot_type = LinePlot

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
    def _check_exists(filename):

        if not os.path.exists(filename):
            raise IOError(f'Cannot create a file from {filename} - it did '
                          f'not exist')


class HTMLFile(File):

    def __init__(self, filename):

        self._check_exists(filename)
        self._template_filename = filename

    @property
    def _filename(self) -> str:
        """Filename is just the template without the _templates/ directory"""
        return ''.join(self._template_filename.split('/')[1:])

    @property
    def _current_file_lines(self) -> List[str]:
        fn = self._filename if os.path.exists(self._filename) else self._template_filename
        return open(fn, 'r').readlines()

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
                               f"{self._template_filename}.")

        return None


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

        self._check_exists(filename)
        self.filename = filename

        self.values:       List[float] = []
        self.dates:        List[date] = []

        if metric is not None:
            self.extract(metric)

    @property
    def file_lines(self) -> List[str]:
        return open(self.filename, 'r').readlines()

    @property
    def file_path_alt(self) -> str:
        return '/'.join(self.filename.split('/')[2:])

    @property
    def file_path_truncated(self) -> str:
        return f'...{self.filename[-12:-4]}'

    @property
    def metrics(self) -> List[str]:
        """Performance metrics that are present in this file"""
        metrics = []

        for line in self.file_lines:

            try:
                metric = line.split('|')[-4].split('=')[0]
                metrics.append(metric)
            except IndexError:
                continue

        return metrics

    @property
    def has_multiple_values(self) -> bool:
        """Does this log file have multiple values of a metric"""
        return len(self.values) > 1

    def extract_values(self, metric: str) -> None:
        """
        Extract the value of a metric from the file

        -----------------------------------------------------------------------
        Arguments:
            metric:

        Raises:
            (IOError): If the file cannot be found
            (RuntimeError): If the metric cannot be found
        """

        self.values.clear()

        try:
            for line  in filter(lambda l: metric in l, self.file_lines):

                pair = next(item for item in line.split('|') if metric in item)
                self.values.append(float(pair.split('=')[-1]))

        except (StopIteration, ValueError, TypeError, IndexError):
            raise RuntimeError(f'Failed to find {metric} in {self.filename}')

    def units_of(self, metric: str) -> str:
        """Extract the units of a particular metric"""

        def first_line_with_metric():
            return next(l for l in self.file_lines if metric in l)

        def first_item_with_metric_in_item_before(xs):
            return next(x for i, x in enumerate(xs[1:]) if metric in xs[i])

        try:
            items = first_line_with_metric().split('|')
            return first_item_with_metric_in_item_before(items)

        except (StopIteration, ValueError, TypeError, IndexError):
            raise RuntimeError(f'Failed to find {metric} in {self.filename}')

    def extract_dates(self, metric: str) -> None:
        """Extract the times at which the metric was evaluated"""

        self.dates.clear()

        try:
            for line in filter(lambda l: metric in l, self.file_lines):
                time_str = line.split('T')[0]
                self.dates.append(date.fromisoformat(time_str))

        except (StopIteration, ValueError, TypeError, IndexError):
            raise RuntimeError(f'Failed to find {metric} in {self.filename}')

    def extract(self, metric: str) -> None:
        """Extract the relevant information from a ReFrame log file"""

        self.extract_values(metric)
        self.extract_dates(metric)

        return None


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

        for axis in (plot.xaxis, plot.yaxis):
            axis.axis_label_text_font_size = '14px'

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

        for path in tuple(paths):
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

        return self._log_files[0].units_of(self._metric)

    @property
    def n_files(self) -> int:
        """Number of data files that comprise this plot"""
        return len(self._log_files)


class BarPlot(AutoGeneratedPlot):

    def bokeh_components(self) -> Tuple[str, str]:
        """Generate script and div components for a Bokeh bar plot"""

        x = [f.file_path_alt for f in self._log_files]

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

        plot.vbar(x='index',
                  top='value',
                  width=0.9,
                  source=ColumnDataSource(data={'index': range(self.n_files),
                                                'value': y,
                                                'desc': x,
                                                'date': dates})
                  )

        plot.add_tools(hover)
        self._set_categorical_x_ticks(plot)
        plot.yaxis.axis_label = f'{self._metric} / {self._units}'

        self._set_default_style(plot)
        return components(plot)

    def _set_categorical_x_ticks(self, plot) -> None:
        """Set the labels on the x axis"""

        plot.xaxis.ticker = list(range(self.n_files))
        plot.xaxis.major_label_overrides = {
            i: f.file_path_truncated for i, f in enumerate(self._log_files)
        }
        plot.xaxis.minor_tick_line_color = None

        return None


class LinePlot(AutoGeneratedPlot):

    def bokeh_components(self) -> Tuple[str, str]:
        raise NotImplementedError


class TimeSeriesRegressionPlot(Plot):

    _cache_filename = '.regression_plot.txt'
    colours = itertools.cycle(palette)

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

                self.data[k] = {'x': (float(x) for x in xs.split(',')),
                                'y': (float(y) for y in ys.split(','))}
        return None

    def _extract_data(self) -> None:
        """Extract all relative performance data"""

        for fn in os.listdir('../perflogs'):

            times, values = self._all_dates_values_from(fn)
            self.data[fn] = {'x': times, 'y': values}

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
                    dates.append(d.strftime('%s'))
                    rel_values.append(v/init_value)

        return dates, rel_values

    def bokeh_components(self) -> Tuple[str, str]:

        plot = figure(title='Timeseries regression',
                      width=800,
                      height=400,
                      y_range=(0.6, 4))

        for (cluster_name, xy), c in zip(self.data.items(), self.colours):

            xs = sorted(xy['x'])
            ys = [y for _, y in sorted(zip(xy['x'], xy['y']))]

            plot.line(x=xs,
                      y=ys,
                      legend_label=cluster_name,
                      color=c
                      )

        plot.legend.location = "top_left"
        plot.yaxis.axis_label = 'Relative metric'

        self._set_default_style(plot)
        return components(plot)


if __name__ == '__main__':

    inject_all(plots, '_templates/index.html')
