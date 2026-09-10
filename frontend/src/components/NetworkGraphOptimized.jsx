import React, { useEffect, useRef } from 'react';
import * as sigma from 'sigma';
import { NodeStore, EdgeStore } from 'graphology';
import { SigmaRenderer } from 'sigma/renderers/webgl/WebGLRenderer';
import { assign } from 'lodash';

const NetworkGraphOptimized = ({ nodes, edges, options }) => {
  const sigmaRef = useRef(null);
  const rendererRef = useRef(null);
  const graphRef = useRef(new sigma.classes.Graph());

  useEffect(() => {
    // Initialize Sigma instance
    const container = sigmaRef.current;
    if (!container) return;

    const graph = graphRef.current;
    graph.clear();

    // Add nodes and edges
    nodes.forEach(node => {
      graph.addNode(node.id, { ...node, label: node.label || node.id });
    });

    edges.forEach(edge => {
      graph.addEdge(edge.id, edge.source, edge.target, { ...edge });
    });

    // Create renderer with WebGL for performance
    const renderer = new SigmaRenderer(graph, container, {
      type: 'webgl',
      // Enable label throttling
      labelRenderer: (node, data, context, params) => {
        // Only render labels for nodes with size above threshold or when zoomed in
        if (data.size < 10 || params.ratio < 0.5) return;
        // Default label rendering
        const fontSize = (params.ratio || 1) * 12;
        context.font = `${fontSize}px sans-serif`;
        context.fillStyle = data.color || '#000';
        context.textAlign = 'center';
        context.textBaseline = 'alphabetic';
        context.fillText(data.label || '', 0, 0);
      },
      // Edge throttling: hide edges when too thin or zoomed out
      edgeRenderer: (edge, data, context, params) => {
        if (data.size < 0.5 || params.ratio < 0.3) return;
        // Default edge rendering
        context.lineWidth = data.size || 1;
        context.strokeStyle = data.color || '#aaa';
        context.beginPath();
        context.moveTo(data.x1, data.y1);
        context.lineTo(data.x2, data.y2);
        context.stroke();
      }
    });

    rendererRef.current = renderer;

    // Enable mouse interactions
    graph.refresh();

    // Cleanup on unmount
    return () => {
      renderer.kill();
      graph.clear();
    };
  }, [nodes, edges, options]);

  return <div ref={sigmaRef} style={{ width: '100%', height: '100%' }} />;
};

export default NetworkGraphOptimized;