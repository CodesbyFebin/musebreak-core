/** @type {import("next").NextConfig} */
module.exports = {
  output: "standalone",
  // web-llm is browser/WebGPU only — never bundle it for Node SSR
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals = config.externals || [];
      config.externals.push("@mlc-ai/web-llm");
    }
    config.resolve = config.resolve || {};
    config.resolve.fallback = {
      ...(config.resolve.fallback || {}),
      fs: false,
      path: false,
      crypto: false,
    };
    return config;
  },
};
