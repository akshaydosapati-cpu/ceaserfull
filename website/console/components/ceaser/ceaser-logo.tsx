"use client"

import Image from "next/image"
import type { StaticImageData } from "next/image"
import { cn } from "@/lib/utils"
import defaultLogo from "@/public/logo.png"

interface CeaserLogoProps {
  size?: "sm" | "md" | "lg"
  showText?: boolean
  showIcon?: boolean
  iconSrc?: string | StaticImageData
  className?: string
}

export function CeaserLogo({ size = "md", showText = true, showIcon = true, iconSrc = defaultLogo, className }: CeaserLogoProps) {
  const sizeClasses = {
    sm: "h-6 w-6",
    md: "h-8 w-8",
    lg: "h-12 w-12"
  }

  const imageSizes = {
    sm: 24,
    md: 32,
    lg: 48
  }

  const textSizes = {
    sm: "text-sm",
    md: "text-lg",
    lg: "text-2xl"
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {showIcon && (
        <div className={cn("relative overflow-hidden rounded-md", sizeClasses[size])}>
          <Image
            src={iconSrc}
            alt="CEASER logo"
            width={imageSizes[size]}
            height={imageSizes[size]}
            className="h-full w-full object-contain"
            priority
          />
        </div>
      )}

      {showText && (
        <span className={cn("font-semibold tracking-wide text-foreground", textSizes[size])}>
          CEASER
        </span>
      )}
    </div>
  )
}
