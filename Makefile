
all: html

html: clean_html
	# Create plots of the benchmark data and inject into the HTML
	python inject_plots.py
	python build_network_menu.py


clean_html:
	rm -f *.html

clean: clean_html
	rm -f .regression_plot.txt
