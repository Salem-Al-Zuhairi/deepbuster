/**
 * Deepbuster Vis-Network Live Topology Map Mapping
 * Dynamically builds folder branches from discovered paths and updates a hierarchical tree.
 */

class LiveGraph {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.network = null;
        this.nodes = new vis.DataSet([]);
        this.edges = new vis.DataSet([]);
        this.knownNodes = new Set();
        this.knownEdges = new Set();
        this.currentDirection = 'LR';
        this.activeFilter = 'all';
    }

    init(direction = 'LR') {
        if (!this.container) return;
        this.currentDirection = direction;
        
        const data = {
            nodes: this.nodes,
            edges: this.edges
        };

        const options = {
            nodes: {
                shape: 'box',
                font: {
                    color: '#f0f3fa',
                    size: 13,
                    face: 'Space Grotesk'
                },
                borderWidth: 2,
                shadow: true,
                margin: 10
            },
            edges: {
                color: {
                    color: '#263760',
                    highlight: '#00ff99',
                    hover: '#00ff99'
                },
                width: 2,
                arrows: {
                    to: { enabled: true, scaleFactor: 0.5 }
                },
                smooth: {
                    type: 'cubicBezier',
                    forceDirection: direction === 'UD' ? 'vertical' : 'horizontal',
                    roundness: 0.4
                }
            },
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: direction,
                    sortMethod: 'directed',
                    levelSeparation: 160,
                    nodeSpacing: 100,
                    parentCentralization: true,
                    edgeMinimization: true
                }
            },
            physics: {
                enabled: false
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                dragNodes: true
            }
        };

        this.network = new vis.Network(this.container, data, options);

        // Double-click node to visit the page in a new tab
        this.network.on('doubleClick', (params) => {
            if (params.nodes && params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                if (nodeId === 'root') return;

                // Extract path from nodeId: 'node_some/path' -> '/some/path'
                const path = nodeId.replace(/^node_/, '');
                const targetInput = document.getElementById('targetUrl');
                if (!targetInput) return;

                let base = targetInput.value.trim();
                if (base && !base.endsWith('/')) base += '/';
                const fullUrl = base + path;
                window.open(fullUrl, '_blank');
            }
        });
    }

    setDirection(direction) {
        if (this.currentDirection === direction) return;
        this.init(direction);
    }

    clear() {
        this.nodes.clear();
        this.edges.clear();
        this.knownNodes.clear();
        this.knownEdges.clear();
        this.activeFilter = 'all';
        const btnAll = document.getElementById("btnFilterAll");
        if (btnAll) {
            const filterBtns = ["btnFilterAll", "btnFilter2xx", "btnFilter3xx", "btnFilter4xx", "btnFilter5xx"];
            filterBtns.forEach(id => {
                const btn = document.getElementById(id);
                if (btn) {
                    if (id === "btnFilterAll") {
                        btn.classList.add("active");
                    } else {
                        btn.classList.remove("active");
                    }
                }
            });
        }
    }

    addPath(path, statusCode) {
        if (!this.network) {
            this.init(this.currentDirection);
        }

        // Clean path and break into components
        const cleanPath = path.replace(/^\/+/, '').replace(/\/+$/, '');
        const segments = cleanPath ? cleanPath.split('/') : [];
        
        let parentId = 'root';
        
        // Ensure Root exists
        if (!this.knownNodes.has('root')) {
            this.nodes.add({
                id: 'root',
                label: 'HOST ROOT',
                color: {
                    background: '#071426',
                    border: '#0077ff',
                    highlight: { background: '#071426', border: '#00ff99' }
                },
                size: 25,
                title: 'Target Root URL'
            });
            this.knownNodes.add('root');
        }

        let currentPath = '';
        for (let i = 0; i < segments.length; i++) {
            const segment = segments[i];
            currentPath += (currentPath ? '/' : '') + segment;
            
            const isLast = (i === segments.length - 1);
            const nodeId = 'node_' + currentPath;

            if (!this.knownNodes.has(nodeId)) {
                // Determine color based on status code
                let nodeColor = {
                    background: '#0b1020',
                    border: '#8b9bb4',
                    highlight: { background: '#0b1020', border: '#00ff99' }
                };

                if (isLast && statusCode) {
                    const family = Math.floor(statusCode / 100);
                    if (family === 2) {
                        nodeColor.border = '#00ff99';
                        nodeColor.background = '#061a12';
                    } else if (family === 3) {
                        nodeColor.border = '#ffd34d';
                        nodeColor.background = '#1a180e';
                    } else if (family === 4) {
                        nodeColor.border = '#ff9800';
                        nodeColor.background = '#1a1206';
                    } else if (family === 5) {
                        nodeColor.border = '#ff4d5e';
                        nodeColor.background = '#1a090b';
                    }
                }

                this.nodes.add({
                    id: nodeId,
                    label: '/' + segment,
                    color: nodeColor,
                    title: `Path: /${currentPath}` + (isLast && statusCode ? ` (HTTP ${statusCode})` : ''),
                    statusCode: isLast ? statusCode : null,
                    isLast: isLast
                });
                this.knownNodes.add(nodeId);
            } else if (isLast && statusCode) {
                // Node already exists, but now we have a status code for it! Update it.
                let nodeColor = {
                    background: '#0b1020',
                    border: '#8b9bb4',
                    highlight: { background: '#0b1020', border: '#00ff99' }
                };
                const family = Math.floor(statusCode / 100);
                if (family === 2) {
                    nodeColor.border = '#00ff99';
                    nodeColor.background = '#061a12';
                } else if (family === 3) {
                    nodeColor.border = '#ffd34d';
                    nodeColor.background = '#1a180e';
                } else if (family === 4) {
                    nodeColor.border = '#ff9800';
                    nodeColor.background = '#1a1206';
                } else if (family === 5) {
                    nodeColor.border = '#ff4d5e';
                    nodeColor.background = '#1a090b';
                }

                this.nodes.update({
                    id: nodeId,
                    color: nodeColor,
                    title: `Path: /${currentPath} (HTTP ${statusCode})`,
                    statusCode: statusCode,
                    isLast: true
                });
            }

            // Create Edge
            const edgeId = `${parentId}->${nodeId}`;
            if (!this.knownEdges.has(edgeId)) {
                this.edges.add({
                    id: edgeId,
                    from: parentId,
                    to: nodeId
                });
                this.knownEdges.add(edgeId);
            }

            parentId = nodeId;
        }
    }

    applyFilter(filterType) {
        this.activeFilter = filterType; // 'all', '2xx', '3xx', '4xx', '5xx'
        
        // 1. Determine which nodes match the filter
        const allNodes = this.nodes.get();
        const visibleNodes = new Set();
        
        // Root is always visible
        visibleNodes.add('root');
        
        // Identify directly matching nodes
        allNodes.forEach(node => {
            if (node.id === 'root') return;
            
            let isMatch = false;
            if (filterType === 'all') {
                isMatch = true;
            } else {
                const targetFamily = parseInt(filterType.charAt(0)); // 2, 3, 4, or 5
                if (node.statusCode) {
                    const family = Math.floor(node.statusCode / 100);
                    if (family === targetFamily) {
                        isMatch = true;
                    }
                }
            }
            
            if (isMatch) {
                visibleNodes.add(node.id);
                
                // Add all parent/ancestor node IDs of this visible node
                if (node.id.startsWith('node_')) {
                    const cleanPath = node.id.replace(/^node_/, '');
                    const segments = cleanPath.split('/');
                    let ancestorPath = '';
                    for (let i = 0; i < segments.length - 1; i++) {
                        ancestorPath += (ancestorPath ? '/' : '') + segments[i];
                        visibleNodes.add('node_' + ancestorPath);
                    }
                }
            }
        });
        
        // 2. Update nodes hidden status
        const nodesUpdate = [];
        allNodes.forEach(node => {
            const shouldBeHidden = !visibleNodes.has(node.id);
            if (node.hidden !== shouldBeHidden) {
                nodesUpdate.push({ id: node.id, hidden: shouldBeHidden });
            }
        });
        if (nodesUpdate.length > 0) {
            this.nodes.update(nodesUpdate);
        }
        
        // 3. Update edges hidden status
        const allEdges = this.edges.get();
        const edgesUpdate = [];
        allEdges.forEach(edge => {
            const shouldBeHidden = !visibleNodes.has(edge.from) || !visibleNodes.has(edge.to);
            if (edge.hidden !== shouldBeHidden) {
                edgesUpdate.push({ id: edge.id, hidden: shouldBeHidden });
            }
        });
        if (edgesUpdate.length > 0) {
            this.edges.update(edgesUpdate);
        }
    }
}

// Global instance
window.liveGraph = new LiveGraph('visGraphContainer');
