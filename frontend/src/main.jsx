import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initializeAuth } from './utils/api';
import './styles/global.css';

// Initialize authentication from stored token
initializeAuth();

// Mount React app to DOM
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
