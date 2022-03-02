import os
from typing import Dict, Tuple, List
from abc import ABC, abstractmethod
from glob import glob
from bokeh.plotting import figure
from bokeh.models import HoverTool, ColumnDataSource
from bokeh.embed import components
from bokeh.io import curdoc


plots = {
    # Bar plot for all clusters using openmpi builds, imb benchmark, PingPong
    0: ('bar', '*/*openmpi*/imb/IMB_PingPong.log')
}


def inject_all(plots_dict:    Dict[int, Tuple],
               html_filename: str
               ) -> None:
    """
    Inject all the plots defined in a dictionary

    ---------------------------------------------------------------------------
    Arguments:
        plots_dict: Dictionary keyed with the index of the plot with a value
                    defining the location of the data. Relative to the
                    perflogs folder in the root directory

        html_filename: Name of the html file to inject into. Relative to the
                       the same directory as this file
    """

    for plot_idx, (plot_type_str, files_path) in plots_dict.items():

        if plot_type_str.lower() == 'bar':
            plot_type = BarPlot

        elif plot_type_str.lower() == 'line':
            plot_type = LinePlot

        else:
            raise ValueError(f'Unsupported plot type: {plot_type_str}')

        plot = plot_type(files_path)

        plot.target = HTMLFile(html_filename)
        plot.inject_script()
        plot.inject_div_at(plot_idx)

    return None


class HTMLFile:

    def __init__(self, filename):
        self._template_filename = filename

        if not os.path.exists(filename):
            raise IOError(f'Cannot create a file from {filename} - it did '
                          f'not exist')

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
                    print(string, file=html_file, end='', sep='')

                print(line, file=html_file, end='', sep='')

            # Print the final line
            print(lines[-1], file=html_file)

        return None

    def replace(self, idx: int, string: str):
        """Replace a line with a single integer on it with a string"""

        lines = self._current_file_lines
        found_idx = False

        with open(self._filename, 'w') as html_file:
            for line in lines:

                if line == f'{idx}\n':
                    print(string, file=html_file, end='', sep='')
                    found_idx = True

                else:
                    print(line, file=html_file, end='', sep='')

        if not found_idx:
            raise RuntimeError(f"Replacement failed: failed to find {idx} in "
                               f"{self._template_filename}.")
        return None


class Plot(ABC):

    def __init__(self, files_path: str):
        """
        Construct a plot given a path to a set of output files.

        Example:
            >>> plot = Plot('alska/*/imb/IMB_PingPong')

        which will create a plot for all the PingPong imb benchmarks in the
        perflogs folder.

        -----------------------------------------------------------------------
        Arguments:
            files_path: .log files that can be glob-ed
        """

        self._target = None
        self.file_names = glob(os.path.join('..', 'perflogs', files_path))

        self._script, self._div = self.bokeh_components()

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


class BarPlot(Plot):

    def bokeh_components(self) -> Tuple[str, str]:

        # TODO: Get the correct data here
        x = [1, 2, 3, 4, 5]
        y = [6, 7, 6, 4, 5]

        curdoc().theme = 'caliber'

        hover = HoverTool(tooltips=[('Description', '@category'),
                                    ('Value', '@value')],
                          mode='vline')

        plot = figure(title='caliber', width=500, height=500)
        plot.vbar(x='category',
                  top='value',
                  width=0.9,
                  source=ColumnDataSource(data={'category': x,
                                                'value': y})
                  )

        plot.add_tools(hover)

        plot.xaxis.axis_label = 'Category'
        plot.yaxis.axis_label = 'Value'

        self._set_default_style(plot)
        return components(plot)


class LinePlot(Plot):

    def bokeh_components(self) -> Tuple[str, str]:
        raise NotImplementedError


if __name__ == '__main__':

    inject_all(plots, '_templates/index.html')
