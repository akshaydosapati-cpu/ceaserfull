import type { Metadata, Viewport } from 'next'
import Script from 'next/script'
import favicon from '@/public/favicon.png'
import appIcon from '@/public/app-icon.png'
import './globals.css'

export const metadata: Metadata = {
  metadataBase: new URL('https://www.heyceaser.in'),
  title: 'CEASER - Personal Intelligence Operating System',
  description: 'Your AI Workforce is ready. Manage your personal AI agents with CEASER OS.',
  generator: 'CEASER',
  alternates: { canonical: '/console/' },
  robots: { index: false, follow: false },
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
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-Q9Y3R8G0NH"
          strategy="afterInteractive"
        />
        <Script id="ceaser-ga4" strategy="afterInteractive">
          {`
            if (location.hostname === 'heyceaser.in' || location.hostname === 'www.heyceaser.in') {
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-Q9Y3R8G0NH');
            }
          `}
        </Script>
      </body>
    </html>
  )
}
