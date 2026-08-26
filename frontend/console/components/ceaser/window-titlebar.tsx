import React, { useState, useEffect } from "react"
import { Minus, Square, X } from "lucide-react"
import styles from "./window-titlebar.module.css"

declare global {
  interface Window {
    ceaserDesktop?: {
      windowMinimize?: () => Promise<void>
      windowMaximize?: () => Promise<void>
      windowClose?: () => Promise<void>
      windowIsMaximized?: () => Promise<boolean>
    }
  }
}

export function WindowTitlebar() {
  const [isMaximized, setIsMaximized] = useState(false)

  useEffect(() => {
    checkMaximized()
    const interval = setInterval(checkMaximized, 500)
    return () => clearInterval(interval)
  }, [])

  const checkMaximized = async () => {
    if ((window as any).ceaserDesktop?.windowIsMaximized) {
      const maximized = await (window as any).ceaserDesktop.windowIsMaximized()
      setIsMaximized(maximized)
    }
  }

  const handleMinimize = () => (window as any).ceaserDesktop?.windowMinimize?.()
  const handleMaximize = () => {
    (window as any).ceaserDesktop?.windowMaximize?.()
    setTimeout(checkMaximized, 100)
  }
  const handleClose = () => (window as any).ceaserDesktop?.windowClose?.()

  return (
    <div className={styles.titlebar}>
      <div className={styles.branding}>
        <div className={styles.logo}>
          <span>C</span>
        </div>
        <span className={styles.appName}>CEASER</span>
      </div>
      <div className={styles.spacer} />
      <div className={styles.controls}>
        <button
          onClick={handleMinimize}
          className={styles.controlBtn}
          title="Minimize"
          aria-label="Minimize window"
        >
          <Minus size={16} />
        </button>
        <button
          onClick={handleMaximize}
          className={styles.controlBtn}
          title={isMaximized ? "Restore" : "Maximize"}
          aria-label={isMaximized ? "Restore window" : "Maximize window"}
        >
          <Square size={16} />
        </button>
        <button
          onClick={handleClose}
          className={`${styles.controlBtn} ${styles.closeBtn}`}
          title="Close"
          aria-label="Close window"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  )
}
