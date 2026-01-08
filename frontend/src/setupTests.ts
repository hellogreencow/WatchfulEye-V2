// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// JSDOM does not implement canvas. Our landing/transition components use <canvas>
// for particle effects, so stub a minimal 2D context for unit tests.
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: function getContext() {
    // Minimal 2D context surface (no-ops) used by ParticleEyeHero/ParticleTransitionOverlay.
    const noop = () => {};
    return {
      // state
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 0,
      globalAlpha: 1,
      // transforms
      setTransform: noop,
      // rects
      clearRect: noop,
      fillRect: noop,
      // paths
      beginPath: noop,
      arc: noop,
      fill: noop,
      stroke: noop,
      moveTo: noop,
      lineTo: noop,
      // gradients
      createRadialGradient: () => ({ addColorStop: noop }),
    };
  },
});

// CRA/Jest in this repo is not configured to transform ESM in node_modules.
// axios (recent versions) ships ESM entrypoints, which breaks tests with:
// "SyntaxError: Cannot use import statement outside a module".
//
// We mock axios globally for unit tests to keep tests deterministic and avoid
// bundler/jest config churn.
jest.mock('axios', () => {
  // Avoid self-referential inference issues in TS by constructing in two phases.
  const mockAxios: any = {};
  mockAxios.get = jest.fn();
  mockAxios.post = jest.fn();
  mockAxios.put = jest.fn();
  mockAxios.patch = jest.fn();
  mockAxios.delete = jest.fn();
  mockAxios.interceptors = { request: { use: jest.fn() }, response: { use: jest.fn() } };
  mockAxios.defaults = { headers: { common: {} as Record<string, string> } };
  mockAxios.create = jest.fn(() => mockAxios);
  return {
    __esModule: true,
    default: mockAxios,
  };
});
