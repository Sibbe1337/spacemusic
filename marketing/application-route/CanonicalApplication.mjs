import { r as React, e as jsx } from "./vendor-DhPEFgb5.js";

export default function CanonicalApplication() {
  const destination = "/apply/" + window.location.search + window.location.hash;
  React.useEffect(() => {
    // /apply/ is a separately deployed application, not a marketing SPA screen.
    // Replace the already-pushed route so Back goes to the referring page.
    window.location.replace(destination);
  }, [destination]);
  return jsx.jsx("main", {
    className: "min-h-screen bg-cream flex items-center justify-center",
    "aria-busy": "true",
    children: jsx.jsx("a", {
      href: destination,
      className: "type-ui text-brand underline",
      children: "Continue to application",
    }),
  });
}
