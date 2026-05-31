// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: process.env.ASTRO_SITE ?? 'https://teles.dev.br',
  base: process.env.ASTRO_BASE ?? '/passaportepinheiros',
  vite: {
    plugins: [tailwindcss()],
  },
});
