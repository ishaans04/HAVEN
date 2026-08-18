/** @type {import('next').NextConfig} */
const nextConfig = {
  // A static export, served by FastAPI from the same origin as the API.
  //
  // One process and one port rather than two. The console is already entirely
  // client-side -- every component is "use client" and nothing fetches during
  // render -- so there is no server-side rendering to give up, and a single
  // container is the difference between a judge visiting a URL and a judge
  // debugging a virtualenv.
  output: "export",

  // Emits `path/index.html` rather than `path.html`, which is what a plain
  // static file server expects to find behind a directory URL.
  trailingSlash: true,

  // next/image needs a server to optimise. There is none.
  images: { unoptimized: true },
};

export default nextConfig;
