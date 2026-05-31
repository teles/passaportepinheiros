import type { CollectionEntry } from 'astro:content';
import { withBase } from './urls';

export type Experience = CollectionEntry<'experiencias'>;
export type Category = 'produtos' | 'restaurantes' | 'servicos';

export const categories: Array<{ value: Category; label: string; plural: string }> = [
  { value: 'restaurantes', label: 'Restaurante', plural: 'Restaurantes' },
  { value: 'servicos', label: 'Serviço', plural: 'Serviços' },
  { value: 'produtos', label: 'Produto', plural: 'Produtos' },
];

export function categoryLabel(category: Category): string {
  return categories.find((item) => item.value === category)?.plural ?? category;
}

export function categorySingular(category: Category): string {
  return categories.find((item) => item.value === category)?.label ?? category;
}

export function sortExperiences(experiences: Experience[]): Experience[] {
  return [...experiences].sort((a, b) =>
    a.data.title.localeCompare(b.data.title, 'pt-BR', { sensitivity: 'base' }),
  );
}

export function getCategoryCounts(experiences: Experience[]): Record<Category | 'todos', number> {
  const counts: Record<Category | 'todos', number> = {
    todos: experiences.length,
    produtos: 0,
    restaurantes: 0,
    servicos: 0,
  };

  for (const experience of experiences) {
    counts[experience.data.category] += 1;
  }

  return counts;
}

export function compactDescription(description: string, maxLength = 132): string {
  const compact = normalizeDescription(description);

  if (compact.length <= maxLength) {
    return compact;
  }

  return `${compact.slice(0, maxLength - 1).trim()}...`;
}

export function normalizeDescription(description: string): string {
  return description.replace(/\s+/g, ' ').trim();
}

export function descriptionParagraphs(description: string): string[] {
  return description
    .trim()
    .split(/\n\s*\n+/)
    .map((paragraph) => normalizeDescription(paragraph))
    .filter(Boolean);
}

export function searchPayload(experience: Experience): string {
  const enderecos = experience.data.enderecos
    .flatMap((endereco) => [
      endereco.logradouro,
      endereco.numero,
      endereco.complemento ?? '',
      ...endereco.telefones.flatMap((telefone) => [telefone.numero, telefone.formatado]),
    ])
    .join(' ');

  return [
    experience.data.title,
    experience.data.slug,
    experience.data.category,
    experience.data.instagram ?? '',
    experience.data.instagramUrl ?? '',
    experience.data.description ?? '',
    enderecos,
  ]
    .join(' ')
    .toLocaleLowerCase('pt-BR');
}

export function experiencePath(experience: Experience): string {
  return withBase(`/${experience.data.slug}/`);
}

export function buildExperiencesUrl(category?: Category | 'todos', busca?: string): string {
  const params = new URLSearchParams();
  if (category && category !== 'todos') params.set('categoria', category);
  if (busca && busca.trim()) params.set('busca', busca.trim());
  const qs = params.toString();
  return withBase(`/experiencias/${qs ? `?${qs}` : ''}`);
}
