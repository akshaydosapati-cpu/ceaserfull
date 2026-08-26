"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

export type CeaserSelectOption = {
  value: string
  label: string
  description?: string
}

export function CeaserSelect({
  value,
  onValueChange,
  options,
  placeholder = "Select",
  className,
  triggerClassName,
}: {
  value: string
  onValueChange: (value: string) => void
  options: CeaserSelectOption[]
  placeholder?: string
  className?: string
  triggerClassName?: string
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger
        className={cn(
          "h-11 w-full rounded-xl border border-border bg-card/80 px-3 text-sm font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] outline-none transition hover:border-primary/45 hover:bg-secondary/70 focus:ring-2 focus:ring-primary/25",
          triggerClassName,
          className,
        )}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="z-[80] overflow-hidden rounded-2xl border border-border bg-popover p-1 text-popover-foreground shadow-[0_22px_60px_rgba(0,0,0,0.22)] backdrop-blur-xl">
        {options.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            className="rounded-xl px-3 py-2.5 text-sm text-foreground outline-none transition focus:bg-primary/15 focus:text-primary data-[state=checked]:bg-primary/12 data-[state=checked]:text-primary"
          >
            <OptionLabel label={option.label} description={option.description} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function OptionLabel({ label, description }: { label: string; description?: string }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate">{label}</span>
      {description && <span className="truncate text-xs text-muted-foreground">{description}</span>}
    </span>
  )
}
