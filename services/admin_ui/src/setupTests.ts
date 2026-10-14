import '@testing-library/jest-dom';
import { beforeAll, afterEach, afterAll } from 'vitest';

// Polyfill EventSource and matchMedia for JSDOM (used by DealsPage SSE & Vaul Drawer / Sonner)
if (typeof globalThis.EventSource === 'undefined') {
  class MockEventSource {
    url: string;
    onopen: (() => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((err: unknown) => void) | null = null;
    constructor(url: string) {
      this.url = url;
    }
    close() {}
    addEventListener() {}
    removeEventListener() {}
  }
  // @ts-expect-error polyfill for JSDOM
  globalThis.EventSource = MockEventSource;
}

if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

if (typeof Element !== 'undefined') {
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
}

if (typeof window !== 'undefined' && window.getComputedStyle) {
  const origGetComputedStyle = window.getComputedStyle;
  window.getComputedStyle = (elt: Element, pseudoElt?: string | null) => {
    const style = origGetComputedStyle(elt, pseudoElt);
    if (style && !style.transform) {
      Object.defineProperty(style, 'transform', {
        value: 'none',
        writable: true,
        configurable: true,
      });
    }
    return style;
  };
}

// Import MSW server setup
import { server } from './mocks/server';

// Establish API mocking before all tests.
beforeAll(() => server.listen());

// Reset any request handlers that we may add during the tests,
// so they don't affect other tests.
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished.
afterAll(() => server.close()); 