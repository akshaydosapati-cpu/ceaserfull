import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import favicon from '@/public/favicon.png'
import appIcon from '@/public/app-icon.png'
import './globals.css'

export const metadata: Metadata = {
  title: 'CEASER - Personal Intelligence Operating System',
  description: 'Your AI Workforce is ready. Manage your personal AI agents with CEASER OS.',
  generator: 'CEASER',
  icons: {
    icon: favicon.src,
    apple: appIcon.src,
  },
}

export const viewport: Viewport = {
  themeColor: '#0a0f1a',
  colorScheme: 'dark',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="bg-background">
      <body className="font-sans antialiased">
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
