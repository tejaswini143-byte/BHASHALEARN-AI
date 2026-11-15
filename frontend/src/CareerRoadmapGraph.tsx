import { useMemo } from "react";
import {
  Background, Controls, MarkerType, MiniMap, ReactFlow, type Edge, type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./career-roadmap-graph.css";

export type RoadmapGraphPhase = {
  skill_key: string;
  title: string;
  title_te?: string;
  prerequisite_skills: string[];
  milestone_id: string;
  completed: boolean;
  estimated_hours: number;
  resources?: { title: string; url: string }[];
};

export function CareerRoadmapGraph({ phases, onSelect }: {
  phases: RoadmapGraphPhase[];
  onSelect: (milestoneId: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const index = new Map(phases.map((phase, i) => [phase.skill_key, i]));
    const nodes: Node[] = phases.map((phase, i) => ({
      id: phase.skill_key,
      position: { x: 40 + i * 270, y: 70 },
      data: { label: `${phase.completed ? "✓ " : ""}${phase.title}\n${phase.estimated_hours} hours · ${phase.resources?.length ?? 0} resources` },
      className: phase.completed ? "roadmap-flow-node roadmap-flow-node-done" : "roadmap-flow-node",
      style: { width: 225, whiteSpace: "pre-line" as const },
    }));
    const edges: Edge[] = phases.flatMap(phase => phase.prerequisite_skills
      .filter(skill => index.has(skill))
      .map(skill => ({
        id: `${skill}-${phase.skill_key}`,
        source: skill,
        target: phase.skill_key,
        label: "prerequisite",
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: !phase.completed,
        style: { stroke: phase.completed ? "#36a477" : "#8b90a2", strokeWidth: 2 },
      })));
    return { nodes, edges };
  }, [phases]);

  return <section className="roadmap-graph-wrap" aria-label="Interactive career roadmap">
    <div className="roadmap-graph-heading"><h3>Skill dependencies</h3><span>Drag to explore · select a node to open its milestone</span></div>
    <div className="roadmap-graph-canvas">
      <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false} nodesConnectable={false} onNodeClick={(_, node) => {
          const phase = phases.find(item => item.skill_key === node.id);
          if (phase) onSelect(phase.milestone_id);
        }} aria-label="Roadmap skill graph">
        <MiniMap pannable zoomable />
        <Controls />
        <Background gap={20} size={1} />
      </ReactFlow>
    </div>
  </section>;
}
