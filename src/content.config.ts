import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const experiencias = defineCollection({
  loader: glob({
    base: './src/content/experiencias',
    pattern: '**/*.md',
  }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    category: z.enum(['produtos', 'restaurantes', 'servicos']),
    instagram: z.string(),
    instagramUrl: z.string().url(),
    description: z.string(),
    images: z.object({
      experience: z.string(),
      logo: z.string(),
    }),
    source: z.object({
      path: z.string(),
      filename: z.string(),
    }),
  }),
});

export const collections = { experiencias };
