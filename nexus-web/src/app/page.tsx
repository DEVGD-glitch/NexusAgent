"use client";

import { Sidebar } from "@/components/nexus/sidebar";
import { AgentsWallPanel } from "@/components/nexus/agents-wall-panel";
import { ChatPanel } from "@/components/nexus/chat-panel";
import { TasksPanel } from "@/components/nexus/tasks-panel";
import { CodePanel } from "@/components/nexus/code-panel";
import { MemoryPanel } from "@/components/nexus/memory-panel";
import { KnowledgePanel } from "@/components/nexus/knowledge-panel";
import { ToolsPanel } from "@/components/nexus/tools-panel";
import { SettingsPanel } from "@/components/nexus/settings-panel";
import { useNexusStore } from "@/lib/nexus-store";

const panels: Record<string, React.ElementType> = {
  agents: AgentsWallPanel,
  chat: ChatPanel,
  tasks: TasksPanel,
  code: CodePanel,
  memory: MemoryPanel,
  knowledge: KnowledgePanel,
  tools: ToolsPanel,
  settings: SettingsPanel,
};

export default function Home() {
  const { activePanel } = useNexusStore();
  const Panel = panels[activePanel] || AgentsWallPanel;

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <Panel />
      </main>
    </div>
  );
}
