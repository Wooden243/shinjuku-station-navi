import "@testing-library/jest-dom/vitest";

if (!window.URL.createObjectURL) {
  window.URL.createObjectURL = () => "blob:test-worker";
}

if (!window.URL.revokeObjectURL) {
  window.URL.revokeObjectURL = () => undefined;
}
