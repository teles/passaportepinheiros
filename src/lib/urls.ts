const rawBase = import.meta.env.BASE_URL || '/';

export const appBase = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;

export function withBase(path: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(path) || path.startsWith('//')) {
    return path;
  }

  return `${appBase}${path.replace(/^\/+/, '')}`;
}

export function withoutBase(pathname: string): string {
  if (appBase === '/') {
    return pathname || '/';
  }

  const baseWithoutSlash = appBase.replace(/\/$/, '');

  if (pathname === baseWithoutSlash) {
    return '/';
  }

  if (pathname.startsWith(appBase)) {
    return `/${pathname.slice(appBase.length)}`;
  }

  return pathname || '/';
}
