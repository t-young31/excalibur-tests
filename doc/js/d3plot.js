const width = 600, height = 400;

let force = d3.layout.force()
    .charge(-200)
    .linkDistance(function (d) {
        if (d.type === "major"){ return 50; }
        return 150;
    })
    .size([width, height]);

let tooltip = d3.select("#d3-network-container")
    .append("div")
    .attr("class", "tooltip")
    .style("position", "relative");

let svg = d3.select("#d3-network-container").select("svg");

if (svg.empty()) {
    svg = d3.select("#d3-network-container").append("svg")
                .attr("width", width)
                .attr("height", height)
                .attr("preserveAspectRatio", "xMidYMid meet");
}

d3.json("assets/network.json", function(error, network) {

    force.nodes(network.nodes)
        .links(network.links)
        .start();

    let links = create_links(network);
    let nodes = create_nodes(network);
    force.on("tick", function() { update_network_position(links, nodes);});
});

function create_links(network){
    // Create edges in the network

    return svg.selectAll(".link")
        .data(network.links)
        .enter().append("line")
        .attr("class", "link")
        .attr("stroke-width", 2);
}

function create_nodes(network){
    // Create nodes in the graph

    return svg.selectAll(".node")
        .data(network.nodes)
        .enter().append("circle")
        .attr("class", "node")
        .attr("r", function (d) {     // Radius
            if (d.type === "major"){ return 16; }
            if (d.name === "timeseries") { return 20; }
            return 10;
        })
        .style("opacity", function (d){
            if (d.type === "minor"){ return 0.7; }
            return 1.0;
        })
        .style("fill", function (n) {
            // We colour the node depending on the degree.
            return d3.rgb(n.color);
        })
        .on("mouseover", function (n){
            show_tooltip(n);
            if (n.name === "timeseries"){ show_time_series();}
        })
        .on("mouseout", function (){ tooltip.style("opacity", 0);}
        )
        .call(force.drag);
}

function show_tooltip(n){
    // Show the tooltip aka. node label annotation

    let w = document.getElementById("d3-network-container").offsetWidth;
    tooltip.html(n.name)
                .style("left", w/2 + "px")
                .style("top", 10 + "px")
                .style("opacity", 1);
}

function show_time_series(){

    let element = document.getElementById("timeseries-div");

    // Create a collapse instance, toggles the collapse element on invocation
    let collapsable = new bootstrap.Collapse(element);
    collapsable.show();
}

function update_network_position(links, nodes){
    links.attr("x1", function(d) { return d.source.x; })
         .attr("y1", function(d) { return d.source.y; })
         .attr("x2", function(d) { return d.target.x; })
         .attr("y2", function(d) { return d.target.y; });

    nodes.attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; });
}

