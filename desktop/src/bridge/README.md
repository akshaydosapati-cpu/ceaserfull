Desktop bridge notes:

- The preload script exposes a narrow `window.ceaserDesktop` API.
- Renderer code does not receive direct Node.js access.
- Backend controls intent classification only. Local desktop actions execute inside the desktop app.
