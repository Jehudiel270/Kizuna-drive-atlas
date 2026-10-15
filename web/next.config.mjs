/** @type {import('next').NextConfig} */
const nextConfig = { reactStrictMode: true, eslint: { ignoreDuringBuilds: true }, transpilePackages: ["three"] };
export default nextConfig;
