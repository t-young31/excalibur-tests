
all: html

html: clean_html
	# Create plots of the benchmark data and inject into the HTML
	python inject_plots.py
	python inject_network.py


clean_html:
	rm -f *.html

clean:
	rm -f .regression_plot.txt
