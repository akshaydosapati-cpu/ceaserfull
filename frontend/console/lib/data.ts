import {
  ceaserAgents,
  ceaserUser,
  type CeaserAgent,
} from "@/lib/ceaser"
import type { LucideIcon } from "lucide-react"

export type Agent = CeaserAgent
export type AgentStatus = CeaserAgent["status"]
export const agents = ceaserAgents.filter((agent) => agent.id !== "ceaser")

export interface Memory {
  id: string
  title: string
  description: string
  date: string
  type: "goal" | "meeting" | "document" | "research" | "conversation" | "project" | "note" | "file"
  agentId?: string
  icon?: LucideIcon
}

export interface Task {
  id: string
  title: string
  dueDate: string
  dueTime?: string
  completed: boolean
  priority?: "low" | "medium" | "high"
}

export interface Event {
  id: string
  title: string
  date: string
  startTime: string
  endTime?: string
  attendees?: { name: string; avatar?: string }[]
}

export interface Project {
  id: string
  name: string
  status: "ongoing" | "planning" | "completed" | "paused"
  progress: number
  agentId?: string
}

export const memories: Memory[] = [
  {
    id: "1",
    title: "CliniLocker Funding Goal",
    description: "Goal set on May 24, 2026",
    date: "May 24, 2026",
    type: "goal"
  },
  {
    id: "2",
    title: "Meeting with Investor",
    description: "Discussed on May 22, 2026",
    date: "May 22, 2026",
    type: "meeting"
  },
  {
    id: "3",
    title: "Product Roadmap v2",
    description: "Updated on May 20, 2026",
    date: "May 20, 2026",
    type: "document"
  },
  {
    id: "4",
    title: "Competitor Analysis",
    description: "Researched on May 19, 2026",
    date: "May 19, 2026",
    type: "research"
  }
]

export const tasks: Task[] = [
  {
    id: "1",
    title: "Review growth strategy",
    dueDate: "Today",
    dueTime: "10:00 AM",
    completed: false,
    priority: "high"
  },
  {
    id: "2",
    title: "Analyze revenue model",
    dueDate: "Today",
    dueTime: "1:30 PM",
    completed: false,
    priority: "medium"
  },
  {
    id: "3",
    title: "Content approval",
    dueDate: "Tomorrow",
    dueTime: "11:00 AM",
    completed: false,
    priority: "medium"
  },
  {
    id: "4",
    title: "Investor update email",
    dueDate: "Tomorrow",
    dueTime: "4:00 PM",
    completed: false,
    priority: "low"
  }
]

export const events: Event[] = [
  {
    id: "1",
    title: "Team Standup",
    date: "May 25",
    startTime: "10:00 AM",
    endTime: "10:30 AM",
    attendees: [
      { name: "Alex" },
      { name: "Sarah" },
      { name: "Mike" },
      { name: "John" },
      { name: "Emma" }
    ]
  }
]

export const projects: Project[] = [
  {
    id: "1",
    name: "CliniLocker",
    status: "ongoing",
    progress: 70,
    agentId: "zeus"
  },
  {
    id: "2",
    name: "AI Research",
    status: "ongoing",
    progress: 45,
    agentId: "nova"
  },
  {
    id: "3",
    name: "Content Hub",
    status: "planning",
    progress: 30,
    agentId: "friday"
  },
  {
    id: "4",
    name: "Personal Fitness Plan",
    status: "ongoing",
    progress: 60,
    agentId: "alex"
  },
  {
    id: "5",
    name: "Marketing Strategy",
    status: "ongoing",
    progress: 55
  },
  {
    id: "6",
    name: "SaaS Idea Validation",
    status: "planning",
    progress: 20
  }
]

export const briefItems = [
  { agent: "Zeus", action: "analyzed revenue growth", time: "2m ago", agentId: "zeus" },
  { agent: "Nova", action: "completed competitor research", time: "15m ago", agentId: "nova" },
  { agent: "Friday", action: "scheduled 3 posts", time: "45m ago", agentId: "friday" },
  { agent: "Bolt", action: "automated weekly report", time: "1h ago", agentId: "bolt" }
]

export const stats = {
  projects: 3,
  tasks: 18,
  goals: 12,
  agentsActive: 5,
  agentsTotal: 6,
  tasksRunning: 14,
  tasksCompleted: 28
}

export const user = ceaserUser
