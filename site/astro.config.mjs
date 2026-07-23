import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://gtsummertracker.example',
  redirects: {
    // Stats reclaimed the home slot (2026-07-23); old dashboard links land home.
    '/stats': '/',
  },
});
