const width = 400, height = 400;
const color = d3.scale.category20();

let force = d3.layout.force()
    .charge(-200)
    .linkDistance(function (d) {
        if (d.type === "major"){
            return 50;
        }
        return 150;
    })
    .size([width, height]);

let svg = d3.select("#d3-network-container").select("svg");
if (svg.empty()) {
    svg = d3.select("#d3-network-container").append("svg")
                .attr("width", width)
                .attr("height", height)
                .attr("preserveAspectRatio", "xMidYMid meet");
}

d3.json("assets/network.json", function(error, graph) {

    force.nodes(graph.nodes)
        .links(graph.links)
        .start();

    let link = svg.selectAll(".link")  // Create edges
        .data(graph.links)
        .enter().append("line")
        .attr("class", "link")
        .attr("stroke-width", 2);

    let node = svg.selectAll(".node")  // Create nodes
        .data(graph.nodes)
        .enter().append("circle")
        .attr("class", "node")
        .attr("r", function (n) {     // Radius
            if (n.type === "major"){
                return 16;
            }
            return 10;
        })               // radius
        .style("fill", function (n) {
            // We colour the node depending on the degree.
            return color(n.degree/10);
        })
        .on("mouseover", function (n){
            tooltip.html(n.name)
                .style("left", d3.select(this).attr("cx") + "px")
                .style("top", d3.select(this).attr("cy") + "px")
                .style("opacity", 1);

            if (n.name === "timeseries"){ show_time_series();}
        })
        .on("mouseout", function (n){
            tooltip.style("opacity", 0);
        })
        .call(force.drag);

    force.on("tick", function() {
        link.attr("x1", function(d) { return d.source.x; })
            .attr("y1", function(d) { return d.source.y; })
            .attr("x2", function(d) { return d.target.x; })
            .attr("y2", function(d) { return d.target.y; });

        node.attr("cx", function(d) { return d.x; })
            .attr("cy", function(d) { return d.y; });
    });
});

// create a tooltip
let tooltip = d3.select("#d3-network-container")
    .append("div")
    .attr("class", "tooltip")
    .style("position", "absolute");

function show_time_series(){

    let element = document.getElementById("timeseries-div");

    // Create a collapse instance, toggles the collapse element on invocation
    let collapsable = new bootstrap.Collapse(element);
    collapsable.show();
}