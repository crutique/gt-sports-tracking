import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://gtsummertracker.example',
  redirects: {
    // Outlook took the home slot (2026-07-23); old roster-outlook links land home.
    '/outlook': '/',
  },
});
