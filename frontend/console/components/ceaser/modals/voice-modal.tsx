"use client"

import { useApp } from "@/lib/app-context"
import { cn } from "@/lib/utils"
import { motion, AnimatePresence } from "framer-motion"
import { Mic, X } from "lucide-react"
import { useState, useEffect } from "react"

export function VoiceModal() {
  const { isVoiceModalOpen, setIsVoiceModalOpen } = useApp()
  const [isListening, setIsListening] = useState(false)
  
  useEffect(() => {
    if (isVoiceModalOpen) {
      const timer = setTimeout(() => setIsListening(true), 500)
      return () => clearTimeout(timer)
    } else {
      setIsListening(false)
    }
  }, [isVoiceModalOpen])

  return (
    <AnimatePresence>
      {isVoiceModalOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
          onClick={() => setIsVoiceModalOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="relative flex flex-col items-center gap-6 p-8"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={() => setIsVoiceModalOpen(false)}
              className="absolute -right-4 -top-4 flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-muted-foreground transition-colors hover:bg-destructive hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Animated rings */}
            <div className="relative flex items-center justify-center">
              {isListening && (
                <>
                  <motion.div
                    className="absolute h-40 w-40 rounded-full border border-primary/20"
                    animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
                  />
                  <motion.div
                    className="absolute h-40 w-40 rounded-full border border-primary/20"
                    animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
                  />
                  <motion.div
                    className="absolute h-40 w-40 rounded-full border border-primary/20"
                    animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: 1 }}
                  />
                </>
              )}
              
              {/* Main mic button */}
              <motion.div
                className={cn(
                  "flex h-32 w-32 items-center justify-center rounded-full transition-all",
                  isListening 
                    ? "bg-primary/20 border-2 border-primary glow-primary-strong" 
                    : "bg-secondary border-2 border-border"
                )}
                animate={isListening ? { scale: [1, 1.05, 1] } : {}}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <Mic className={cn(
                  "h-12 w-12 transition-colors",
                  isListening ? "text-primary" : "text-muted-foreground"
                )} />
              </motion.div>
            </div>

            {/* Status text */}
            <motion.p
              className="text-lg font-medium"
              animate={{ opacity: isListening ? 1 : 0.5 }}
            >
              {isListening ? "Listening..." : "Speak now"}
            </motion.p>

            {/* Wave visualization */}
            <div className="flex items-center gap-1">
              {[...Array(24)].map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1 rounded-full bg-primary"
                  animate={isListening ? {
                    height: [8, 24 + Math.random() * 16, 8],
                  } : { height: 8 }}
                  transition={{
                    duration: 0.5 + Math.random() * 0.3,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: i * 0.05
                  }}
                />
              ))}
            </div>

            {/* Cancel button */}
            <button
              onClick={() => setIsVoiceModalOpen(false)}
              className="mt-4 rounded-lg border border-border px-6 py-2 text-sm transition-colors hover:bg-secondary"
            >
              Cancel
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
