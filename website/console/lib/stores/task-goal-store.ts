"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface Task {
  id: string
  title: string
  dueDate: string
  dueTime?: string
  completed: boolean
  priority: "low" | "medium" | "high"
  agentId?: string
  projectId?: string
}

export interface Goal {
  id: string
  title: string
  description?: string
  progress: number
  targetDate?: string
  agentId?: string
  milestones?: { id: string; title: string; completed: boolean }[]
}

export interface CalendarEvent {
  id: string
  title: string
  date: string
  startTime: string
  endTime?: string
  attendees?: { name: string; avatar?: string }[]
  agentId?: string
  type?: "meeting" | "task" | "reminder" | "event"
}

const defaultTasks: Task[] = [
  {
    id: "1",
    title: "Review growth strategy",
    dueDate: "Today",
    dueTime: "10:00 AM",
    completed: false,
    priority: "high",
    agentId: "zeus"
  },
  {
    id: "2",
    title: "Analyze revenue model",
    dueDate: "Today",
    dueTime: "1:30 PM",
    completed: false,
    priority: "medium",
    agentId: "zeus"
  },
  {
    id: "3",
    title: "Content approval",
    dueDate: "Tomorrow",
    dueTime: "11:00 AM",
    completed: false,
    priority: "medium",
    agentId: "friday"
  },
  {
    id: "4",
    title: "Investor update email",
    dueDate: "Tomorrow",
    dueTime: "4:00 PM",
    completed: false,
    priority: "low",
    agentId: "zeus"
  },
  {
    id: "5",
    title: "Research competitor pricing",
    dueDate: "May 27",
    dueTime: "2:00 PM",
    completed: false,
    priority: "medium",
    agentId: "nova"
  },
  {
    id: "6",
    title: "Schedule social posts",
    dueDate: "May 28",
    completed: false,
    priority: "low",
    agentId: "friday"
  }
]

const defaultGoals: Goal[] = [
  {
    id: "1",
    title: "Raise $500K seed funding",
    description: "Close seed round by Q3 2026",
    progress: 40,
    targetDate: "Sep 30, 2026",
    agentId: "zeus",
    milestones: [
      { id: "1a", title: "Prepare pitch deck", completed: true },
      { id: "1b", title: "Contact investors", completed: true },
      { id: "1c", title: "First investor meeting", completed: false },
      { id: "1d", title: "Term sheet negotiation", completed: false }
    ]
  },
  {
    id: "2",
    title: "Launch MVP by June",
    description: "Ship minimum viable product",
    progress: 70,
    targetDate: "Jun 30, 2026",
    agentId: "atlas",
    milestones: [
      { id: "2a", title: "Core features complete", completed: true },
      { id: "2b", title: "Beta testing", completed: true },
      { id: "2c", title: "Bug fixes", completed: false },
      { id: "2d", title: "Launch", completed: false }
    ]
  },
  {
    id: "3",
    title: "Build email list to 10K",
    description: "Grow newsletter subscribers",
    progress: 35,
    targetDate: "Dec 31, 2026",
    agentId: "friday",
    milestones: [
      { id: "3a", title: "Create lead magnet", completed: true },
      { id: "3b", title: "Launch landing page", completed: false },
      { id: "3c", title: "Run first campaign", completed: false }
    ]
  },
  {
    id: "4",
    title: "Run 100 miles this month",
    description: "Personal fitness goal",
    progress: 60,
    targetDate: "May 31, 2026",
    agentId: "alex"
  }
]

const defaultEvents: CalendarEvent[] = [
  {
    id: "1",
    title: "Team Standup",
    date: "2026-05-25",
    startTime: "10:00 AM",
    endTime: "10:30 AM",
    type: "meeting",
    attendees: [
      { name: "Alex" },
      { name: "Sarah" },
      { name: "Mike" },
      { name: "John" },
      { name: "Emma" }
    ]
  },
  {
    id: "2",
    title: "Investor Call",
    date: "2026-05-26",
    startTime: "2:00 PM",
    endTime: "3:00 PM",
    type: "meeting",
    agentId: "zeus"
  },
  {
    id: "3",
    title: "Content Review",
    date: "2026-05-27",
    startTime: "11:00 AM",
    endTime: "12:00 PM",
    type: "meeting",
    agentId: "friday"
  },
  {
    id: "4",
    title: "Sprint Planning",
    date: "2026-05-28",
    startTime: "9:00 AM",
    endTime: "10:30 AM",
    type: "meeting",
    agentId: "atlas"
  }
]

interface TaskGoalStore {
  tasks: Task[]
  goals: Goal[]
  events: CalendarEvent[]

  // Task actions
  addTask: (task: Omit<Task, "id">) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  deleteTask: (id: string) => void
  toggleTaskComplete: (id: string) => void
  getTasksByAgent: (agentId: string) => Task[]
  getTasksByDate: (date: string) => Task[]
  getIncompleteTasks: () => Task[]

  // Goal actions
  addGoal: (goal: Omit<Goal, "id">) => void
  updateGoal: (id: string, updates: Partial<Goal>) => void
  deleteGoal: (id: string) => void
  toggleMilestone: (goalId: string, milestoneId: string) => void
  getGoalsByAgent: (agentId: string) => Goal[]

  // Event actions
  addEvent: (event: Omit<CalendarEvent, "id">) => void
  updateEvent: (id: string, updates: Partial<CalendarEvent>) => void
  deleteEvent: (id: string) => void
  getEventsByDate: (date: string) => CalendarEvent[]
  getUpcomingEvents: (limit?: number) => CalendarEvent[]
}

export const useTaskGoalStore = create<TaskGoalStore>()(
  persist(
    (set, get) => ({
      tasks: defaultTasks,
      goals: defaultGoals,
      events: defaultEvents,

      // Task actions
      addTask: (task: Omit<Task, "id">) => {
        const id = Date.now().toString()
        set((state) => ({
          tasks: [{ ...task, id }, ...state.tasks]
        }))
      },

      updateTask: (id: string, updates: Partial<Task>) => {
        set((state) => ({
          tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t))
        }))
      },

      deleteTask: (id: string) => {
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id)
        }))
      },

      toggleTaskComplete: (id: string) => {
        set((state) => ({
          tasks: state.tasks.map((t) =>
            t.id === id ? { ...t, completed: !t.completed } : t
          )
        }))
      },

      getTasksByAgent: (agentId: string) => {
        return get().tasks.filter((t) => t.agentId === agentId)
      },

      getTasksByDate: (date: string) => {
        return get().tasks.filter((t) => t.dueDate === date)
      },

      getIncompleteTasks: () => {
        return get().tasks.filter((t) => !t.completed)
      },

      // Goal actions
      addGoal: (goal: Omit<Goal, "id">) => {
        const id = Date.now().toString()
        set((state) => ({
          goals: [{ ...goal, id }, ...state.goals]
        }))
      },

      updateGoal: (id: string, updates: Partial<Goal>) => {
        set((state) => ({
          goals: state.goals.map((g) => (g.id === id ? { ...g, ...updates } : g))
        }))
      },

      deleteGoal: (id: string) => {
        set((state) => ({
          goals: state.goals.filter((g) => g.id !== id)
        }))
      },

      toggleMilestone: (goalId: string, milestoneId: string) => {
        set((state) => ({
          goals: state.goals.map((g) => {
            if (g.id !== goalId || !g.milestones) return g
            const updatedMilestones = g.milestones.map((m) =>
              m.id === milestoneId ? { ...m, completed: !m.completed } : m
            )
            const completedCount = updatedMilestones.filter((m) => m.completed).length
            const progress = Math.round((completedCount / updatedMilestones.length) * 100)
            return { ...g, milestones: updatedMilestones, progress }
          })
        }))
      },

      getGoalsByAgent: (agentId: string) => {
        return get().goals.filter((g) => g.agentId === agentId)
      },

      // Event actions
      addEvent: (event: Omit<CalendarEvent, "id">) => {
        const id = Date.now().toString()
        set((state) => ({
          events: [...state.events, { ...event, id }]
        }))
      },

      updateEvent: (id: string, updates: Partial<CalendarEvent>) => {
        set((state) => ({
          events: state.events.map((e) => (e.id === id ? { ...e, ...updates } : e))
        }))
      },

      deleteEvent: (id: string) => {
        set((state) => ({
          events: state.events.filter((e) => e.id !== id)
        }))
      },

      getEventsByDate: (date: string) => {
        return get().events.filter((e) => e.date === date)
      },

      getUpcomingEvents: (limit = 5) => {
        return get().events.slice(0, limit)
      }
    }),
    {
      name: "ceaser-task-goal-store"
    }
  )
)
