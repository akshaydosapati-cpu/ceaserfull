"""
Template Library - Pre-built templates for common frameworks
"""

from typing import Dict, List, Any

class TemplateLibrary:
    """Collection of project templates for different frameworks"""
    
    def __init__(self):
        self.templates = {
            "react": {
                "package.json": {
                    "name": "{project_name}",
                    "version": "1.0.0",
                    "scripts": {
                        "dev": "vite",
                        "build": "vite build",
                        "preview": "vite preview"
                    },
                    "dependencies": {
                        "react": "^18.2.0",
                        "react-dom": "^18.2.0"
                    },
                    "devDependencies": {
                        "vite": "^5.0.0",
                        "@vitejs/plugin-react": "^4.2.0"
                    }
                },
                "vite.config.js": 'import react from "@vitejs/plugin-react"\nexport default {\n  plugins: [react()],\n}',
                "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>""",
                "src/main.jsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)""",
                "src/App.jsx": """import { useState } from 'react'
import './App.css'

function App() {
  return (
    <div className="app">
      <h1>{project_name}</h1>
      <p>Welcome to your new app!</p>
    </div>
  )
}

export default App""",
                "src/index.css": """* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}""",
                "src/App.css": ""
            },
            "nextjs": {
                "package.json": {
                    "name": "{project_name}",
                    "version": "1.0.0",
                    "scripts": {
                        "dev": "next dev",
                        "build": "next build",
                        "start": "next start"
                    },
                    "dependencies": {
                        "react": "^18.2.0",
                        "react-dom": "^18.2.0",
                        "next": "^14.0.0"
                    }
                },
                "next.config.js": "module.exports = {}",
                "pages/_app.js": """export default function App({ Component, pageProps }) {
  return <Component {...pageProps} />
}""",
                "pages/index.js": """export default function Home() {
  return (
    <div>
      <h1>{project_name}</h1>
      <p>Welcome to your Next.js app!</p>
    </div>
  )
}"""
            },
            "vue": {
                "package.json": {
                    "name": "{project_name}",
                    "version": "1.0.0",
                    "scripts": {
                        "dev": "vite",
                        "build": "vite build",
                        "preview": "vite preview"
                    },
                    "dependencies": {
                        "vue": "^3.3.0"
                    },
                    "devDependencies": {
                        "vite": "^5.0.0",
                        "@vitejs/plugin-vue": "^4.5.0"
                    }
                },
                "vite.config.js": """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()]
})""",
                "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
</head>
<body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
</body>
</html>""",
                "src/main.js": """import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

createApp(App).mount('#app')""",
                "src/App.vue": """<template>
  <div class="app">
    <h1>{{ projectName }}</h1>
    <p>Welcome to your Vue app!</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      projectName: '{project_name}'
    }
  }
}
</script>

<style>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>"""
            }
        }
    
    def get_template(self, framework: str) -> Dict[str, Any]:
        """Get template files for a framework"""
        return self.templates.get(framework.lower(), self.templates["react"])
    
    def list_frameworks(self) -> List[str]:
        """List available frameworks"""
        return list(self.templates.keys())

