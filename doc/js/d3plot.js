const width = 400, height = 400;
const color = d3.scale.category20();

let force = d3.layout.force()
    .charge(-250)
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
        .call(force.drag);

    // The label each node its name from the networkx graph.
    node.append("title")
        .text(function(d) { return d.name; });

    force.on("tick", function() {
        link.attr("x1", function(d) { return d.source.x; })
            .attr("y1", function(d) { return d.source.y; })
            .attr("x2", function(d) { return d.target.x; })
            .attr("y2", function(d) { return d.target.y; });

        node.attr("cx", function(d) { return d.x; })
            .attr("cy", function(d) { return d.y; });
    });
});