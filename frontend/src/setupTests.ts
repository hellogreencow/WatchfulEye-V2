// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// JSDOM does not implement <canvas>. Many UI components draw to canvas, but unit tests
// should not require a full canvas implementation. Stub getContext to keep tests deterministic.
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: jest.fn(() => {
    // Minimal mock of a 2D context used by our components.
    return {
      clearRect: jest.fn(),
      fillRect: jest.fn(),
      beginPath: jest.fn(),
      arc: jest.fn(),
      fill: jest.fn(),
      createRadialGradient: jest.fn(() => ({
        addColorStop: jest.fn(),
      })),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any;
  }),
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
