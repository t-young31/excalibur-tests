const width = 600, height = 400;

let force = d3.layout.force()
    .charge(-200)
    .linkDistance(function (d) {
        if (d.type === "major"){ return 50; }
        return 150;
    })
    .size([width, height]);

let svg = d3.select("#d3-network-container").select("svg");

if (svg.empty()) { svg = create_svg(); }

let tooltip = d3.select("#d3-network-container")
    .append("div")
    .attr("class", "tooltip")
    .style("position", "relative");

d3.json("assets/network.json", function(error, network) {

    // network parameter is built from the json...
    force.nodes(network.nodes).links(network.links).start();

    network.a_node_is_highlighted = false;

    let links = create_links(network);
    let nodes = create_nodes(network);
    force.on("tick", function() { update_positions(nodes, links); });

    network.link_dict = create_network_link_dict(network);

    nodes.on('click', function (d) {
        d.selected = !d.selected;
        highlight_neighbours(d, nodes, links, network);
        show_bootstrap_div(d.name+"-scaling");
    });
});

function create_svg(){
    return d3.select("#d3-network-container").append("svg")
                .attr("width", width)
                .attr("height", height)
                .attr("preserveAspectRatio", "xMidYMid meet");
}

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
        .style("opacity", default_node_opacity)
        .style("fill", function (n) {
            // We colour the node depending on the degree.
            return d3.rgb(n.color);
        })
        .on("mouseover", function (n){
            if (network.a_node_is_highlighted) {return;}
            show_tooltip(n);
            if (n.name === "timeseries"){ show_time_series();}
        })
        .on("mouseout", function (d){
            if (network.a_node_is_highlighted) {return;}
            if (!d.selected){ tooltip.style("opacity", 0);}
        })
        .call(force.drag);
}

function default_node_opacity(node){
    if (node.type === "minor"){ return 0.7; }
    return 1.0;
}

function show_tooltip(n){
    // Show the tooltip aka. node label annotation

    let w = parseFloat(document
        .getElementById("d3-network-container")
        .offsetWidth);

    let html_str = n.name
    if (n.desc !== "none"){ html_str += n.desc; }

    tooltip.html(html_str)
                .style("left", (w-width)/2 + "px")
                .style("top", 10 + "px")
                .style("opacity", 1);
}

function show_bootstrap_div(div_name){
    let element = document.getElementById(div_name);

    if (element == null){ return console.log("Cannot get element", div_name)}

    // Create a collapse instance, toggles the collapse element on invocation
    let collapsable = new bootstrap.Collapse(element);
    collapsable.show();
}

function show_time_series(){ show_bootstrap_div("timeseries-div"); }

function update_positions(nodes, links){
    links.attr("x1", function(d) { return d.source.x; })
         .attr("y1", function(d) { return d.source.y; })
         .attr("x2", function(d) { return d.target.x; })
         .attr("y2", function(d) { return d.target.y; });

    nodes.attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; });
}

function highlight_neighbours(o, nodes, links, network){
    // Highlight a node and its neighbours based on the links, update the
    // opacities and link widths

    function are_neighbours(a, b) {
        return network.link_dict[a.index + "," + b.index];
    }

    if (!network.a_node_is_highlighted) {

        nodes.style("opacity", function (d) {
            if (d.id === o.id){ return 1.0; }
            if (o.type === "major"){ return 0.3; }
            return (are_neighbours(d, o) || are_neighbours(o, d)) ? 0.8 : 0.3;
        });

        links.style("opacity", function (d) {
            return (o.id===d.source.id ||  o.id===d.target.id) ? 0.8 : 0.3;}
        )
            .style("stroke-width", function (d) {
            return (o.id===d.source.id ||  o.id===d.target.id) ? 3 : 2;
        });

        network.a_node_is_highlighted = true;
    } else {
        o.selected = false;
        nodes.style("opacity", default_node_opacity);
        links.style("opacity", 1).style("stroke-width", 2);
        network.a_node_is_highlighted = false;
    }
}

function create_network_link_dict(network){
    // Create a dictionary of bits for whether two nodes in the network are linked

    let linked_dict = {};

    for (let i = 0; i < network.nodes.length; i++) {
        linked_dict[i + "," + i] = true;
    }

    network.links.forEach(function (d) {
        linked_dict[d.source.index + "," + d.target.index] = true;
    });

    return linked_dict;
}
