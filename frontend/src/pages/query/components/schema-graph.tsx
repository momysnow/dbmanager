import { useEffect, useState } from "react";
import {
  ReactFlow,
  Handle,
  Position,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import type { Node, Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import api from "@/services/api";
import { Loader2, Key } from "lucide-react";

interface Column {
  name: string;
  type: string;
  nullable: boolean;
  isPrimary: boolean;
}

interface TableDef {
  id: string;
  name: string;
  columns: Column[];
}

interface EdgeDef {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
}

interface SchemaData {
  tables: TableDef[];
  edges: EdgeDef[];
}

// Custom Node to display a Database Table
const TableNode = ({ data }: { data: TableDef }) => {
  return (
    <div className="bg-card border rounded-lg shadow-sm min-w-[250px] font-sans text-sm">
      <div className="px-3 py-2 border-b bg-muted/30 font-semibold text-primary rounded-t-lg flex items-center justify-between">
        <span>{data.name}</span>
      </div>
      <div className="flex flex-col py-1">
        {data.columns.map((col) => (
          <div
            key={col.name}
            className={`px-3 py-1 flex justify-between relative hover:bg-muted/50 ${
              col.isPrimary ? "bg-primary/5" : ""
            }`}
          >
            {/* Target Handle (Incoming Foreign Key) */}
            <Handle
              type="target"
              position={Position.Left}
              id={col.name}
              className="!w-px !h-px !min-w-0 !min-h-0 !opacity-0 !border-0 !bg-transparent"
            />
            
            <div className="flex items-center gap-2 text-foreground font-mono text-xs w-full">
              {col.isPrimary && <Key className="h-3 w-3 text-amber-500" />}
              <span className={col.isPrimary ? "font-semibold" : ""}>{col.name}</span>
              <span className="text-muted-foreground ml-auto">{col.type}</span>
            </div>

            {/* Source Handle (Outgoing Foreign Key) */}
            <Handle
              type="source"
              position={Position.Right}
              id={col.name}
              className="!w-px !h-px !min-w-0 !min-h-0 !opacity-0 !border-0 !bg-transparent"
            />
          </div>
        ))}
      </div>
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

// Dagre Layout Algorithm
const getLayoutedElements = (nodes: { id: string }[], edges: { source: string; target: string }[], direction = "LR") => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const nodeWidth = 300;
  const nodeHeight = 250;

  dagreGraph.setGraph({ rankdir: direction, ranksep: 100, nodesep: 50 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const newNode = {
      ...node,
      targetPosition: Position.Left,
      sourcePosition: Position.Right,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
    return newNode;
  });

  return { nodes: newNodes, edges };
};

export default function SchemaGraph({ databaseId }: { databaseId: number }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSchema() {
      if (!databaseId) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const response = await api.get(`/databases/${databaseId}/schema`);
        const data: SchemaData = response.data;
        
        // Transform API data to ReactFlow structure
        const initialNodes = data.tables.map((table) => ({
          id: table.id,
          type: "tableNode",
          data: table,
          position: { x: 0, y: 0 },
        }));

        const initialEdges = data.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
          animated: true,
          style: { stroke: "hsl(var(--primary))", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "hsl(var(--primary))",
          },
        }));

        // Apply automatic layouting
        const layouted = getLayoutedElements(initialNodes, initialEdges);
        
        // Ensure layouted conforms to Node[] and Edge[] types correctly
        setNodes(layouted.nodes as Node[]);
        setEdges(layouted.edges as Edge[]);
      } catch (err: unknown) {
        console.error("Failed to load schema:", err);
        setError("Could not extract database schema. Make sure the database is online and its provider supports schema extraction.");
      } finally {
        setLoading(false);
      }
    }

    loadSchema();
  }, [databaseId, setNodes, setEdges]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p>Extracting schema and building graph...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center text-destructive p-8 max-w-md mx-auto">
        <p className="font-semibold mb-2">Schema Extraction Failed</p>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground p-8">
        <p>No tables found in this database.</p>
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-muted/10">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        className="w-full h-full"
        minZoom={0.1}
      >
        <Background gap={24} size={2} color="hsl(var(--muted-foreground))" />
        <Controls />
      </ReactFlow>
    </div>
  );
}
