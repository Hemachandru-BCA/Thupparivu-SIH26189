import networkx as nx

# Create a new graph
G = nx.Graph()

# Add 100k nodes to the graph
for i in range(100000):
    G.add_node(i)

# Add edges to the graph
for i in range(100000):
    for j in range(i+1, 100000):
        G.add_edge(i, j)

# Print the graph
print(G)