/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: process.env.SPECTRA_API_URL
          ? `${process.env.SPECTRA_API_URL}/:path*`
          : "http://127.0.0.1:8000/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
