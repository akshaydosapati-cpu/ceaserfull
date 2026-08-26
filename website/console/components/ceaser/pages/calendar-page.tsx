"use client"

import { useState } from "react"
import { agents, events, type Event as BaseCalendarEvent } from "@/lib/data"
import { AgentAvatar } from "../agent-avatar"
import { GlowCard } from "../glow-card"
import { cn } from "@/lib/utils"
import { 
  Plus, 
  ChevronLeft, 
  ChevronRight,
  Clock,
  Users
} from "lucide-react"

type CalendarEvent = BaseCalendarEvent & {
  agentId?: string
  type?: string
}

const calendarEvents: CalendarEvent[] = [
  ...events,
  {
    id: "2",
    title: "Product Review",
    date: "May 26",
    startTime: "2:00 PM",
    endTime: "3:00 PM",
    agentId: "zeus",
    type: "meeting"
  },
  {
    id: "3",
    title: "Content Planning",
    date: "May 27",
    startTime: "11:00 AM",
    endTime: "12:00 PM",
    agentId: "friday",
    type: "task"
  },
  {
    id: "4",
    title: "Investor Call",
    date: "May 28",
    startTime: "4:00 PM",
    endTime: "5:00 PM",
    type: "meeting"
  }
]

const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
const currentMonth = "May 2026"

// Generate calendar days
const generateCalendarDays = () => {
  const daysInMonth = 31 // May has 31 days
  const firstDayOfWeek = 5 // May 2026 starts on Friday
  const calendarDays = []
  
  // Add empty cells for days before the 1st
  for (let i = 0; i < firstDayOfWeek; i++) {
    calendarDays.push({ day: null, events: [] })
  }
  
  // Add days of the month
  for (let day = 1; day <= daysInMonth; day++) {
    const dayEvents = calendarEvents.filter(e => {
      const eventDay = parseInt(e.date.split(" ")[1])
      return eventDay === day
    })
    calendarDays.push({ day, events: dayEvents })
  }
  
  return calendarDays
}

export function CalendarPage() {
  const [selectedDate, setSelectedDate] = useState<number | null>(25)
  const calendarDays = generateCalendarDays()

  const selectedDayEvents = selectedDate 
    ? calendarEvents.filter(e => parseInt(e.date.split(" ")[1]) === selectedDate)
    : []

  return (
    <div className="flex h-full">
      {/* Calendar Grid */}
      <div className="flex-1 p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Calendar</h1>
          <button className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
            <Plus className="h-4 w-4" />
            New Event
          </button>
        </div>

        {/* Month Navigation */}
        <div className="mb-6 flex items-center justify-between">
          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h2 className="text-xl font-semibold">{currentMonth}</h2>
          <button className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>

        {/* Days of Week Header */}
        <div className="mb-2 grid grid-cols-7 gap-1">
          {days.map((day) => (
            <div key={day} className="py-2 text-center text-sm font-medium text-muted-foreground">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((item, i) => (
            <button
              key={i}
              onClick={() => item.day && setSelectedDate(item.day)}
              disabled={!item.day}
              className={cn(
                "relative flex h-24 flex-col items-start rounded-lg border p-2 transition-colors",
                item.day 
                  ? "border-border hover:border-primary/50" 
                  : "border-transparent",
                selectedDate === item.day && "border-primary bg-primary/5",
                item.day === 25 && "bg-primary/10" // Today
              )}
            >
              {item.day && (
                <>
                  <span className={cn(
                    "text-sm font-medium",
                    item.day === 25 && "text-primary"
                  )}>
                    {item.day}
                  </span>
                  {item.events.length > 0 && (
                    <div className="mt-1 flex flex-col gap-0.5">
                      {item.events.slice(0, 2).map((event, j) => {
                        const agent = event.agentId 
                          ? agents.find(a => a.id === event.agentId)
                          : null
                        return (
                          <div 
                            key={j}
                            className="truncate rounded px-1 py-0.5 text-xs"
                            style={{ 
                              backgroundColor: agent?.color ? `${agent.color}20` : "var(--secondary)",
                              color: agent?.color || "var(--muted-foreground)"
                            }}
                          >
                            {event.title}
                          </div>
                        )
                      })}
                      {item.events.length > 2 && (
                        <span className="text-xs text-muted-foreground">
                          +{item.events.length - 2} more
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Event Details Sidebar */}
      <aside className="w-80 border-l border-border bg-card/50 p-4">
        <h2 className="mb-4 text-lg font-semibold">
          {selectedDate ? `May ${selectedDate}, 2026` : "Select a date"}
        </h2>

        {selectedDayEvents.length > 0 ? (
          <div className="space-y-3">
            {selectedDayEvents.map((event) => {
              const agent = event.agentId 
                ? agents.find(a => a.id === event.agentId)
                : null
              
              return (
                <GlowCard key={event.id} glowColor={agent?.color}>
                  <div className="flex items-start gap-3">
                    {agent ? (
                      <AgentAvatar agent={agent} size="md" showGlow />
                    ) : (
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary">
                        <Clock className="h-5 w-5 text-muted-foreground" />
                      </div>
                    )}
                    <div className="flex-1">
                      <h3 className="font-medium">{event.title}</h3>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {event.startTime} - {event.endTime}
                      </div>
                      {event.attendees && (
                        <div className="mt-2 flex items-center gap-2">
                          <Users className="h-3 w-3 text-muted-foreground" />
                          <div className="flex -space-x-2">
                            {event.attendees.slice(0, 3).map((attendee, i) => (
                              <div 
                                key={i}
                                className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-card bg-secondary text-xs font-medium"
                              >
                                {attendee.name.charAt(0)}
                              </div>
                            ))}
                          </div>
                          {event.attendees.length > 3 && (
                            <span className="text-xs text-muted-foreground">
                              +{event.attendees.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </GlowCard>
              )
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
              <Clock className="h-6 w-6 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">No events scheduled</p>
            <button className="mt-4 flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
              <Plus className="h-4 w-4" />
              Add Event
            </button>
          </div>
        )}
      </aside>
    </div>
  )
}
