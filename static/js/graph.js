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
                    title: `Path: /${currentPath}` + (isLast && statusCode ? ` (HTTP ${statusCode})` : '')
                });
                this.knownNodes.add(nodeId);
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
}

// Global instance
window.liveGraph = new LiveGraph('visGraphContainer');
