import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { Auth0Provider } from '@auth0/auth0-react'

const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN
const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID
// const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE; // For API protection

if (!auth0Domain || !auth0ClientId) {
  console.error(
    "Auth0 domain or client ID not found. Please set VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID in your .env file."
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Auth0Provider
      domain={auth0Domain || ""} // Fallback to empty string if undefined to avoid runtime error, though app won't work
      clientId={auth0ClientId || ""} // Fallback
      authorizationParams={{
        redirect_uri: window.location.origin,
        // audience: auth0Audience, // Uncomment if you have an API audience
      }}
      // cacheLocation="localstorage" // Consider for better UX persistence
    >
      <App />
    </Auth0Provider>
  </StrictMode>,
)
